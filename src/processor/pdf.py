'''
Recognize content and format from PDF file with PyMuPDF
@created: 2019-06-24
@author: train8808@gmail.com
---

The raw page content extracted with with PyMuPDF, especially in JSON 
format is described per link:
https://pymupdf.readthedocs.io/en/latest/textpage/

The parsed results of this module is similar to the raw layout dict, 
but with some new features added, e.g.
 - add page margin
 - regroup lines in adjacent blocks considering context
 - recognize list format: block.type=2
 - recognize table format: block.type=3

An example of processed layout result:
    {
    "width": 504.0,
    "height": 661.5,
    "margin": [20.4000, 574.9200, 37.5600, 806.4000],
    "blocks": [{...}, {...}, ...]
    }

Note: The length unit for each boundary box is pt, which is 1/72 Inch.

where the type of blocks is extended from `text` and `image` to `list` 
and `table`:

- text block:
    In addition to the font style (size, color, weight), more text formats,
    including highlight, underline, strike through line, are considered. So
    the `span`-s in `line` are re-grouped with styles, and more keys are 
    added to the original structure of `span`.
        {
            "bbox": [,,,]
            "size": 15.770000457763672,
            "flags": 20,
            "font": "MyriadPro-SemiboldCond",
            "color": 14277081,
            "text": "Adjust Your Headers", # joined from chars
            "chars": [{...}]
            # ----- new items -----
            "style": [{
                "type": 0, # 0-highlight, 1-underline, 2-strike-through-line
                "color": 14277081
                }, {...}]            
        }

- image block
    Normal image block defined in PyMuPDF: 
        { "type": 1, "bbox": [], "ext": "png", "image": , ...}

    Inline image has a same structure, but will be merged into associated text 
    block: a span in block line.

    So, an image structure may exist in block or line span. The key `image` is 
    used to distinguish image type.

- list block

- table block

'''

import fitz
from operator import itemgetter
import copy

from .. import util


def layout(layout, rects, **kwargs):
    ''' processed page layout:
            - split block with multi-lines into seperated blocks
            - merge blocks vertically to complete sentence
            - merge blocks horizontally for convenience of docx generation

        args:
            layout: raw layout data extracted from PDF with
                ```layout = page.getText('dict')```                   

            rects: a list of rectangle shapes extracted from PDF xref_stream,
                [{'bbox': [float,float,float,float], 'color': int }]

            kwargs: dict for layout plotting
                kwargs = {
                    'debug': bool,
                    'doc': fitz document or None,
                    'filename': str
                }            
    '''

    # preprocessing, e.g. change block order, clean negative block, 
    # get span text by joining chars
    _preprocessing(layout, rects, **kwargs)

    # check inline images
    _merge_inline_images(layout, **kwargs)

    # parse text format, e.g. highlight, underline
    _parse_text_format(layout, **kwargs)

    

def rects_from_source(xref_stream, height):
    ''' Get rectangle shape by parsing page cross reference stream.

        Note: 
            these shapes are generally converted from pdf source, e.g. highlight, 
            underline, which are different from PDF comments shape.

        xref_streams:
            doc._getXrefStream(xref).decode()        
        height:
            page height for coordinate system conversion
        
        The context meaning of rectangle shape may be:
           - strike through line of text
           - under line of text
           - highlight area of text

        --------
        
        Refer to:
        - Appendix A from PDF reference for associated operators:
          https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdf_reference_archive/pdf_reference_1-7.pdf
        - https://github.com/pymupdf/PyMuPDF/issues/263

        typical mark of rectangle in xref stream:
            /P<</MCID 0>> BDC
            ...
            1 0 0 1 90.0240021 590.380005 cm
            ...
            1 1 0 rg # or 0 g
            ...
            285.17 500.11 193.97 13.44 re f*
            ...
            EMC

        where,
            - `MCID` indicates a Marked content, where rectangles exist
            - `cm` specify a coordinate system transformation, 
               here (0,0) translates to (90.0240021 590.380005)
            - `q`/`Q` save/restores graphic status
            - `rg` / `g` specify color mode: rgb / grey
            - `re`, `f` or `f*`: fill rectangle path with pre-defined color, 
               in this case,
                - fill color is yellow (1,1,0)
                - lower left corner: (285.17 500.11)
                - width: 193.97
                - height: 13.44

        Note: coordinates system transformation should be considered if text format
              is set from PDF file with edit mode. 

        return a list of rectangles:
            [{
                "bbox": (x0, y0, x1, y1),
                "color": sRGB
             }
             {...}
            ]
    '''
    res = []

    # current working CS is coincident with the absolute origin (0, 0)
    Ax, Ay = 0, 0
    Wx, Wy = 0, 0

    # current graphics color is black
    Ac = util.RGB_value((0, 0, 0))
    Wc = Ac

    # check xref stream word by word (line always changes)    
    begin_text_setting = False    
    lines = xref_stream.split()
    for (i, line) in enumerate(lines):
        # skip any lines between `BT` and `ET`, 
        # since text seeting has no effects on shape        
        if line=='BT':  # begin text
            begin_text_setting = True
       
        elif line=='ET': # end text
            begin_text_setting = False

        if begin_text_setting:
            continue        

        # CS transformation
        if line=='cm':
            # update working CS
            Wx += float(lines[i-2])
            Wy += float(lines[i-1])        

        # painting color
        # gray mode
        elif line=='g': # 0 g
            g = float(lines[i-1])
            Wc = util.RGB_value((g, g, g))

        # RGB mode
        elif line=='rg': # 1 1 0 rg
            r, g, b = map(float, lines[i-3:i])
            Wc = util.RGB_value((r, g, b))

        # save or restore graphics state:
        # only consider transformation and color here
        elif line=='q': # save
            Ax, Ay = Wx, Wy
            Ac = Wc
            
        elif line=='Q': # restore
            Wx, Wy = Ax, Ay
            Wc = Ac

        # finally, come to the rectangle block
        elif line=='re' and lines[i+1] in ('f', 'f*'):
            # (x, y, w, h) before this line
            x, y, w, h = map(float, lines[i-4:i])

            # change bottom left point to top left,
            # consider also the working CS
            x0 = Wx + x
            y0 = Wy + y + h
            x1 = x0 + w
            y1 = Wy + y

            # add rectangle, meanwhile convert bbox to PyMuPDF coordinates system
            res.append({
                'bbox': (x0, height-y0, x1, height-y1), 
                'color': Wc
            })
        
    return res

def rects_from_annots(annots):
    ''' get annotations(comment shapes) from PDF page
        Note: 
            consider highlight, underline, strike-through-line only. 

        annots:
            a list of PyMuPDF Annot objects        
    '''
    res = []

    # map rect type from PyMuPDF
    # Annotation types:
    # https://pymupdf.readthedocs.io/en/latest/vars/#annotationtypes    
    # PDF_ANNOT_HIGHLIGHT 8
    # PDF_ANNOT_UNDERLINE 9
    # PDF_ANNOT_SQUIGGLY 10
    # PDF_ANNOT_STRIKEOUT 11
    type_map = { 8: 0, 9: 1, 11: 2}

    for annot in annots:

        # consider highlight, underline, strike-through-line only.
        # e.g. annot.type = (8, 'Highlight')
        if not annot.type[0] in (8,9,11): 
            continue
        
        # color, e.g. {'stroke': [1.0, 1.0, 0.0], 'fill': []}
        c = annot.colors.get('stroke', (0,0,0)) # black by default

        # convert rect coordinates
        rect = annot.rect

        res.append({
            'type': type_map[annot.type[0]],
            'bbox': (rect.x0, rect.y0, rect.x1, rect.y1),
            'color': util.RGB_value(c)
        })

    return res

def plot_layout(doc, layout, title):
    '''plot layout with PyMuPDF
       doc: fitz document object
    '''
    # insert a new page with borders
    page = _new_page_with_margin(doc, layout, title)    

    # plot blocks
    for block in layout['blocks']:
        # block border
        blue = util.getColor('blue')
        r = fitz.Rect(block['bbox'])
        page.drawRect(r, color=blue, fill=None, width=0.5, overlay=False)

        # spans in same line show same color
        for line in block.get('lines', []): # TODO: other types, e.g. image, list, table            
            red = util.getColor('red')
            r = fitz.Rect(line['bbox'])
            page.drawRect(r, color=red, fill=None, overlay=False)

            # spans in current block
            for span in line.get('spans', []):
                c = util.getColor('')
                r = fitz.Rect(span['bbox'])
                page.drawRect(r, color=c, fill=c, overlay=False)

def plot_rectangles(doc, layout, rects, title):
    ''' plot rectangles with PyMuPDF

        width, height: page width/height
        rects: a list of rectangles recognized from xref stream
        doc: fitz document object
    '''
    if not rects: return

    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw rectangle one by one
    for rect in rects:
        # fill color
        c = util.RGB_component(rect['color'])
        c = [_/255.0 for _ in c]
        page.drawRect(rect['bbox'], color=c, fill=c, overlay=False)


# ---------------------------------------------

def _new_page_with_margin(doc, layout, title):
    ''' insert a new page and plot margin borders'''
    # insert a new page
    w, h = layout['width'], layout['height']
    page = doc.newPage(width=w, height=h)
    
    # plot page margin
    red = util.getColor('red')
    args = {
        'color': red,
        'width': 0.5
    }
    dL, dR, dT, dB = layout.get('margin', _page_margin(layout)) 
    page.drawLine((dL, 0), (dL, h), **args) # left border
    page.drawLine((w-dR, 0), (w-dR, h), **args) # right border
    page.drawLine((0, dT), (w, dT), **args) # top
    page.drawLine((0, h-dB), (w, h-dB), **args) # bottom

    # plot title within the top margin
    page.insertText((dL, dT*0.75), title, color=red, fontsize=dT/2.0)

    return page


def _debug_plot(title, plot=True):
    '''plot layout for debug'''
    def wrapper(func):
        def inner(*args, **kwargs):
            # execute function
            func(*args, **kwargs)

            # check if plot layout
            debug = kwargs.get('debug', False)
            doc = kwargs.get('doc', None)
            if plot and debug and doc is not None:
                layout = args[0]
                plot_layout(doc, layout, title)
        
        return inner
    return wrapper


@_debug_plot('Preprocessed', True)
def _preprocessing(layout, rects, **kwargs):
    '''preprocessing for the raw layout of PDF page'''
    # remove blocks exceeds page region: negative bbox
    layout['blocks'] = list(filter(
        lambda block: all(x>0 for x in block['bbox']), 
        layout['blocks']))

    # reorder to reading direction:
    # from up to down, from left to right
    layout['blocks'].sort(
        key=lambda block: (block['bbox'][1], 
            block['bbox'][0]))

    # calculate page margin
    layout['margin'] = _page_margin(layout)

    # assign rectangle shapes to associated block;
    # get span text by joining chars
    for block in layout['blocks']:
        # skip image
        if block['type']==1: continue

        # assign rectangles
        block['_rects'] = []
        block_rect = fitz.Rect(block['bbox'])
        for rect in rects:
            # any intersection?
            if block_rect.intersects(rect['bbox']):
                block['_rects'].append(rect)

        # join chars
        for line in block['lines']:
            for span in line['spans']:
                chars = [char['c'] for char in span['chars']]
                span['text'] = ''.join(chars)
    
@_debug_plot('Merged inline images', True)
def _merge_inline_images(layout, **kwargs):
    ''' merge inline image blocks into text block: 
        a block line or a line span.
    '''
    # get all images blocks with index
    f = lambda item: item[1]['type']==1
    index_images = list(filter(f, enumerate(layout['blocks'])))

    # get index of inline images: intersected with text block
    # assumption: an inline image intersects with only one text block
    index_inline = []
    num = len(index_images)
    for block in layout['blocks']:

        # suppose no overlap between two images
        if block['type']==1: continue

        # all images found their block, then quit
        if len(index_inline)==num: break

        # check all images for current block
        image_merged = False
        for i, image in index_images:
            # an inline image belongs to only one block
            if i in index_inline: continue

            # horizontally aligned with current text block?
            # no, pass
            if not util.is_horizontal_aligned(block['bbox'], image['bbox']): continue

            # yes, inline image
            image_merged = True
            index_inline.append(i)
            _insert_image_to_block(image, block)

        # if current block get images merged as new line,
        # go further step here: merge image into span if necessary
        if image_merged:
            _merge_lines_in_block(block)

    # remove inline images from top layout
    # the index of element in original list changes when any elements are removed
    # so try to 
    for i in index_inline[::-1]:
        layout['blocks'].pop(i)

@_debug_plot('Parsed Text Format', True)
def _parse_text_format(layout, **kwargs):
    '''parse text format with rectangle style'''
    for block in layout['blocks']:
        if block['type']==1: continue
        if not block['_rects']: continue

        # use each rectangle (a specific text format) to split line spans
        for rect in block['_rects']:
            the_rect = fitz.Rect(rect['bbox'])
            for line in block['lines']:
                # any intersection in this line?
                line_rect = fitz.Rect(line['bbox'])
                intsec = the_rect & ( line_rect + util.DR )
                if not intsec: continue

                # yes, then try to split the spans in this line
                split_spans = []
                for span in line['spans']: 
                    # split span with the format rectangle: span-intersection-span
                    tmp_span = _split_span_with_rect(span, rect)
                    split_spans.extend(tmp_span)
                                                   
                # update line spans                
                line['spans'] = split_spans


def _split_span_with_rect(span, rect):
    '''split span with the intersection: span-intersection-span'''

    # split spans
    split_spans = []

    # any intersection in this span?
    span_rect = fitz.Rect(span['bbox'])
    the_rect = fitz.Rect(rect['bbox'])
    intsec = the_rect & span_rect

    # no, then add this span as it is
    if not intsec:
        split_spans.append(span)

    # yes, then split spans:
    # - add new style to the intersection part
    # - keep the original style for the rest
    else:
        # expand the intersection area, e.g. for strike through line,
        # the intersection is a `line`, i.e. a rectangle with very small height,
        # so expand the height direction to span height
        intsec.y0 = span_rect.y0
        intsec.y1 = span_rect.y1

        # calculate chars in the format rectangle
        pos, length = _index_chars_in_rect(span, intsec)
        pos_end = max(pos+length, 0) # max() is used in case: pos=-1, length=0

        # split span with the intersection: span-intersection-span
        # 
        # left part if exists
        if pos > 0:
            split_span = copy.deepcopy(span)
            split_span['bbox'] = (span_rect.x0, span_rect.y0, intsec.x0, span_rect.y1)
            split_span['chars'] = span['chars'][0:pos]
            split_span['text'] = span['text'][0:pos]
            split_spans.append(split_span)

        # middle intersection part if exists
        if length > 0:
            split_span = copy.deepcopy(span)            
            split_span['bbox'] = (intsec.x0, intsec.y0, intsec.x1, intsec.y1)
            split_span['chars'] = span['chars'][pos:pos_end]
            split_span['text'] = span['text'][pos:pos_end]

            # update style
            new_style = util.rect_to_style(rect, split_span['bbox'])
            if new_style:
                if 'style' in split_span:
                    split_span['style'].append(new_style)
                else:
                    split_span['style'] = [new_style]

            split_spans.append(split_span)                

        # right part if exists
        if pos_end < len(span['chars']):
            split_span = copy.deepcopy(span)
            split_span['bbox'] = (intsec.x1, span_rect.y0, span_rect.x1, span_rect.y1)
            split_span['chars'] = span['chars'][pos_end:]
            split_span['text'] = span['text'][pos_end:]
            split_spans.append(split_span)

    return split_spans
 

def _index_chars_in_rect(span, rect):
    ''' get the index of span chars in a given rectangle region

        return (start index, length) of span chars
    '''
    # combine an index with enumerate(), so the second element is the char
    f = lambda items: util.is_char_in_rect(items[1], rect)
    index_chars = list(filter(f, enumerate(span['chars'])))

    # then we get target chars in a sequence
    pos = index_chars[0][0] if index_chars else -1 # start index -1 if nothing found
    length = len(index_chars)

    return pos, length


def _page_margin(layout):
    '''get page margin:
       - left: as small as possible in x direction and should not intersect with any other bbox
       - right: MIN(left, width-max(bbox[3]))
       - top: MIN(bbox[1])
       - bottom: height-MAX(bbox[3])
    '''

    # check candidates for left margin:
    list_bbox = list(map(lambda x: x['bbox'], layout['blocks']))
    list_bbox.sort(key=lambda x: (x[0], x[2]))
    lm_bbox, num = list_bbox[0], 0
    candidates = []
    for bbox in list_bbox:
        # count of blocks with save left border
        if abs(bbox[0]-lm_bbox[0])<util.DM:
            num += 1
        else:
            # stop counting if current block border is not equal to previous,
            # then get the maximum count of aligned blocks
            candidates.append((lm_bbox, num))

            # start to count current block border. this border is invalid if intersection with 
            # previous block occurs, so count it as -1
            num = 1 if bbox[0]>lm_bbox[2] else -1

        lm_bbox = bbox
    else:
        candidates.append((lm_bbox, num)) # add last group

    # if nothing found, e.g. whole page is an image, return standard margin
    if not candidates:
        return (util.ITP, ) * 4 # 1 Inch = 72 pt

    # get left margin which is supported by bboxes as more as possible
    candidates.sort(key=lambda x: x[1], reverse=True)
    left = candidates[0][0][0]

    # right margin
    x_max = max(map(lambda x: x[2], list_bbox))
    w, h = layout['width'], layout['height']
    right = min(w-x_max, left)

    # top/bottom margin
    top = min(map(lambda x: x[1], list_bbox))
    bottom = h-max(map(lambda x: x[3], list_bbox))

    return left, right, top, min(util.ITP, bottom)


def _insert_image_to_block(image, block):
    '''insert inline image to associated block'''
    image_rect = fitz.Rect(image['bbox'])

    # get the insetting position
    for i,line in enumerate(block['lines']):
        if image_rect.x0 < line['bbox'][0]:
            break
    else:
        i = 0

    # insert image as a line in block, 
    # and waiting for further step: merge image into span as necessary
    image_line = {
        "wmode": 0,
        "dir"  : (1, 0),
        "bbox" : image['bbox'],
        "spans": [image]
        }
    block['lines'].insert(i, image_line)

    # update bbox accordingly
    x0 = min(block['bbox'][0], image['bbox'][0])
    y0 = min(block['bbox'][1], image['bbox'][1])
    x1 = max(block['bbox'][2], image['bbox'][2])
    y1 = max(block['bbox'][3], image['bbox'][3])
    block['bbox'] = (x0, y0, x1, y1)


def _merge_lines_in_block(block):
    ''' Merge lines aligned horizontally in a block.
        Generally, it is performed when inline image is added into block line.
    '''
    new_lines = []
    for line in block['lines']:        
        # add line directly if not aligned horizontally with previous line
        if not new_lines or not util.is_horizontal_aligned(line['bbox'], new_lines[-1]['bbox']):
            new_lines.append(line)
            continue

        # if it exists x-distance obviously to previous line,
        # take it as a separate line as it is
        if abs(line['bbox'][0]-new_lines[-1]['bbox'][2]) > util.DM:
            new_lines.append(line)
            continue

        # now, this line will be append to previous line as a span
        new_lines[-1]['spans'].extend(line['spans'])

        # update bbox
        new_lines[-1]['bbox'] = (
            new_lines[-1]['bbox'][0],
            min(new_lines[-1]['bbox'][1], line['bbox'][1]),
            line['bbox'][2],
            max(new_lines[-1]['bbox'][3], line['bbox'][3])
            )

    # update lines in block
    block['lines'] = new_lines


