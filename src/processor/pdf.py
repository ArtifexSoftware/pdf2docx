'''
PDF text and format pre-processor
@created: 2019-06-24
@author: train8808@gmail.com
---

Recognize content and format based on page layout data extracted
from PDF file with package PyMuPDF. The length unit for each boundary
box is pt, which is 1/72 Inch.

The structure of results is similar to the raw layout dict, but with
meaning of some parameters changed, e.g.
 - add page margin
 - change type of block: paragraph(0), table(1);
 - change wmode of line: text(0), bullet(1), image(2);
 - spans of line is changed from a list of dict to a single dict, and
   with a new key `mark` added for wmode=1, which is the bullet symbol.
 - properties of image block, e.g. width, height, are moved to `lines`

An example of processed layout result:

{
  "width": 504.0,
  "height": 661.5,
  "margin": [20.399999618530273, 574.9200077056885, 37.559967041015625, 806.4000244140625],
  "blocks": [
    {
      "type": 0,
      "bbox": [72.0,62.310791015625,175.2935028076172,81.2032470703125],
      "lines": [
        {
          "wmode": 0,
          "dir": [1.0,0.0],
          "bbox": [72.0,62.310791015625,175.2935028076172,81.2032470703125],
          "spans": {
            "size": 15.770000457763672,
            "flags": 20,
            "font": "MyriadPro-SemiboldCond",
            "text": "Adjust Your Headers "
          }
        },
        {...} # more lines
      ]
    },
    {...} # more blocks
   ]
}

'''

from .. import util


def layout(layout):
    '''processed page layout:
        - split block with multi-lines into seperated blocks
        - merge blocks vertically to complete sentence
        - merge blocks horizontally for convenience of docx generation

       args:
           layout: raw layout data extracted from PDF with 

           ```layout = page.getText('dict')```
    '''

    # split blocks
    layout = _split_blocks(layout)

    # detect table here
    # TODO

    # merge blocks verticaly
    layout = _merge_vertical_blocks(layout)

    # merge blocks horizontally
    layout = _merge_horizontal_blocks(layout)

    # margin
    layout['margin'] = _page_margin(layout)

    return layout

def layout_debug(layout):
    '''plot page layout during parsing process'''

    import matplotlib.pyplot as plt

    # original layout
    ax = plt.subplot(151)
    plot_layout(ax, layout, 'raw')
    

    # split blocks
    layout = _split_blocks(layout)
    ax = plt.subplot(152)
    plot_layout(ax, layout, 'split blocks')

    # detect table here
    # TODO

    # merge blocks vertically
    layout = _merge_vertical_blocks(layout)
    ax = plt.subplot(153)
    plot_layout(ax, layout, 'merge blocks vertically')

    # merge blocks horizontally
    layout = _merge_horizontal_blocks(layout)
    ax = plt.subplot(154)
    plot_layout(ax, layout, 'merge blocks horizontally')

    # margin
    layout['margin'] = _page_margin(layout)

    plt.show()

    return layout

def plot_layout(axis, layout, title='page layout'):
    '''plot page layout for debug'''

    w, h = layout['width'], layout['height']
    blocks = layout['blocks']

    # plot setting
    axis.set_title(title)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_xlim(0, w)
    axis.set_ylim(0, h)
    axis.xaxis.set_ticks_position('top')
    axis.yaxis.set_ticks_position('left')
    axis.invert_yaxis()
    axis.set_aspect('equal')

    # plot left/right margin
    dL, dR, dT, dB = _page_margin(layout)
    axis.plot([dL, dL], [0, h], 'r--', linewidth=0.5)
    axis.plot([w-dR, w-dR,], [0, h], 'r--', linewidth=0.5)
    axis.plot([0, w,], [dT, dT], 'r--', linewidth=0.5)
    axis.plot([0, w,], [h-dB, h-dB], 'r--', linewidth=0.5)

    # plot block position
    for i, block in enumerate(blocks):
        # lines in current block
        for line in block.get('lines', []):
            patch = util.rectangle(line['bbox'], linecolor='w', fillcolor=util.getColor(i))
            axis.add_patch(patch)

        # block border
        patch = util.rectangle(block['bbox'], linecolor='k')
        axis.add_patch(patch)

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

            # combine spans in line
            for line in lines:
                jonied_span_text = ' '.join(map(__process_line, line['spans']))
                line['spans'] = line['spans'][0]
                line['spans']['text'] = jonied_span_text

                # convert each line to a block
                splited_block = {
                    'type': block['type'],
                    'bbox': line['bbox'],
                    'lines': [line]
                }

                blocks.append(splited_block)

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
        - suppose pragraph margin is larger than line margin
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

            # ignore if sentence completence is not satisfied
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
