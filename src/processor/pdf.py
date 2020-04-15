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
            "size": 15.770000457763672,
            "flags": 20,
            "font": "MyriadPro-SemiboldCond",
            "color": 14277081,
            "text": "Adjust Your Headers",
            # ----- new items -----
            "style": [{
                "type": 0, # 0-highlight, 1-underline, 2-strike-through-line
                "color": 14277081
                }, {...}]            
          }

- image block
    {
      "type": 1,
      "bbox": [72.0,62.310791015625,175.2935028076172,81.2032470703125],
      "ext": "png",
      "width": ,
      "height": '
      "image": ,
      ...
    }

- list block

- table block

'''

import fitz
from operator import itemgetter
import copy

from .. import util


def layout(layout, words, rects, **kwargs):
    ''' processed page layout:
            - split block with multi-lines into seperated blocks
            - merge blocks vertically to complete sentence
            - merge blocks horizontally for convenience of docx generation

        args:
            layout: raw layout data extracted from PDF with
                ```layout = page.getText('dict')```
                   
            words: words with bbox extracted from PDF with
                ```words = page.getTextWords()```           
                each word is represented by:
                (x0, y0, x1, y1, word, bno, lno, wno), where the first 4 
                entries are the word's rectangle coordinates, the last 3 
                are just technical info: block number, line number and 
                word number.

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
    # update rectangle reference point
    _preprocessing(layout, rects, **kwargs)

    # parse text format, e.g. highlight, underline
    _parse_text_format(layout, words, **kwargs)

    # original layout
    # ax = plt.subplot(111)
    # plot_layout(ax, layout, 'raw')
    

    # # split blocks
    # layout = _split_blocks(layout)
    # ax = plt.subplot(152)
    # plot_layout(ax, layout, 'split blocks')

    # detect table here
    # TODO

    # # merge blocks vertically
    # layout = _merge_vertical_blocks(layout)
    # ax = plt.subplot(153)
    # plot_layout(ax, layout, 'merge blocks vertically')

    # # merge blocks horizontally
    # layout = _merge_horizontal_blocks(layout)
    # ax = plt.subplot(154)
    # plot_layout(ax, layout, 'merge blocks horizontally')

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
        page.drawRect(r, color=blue, fill=None, overlay=False)

        # spans in current block
        for line in block.get('lines', []): # TODO: other types, e.g. image, list, table
            for span in line.get('spans', []):
                c = util.getColor() # random color
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


@_debug_plot('Preprocessing', True)
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

    # assign rectangle shapes to associated block
    for block in layout['blocks']:
        if block['type']==1: continue
        block['_rects'] = []
        block_rect = fitz.Rect(*block['bbox']) + util.DR # a bit enlarge
        for rect in rects:
            if block_rect.contains(rect['bbox']):
                block['_rects'].append(rect)
    
    # margin
    layout['margin'] = _page_margin(layout)


@_debug_plot('Parse Text Format', True)
def _parse_text_format(layout, words, **kwargs):
    '''parse text format with rectangle style'''
    for block in layout['blocks']:
        if block['type']==1: continue
        if not block['_rects']: continue

        # use each rectangle (a specific text format) to split line spans
        for rect in block['_rects']:

            the_rect = fitz.Rect(*rect['bbox'])

            for line in block['lines']:
                # any intersection in this line?
                line_rect = fitz.Rect(*line['bbox'])
                intsec = the_rect & ( line_rect + util.DR )
                if not intsec: continue

                # yes, then try to split the spans in this line
                split_spans = []
                for span in line['spans']: 
                    # split span with the intersection: span-intersection-span
                    tmp_span = _split_span_with_rect(span, rect, words)
                    split_spans.extend(tmp_span)
                                                   
                # update line spans                
                line['spans'] = split_spans


def _split_span_with_rect(span, rect, words):
    '''split span with the intersection: span-intersection-span'''

    # split spans
    split_spans = []

    # any intersection in this span?
    span_rect = fitz.Rect(*span['bbox'])
    the_rect = fitz.Rect(*rect['bbox'])
    # do not enlarge span_rect here to avoid introduce extra intersection
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

        # split span with the intersection: span-intersection-span
        # 
        # left part if exists
        if intsec.x0 > span_rect.x0:
            split_span = copy.deepcopy(span)
            # update bbox -> move bottom right corner, i.e.
            # split_span['bbox'][2] -> intsec.x0
            split_span['bbox'] = (span_rect.x0, span_rect.y0, intsec.x0, span_rect.y1)

            # update text: invalid span if text is empty
            text = _text_in_rect(words, split_span['bbox'])
            if text:
                split_span['text'] = text + ' '
                split_spans.append(split_span)

        # middle part: intersection part
        if intsec.x0 < intsec.x1:
            split_span = copy.deepcopy(span)            
            split_span['bbox'] = (intsec.x0, intsec.y0, intsec.x1, intsec.y1)

            # update text: invalid span if text is empty
            text = _text_in_rect(words, split_span['bbox'])
            if text:
                split_span['text'] = text + ' '
                # add new style
                new_style = util.rect_to_style(rect, split_span['bbox'])
                if new_style:
                    if 'style' in split_span:
                        split_span['style'].append(new_style)
                    else:
                        split_span['style'] = [new_style]

                split_spans.append(split_span)

        # right part if exists
        if intsec.x1 < span_rect.x1:
            split_span = copy.deepcopy(span)
            # update bbox -> move top left corner, i.e.
            # split_span['bbox'][0] -> intsec.x1
            split_span['bbox'] = (intsec.x1, span_rect.y0, span_rect.x1, span_rect.y1)

            # update text: invalid span if text is empty
            text = _text_in_rect(words, split_span['bbox'])
            if text:
                split_span['text'] = text + ' '
                split_spans.append(split_span)

    return split_spans
 


def _text_in_rect(words, rect):
    '''get text within rect, refer to:
       https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/textboxtract.py
    '''
    if isinstance(rect, (tuple, list)):
        rect = fitz.Rect(rect)

    # words in rect
    f = lambda word: util.is_word_in_rect(word, rect)
    mywords = list(filter(f, words))

    # sort by y1, x0 of the word rect
    mywords.sort(key=itemgetter(3, 0))
    texts = [w[4] for w in mywords]

    return ' '.join(texts)



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




def _split_blocks(layout):
    '''split block with multi-lines into single line block, which will be used to 
       merge block in next step. Besides, remove duplicated blocks.

       args:
            layout: raw layout data

       notes:
           for image block, it is converted from original data format to a
           similar text block format:
           raw image block: 
                    {'type':1, 'bbox', 'width', 'height', 'ext', 'image'} 
           converted text block: 
                    {'type':0, 'bbox', 'lines': [
                'wmode':2, 'dir', 'bbox', 'width', 'height', 'ext', 'image']}
    '''
    blocks, ref = [], None
    for block in layout['blocks']:

        # check duplication
        if ref and ref['bbox']==block['bbox']:
            continue

        # image block: convert to text block format
        if block['type']==1:
            block['type'] = 0 # treat as normal block
            block['lines'] = [{
                'wmode': 2, # 0 text, 1 bullet, 2 image
                'dir': (1.0, 0.0),
                'bbox': block['bbox'],
                'width': block['width'],
                'height': block['height'],
                'ext': block['ext'],
                'image': block['image']
            }]
            block.pop('image')

        # split text blocks
        else: 
            lines = block['lines']

            # convert each line to a block
            for line in lines:
                split_block = {
                    'type': block['type'],
                    'bbox': line['bbox'],
                    'lines': [line]
                }

                blocks.append(split_block)

        # update reference block
        ref = block

    layout['blocks'] = blocks
    return layout

def _merge_vertical_blocks(layout):
    '''a sentence may be seperated in different blocks, so this step is to merge them back.

       merging conditions:
        - previous line is not the end and current line is not the begin
        - two lines should be in same font and size
        - skip if current line is a bullet item / image
        - suppose paragraph margin is larger than line margin
        - remove overlap/duplicated blocks
    '''

    blocks = layout['blocks']
    merged_blocks = []
    ref = None # previous merged block
    ref_line_space = 0.0 # line space for the recently merged blocks

    for block in blocks:
        merged = False

        if not ref:
            merged_blocks.append(block)

        # ignore image/bullet line
        elif ref['lines'][0]['wmode']==2 or block['lines'][0]['wmode']!=0:
            merged_blocks.append(block)

        else:
            dy = block['bbox'][1]-ref['bbox'][3] # line space
            h = ref['bbox'][3]-ref['bbox'][1] # previous blcok height
            span1 = ref['lines'][0]['spans']
            span2 = block['lines'][0]['spans']

            # ignore empty lines
            if not ref['lines'][0]['spans']['text'].strip() or not block['lines'][0]['spans']['text'].strip():
                merged_blocks.append(block)

            # ignore blocks not aligned in vertical direction
            elif not util.is_vertical_aligned(ref['bbox'], block['bbox']):
                merged_blocks.append(block)        

            # ignore abnormal line space:
            # (a) line space is larger than height of previous block
            elif dy>h:
                merged_blocks.append(block)

            # (b) current line space is different from line space of recently merged blocks
            elif ref_line_space and abs(dy-ref_line_space)>=util.DM:
                merged_blocks.append(block)
            
            # ignore abnormal font
            elif span1['font']!=span2['font'] or span1['size']!=span2['size']: 
                merged_blocks.append(block)

            # ignore if sentence completeness is not satisfied
            elif util.is_end_sentence(span1['text']) or util.is_start_sentence(span2['text']):
                merged_blocks.append(block)

            # finally, it could be merged
            else:
                merged = True
                # combine block to ref
                left = min(block['bbox'][0], ref['bbox'][0])
                right = max(block['bbox'][2], ref['bbox'][2])
                top = min(block['bbox'][1], ref['bbox'][1])
                bottom = max(block['bbox'][3], ref['bbox'][3])
                merged_blocks[-1]['bbox'] = (left, top, right, bottom)
                merged_blocks[-1]['lines'][0]['bbox'] = (left, top, right, bottom)
                merged_blocks[-1]['lines'][0]['spans']['text'] += block['lines'][0]['spans']['text']

        # update reference line space if merged
        ref_line_space = dy if merged else 0.0

        # update reference block
        ref = merged_blocks[-1]

    layout['blocks'] = merged_blocks
    return layout

def _merge_horizontal_blocks(layout):
    '''merge associated blocks in same line, which is preceding steps for creating docx.       
    '''

    # raw layout has been sorted, but after splitting block step, the split blocks may be
    # in wrong order locally. so re-sort all blocks first in this step.
    layout['blocks'].sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))

    # group blocks with condition: aligned horizontally
    grouped_blocks, vertical_blocks = [[]], []
    iblocks = iter(layout['blocks'])
    while True:
        block = next(iblocks, None)
        if not block: break

        # ignore empty lines after an image
        line = block['lines'][0]
        if line['wmode']==0 and not line['spans']['text'].strip(): # empty line
            # check previous block
            if grouped_blocks[-1] and grouped_blocks[-1][-1]['lines'][0]['wmode']==2:
                continue

        # collect vertical blocks directly
        if block['lines'][0]['dir'] != (1.0,0.0):
            vertical_blocks.append(block)
            continue

        # collect horizontal blocks in a same line
        for ref in grouped_blocks[-1]:
            if util.is_horizontal_aligned(ref['bbox'], block['bbox']):
                flag = True
                break
        else:
            flag = False

        if flag:
            grouped_blocks[-1].append(block)
        else:
            grouped_blocks.append([block])

    # combine blocks
    merged_blocks = vertical_blocks # do not have to merge vertical blocks
    for blocks in grouped_blocks[1:]: # skip the first [] when initialize grouped_blocks 
        # update bbox
        left = min(map(lambda x: x['bbox'][0], blocks))
        top = min(map(lambda x: x['bbox'][1], blocks))
        right = max(map(lambda x: x['bbox'][2], blocks))
        bottom = max(map(lambda x: x['bbox'][3], blocks))

        # merged block if there is no overlap between two adjacent blocks
        bbox_pre_block = merged_blocks[-1]['bbox'] if merged_blocks else [0.0]*4
        if abs(left-bbox_pre_block[0])>util.DM or abs(top-bbox_pre_block[1])>util.DM:
            merged_block = {
                'type': 0,
                'bbox': (left, top, right, bottom),
                'lines': list(map(lambda block:block['lines'][0], blocks))
            }
            merged_block['type'] = __block_type(merged_block)
            merged_blocks.append(merged_block)

    layout['blocks'] = merged_blocks
    return layout

def __block_type(block, factor=0.5):
    ''' type of the block:
        - paragraph (0): one line block or multi-line sets in a single word line
        - table(1): otherwise
    '''

    lines = block['lines']

    if len(lines)==1:
        return 0
    else:
        # multi-line sets aligned in one line:
        # the factor of minimum line height to block height should lower than a threshold
        line_height = min(map(lambda line: line['spans']['size'], lines))
        block_height = block['bbox'][3] - block['bbox'][1]

        return 0 if line_height/block_height > factor else 1


def __process_line(span):
    '''combine text in lines to a complete sentence'''
    text = span['text'].strip()
    if text.endswith(('‐', '-')): # these two '-' are not same
        text = text[0:-1]
    else:
        text += ' '
    return text
