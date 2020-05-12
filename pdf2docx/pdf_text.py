'''
Recognize text and image format.

In addition to the font style (size, color, weight), more text formats, including 
highlight, underline, strike through line, are considered. So, the span-s in line 
are re-grouped with styles, and more keys are added to the original structure of span.
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

Normal image block defined in PyMuPDF: 
    { "type": 1, "bbox": [], "ext": "png", "image": , ...}

Inline image has a same structure, but will be merged into associated text block: 
a span in block line. So, an image structure may exist in block or line span. 
The key `image` is used to distinguish image type.

'''

import fitz
import copy

from .pdf_debug import debug_plot
from .pdf_shape import rect_to_style
from . import utils


@debug_plot('Merged Inline Images', True)
def merge_inline_images(layout, **kwargs):
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
            if not utils.is_horizontal_aligned(block['bbox'], image['bbox']): continue

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

    # anything changed in this step?
    return True if index_inline else False


@debug_plot('Parsed Text Format', True)
def parse_text_format(layout, **kwargs):
    '''parse text format with rectangle style'''

    is_layout_updated = False

    for block in layout['blocks']:
        if block['type']==1: continue

        block_rect = fitz.Rect(block['bbox'])

        # use each rectangle (a specific text format) to split line spans
        for rect in layout['rects']:

            # any intersection with current block?
            the_rect = fitz.Rect(rect['bbox'])
            if not block_rect.intersects(the_rect): continue

            # yes, then go further to lines in block            
            for line in block['lines']:
                # any intersection in this line?
                line_rect = fitz.Rect(line['bbox'])
                intsec = the_rect & ( line_rect + utils.DR )
                if not intsec: continue

                # yes, then try to split the spans in this line
                split_spans = []
                for span in line['spans']: 
                    # split span with the format rectangle: span-intersection-span
                    tmp_span = _split_span_with_rect(span, rect)
                    split_spans.extend(tmp_span)
                                                   
                # update line spans                
                line['spans'] = split_spans
                is_layout_updated = True

    # anything changed in this step?
    return is_layout_updated


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
            new_style = rect_to_style(rect, split_span['bbox'])
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
    f = lambda items: utils.is_char_in_rect(items[1], rect)
    index_chars = list(filter(f, enumerate(span['chars'])))

    # then we get target chars in a sequence
    pos = index_chars[0][0] if index_chars else -1 # start index -1 if nothing found
    length = len(index_chars)

    return pos, length


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
        if not new_lines or not utils.is_horizontal_aligned(line['bbox'], new_lines[-1]['bbox']):
            new_lines.append(line)
            continue

        # if it exists x-distance obviously to previous line,
        # take it as a separate line as it is
        if abs(line['bbox'][0]-new_lines[-1]['bbox'][2]) > utils.DM:
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

