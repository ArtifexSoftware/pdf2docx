'''
`blocks` are a group of page contents. The type of blocks is extended from 
the default `text` and `image` to `list` and `table`:
    - text block: type=0
    - image block: type=1
    - list block: type=2
    - table block: type=3 (explicit) or 4 (implicit table)
'''

import fitz

from . import utils



def is_text_block(block):
    return block.get('type', -1)==0


def is_image_block(block):
    return block.get('type', -1)==1


def is_list_block(block):
    return block.get('type', -1)==2


def is_explicit_table_block(block):
    return block.get('type', -1)==3


def is_implicit_table_block(block):
    return block.get('type', -1)==4


def is_table_block(block):
    return is_explicit_table_block(block) or is_implicit_table_block(block)


def set_text_block(block):
    block['type'] = 0


def set_explicit_table_block(block):
    block['type'] = 3


def set_implicit_table_block(block):
    block['type'] = 4


def is_discrete_lines_in_block(block, distance=25, threshold=3):
    ''' Check whether lines in block are discrete: 
        the count of lines with a distance larger than `distance` is greater then `threshold`.
    '''
    if not is_text_block(block): return False

    num = len(block['lines'])
    if num==1: return False

    # check the count of discrete lines
    cnt = 0
    for i in range(num-1):
        bbox = block['lines'][i]['bbox']
        next_bbox = block['lines'][i+1]['bbox']

        if utils.is_horizontal_aligned(bbox, next_bbox):
            # horizontally aligned but not in a same row -> discrete block
            if not utils.in_same_row(bbox, next_bbox):
                return True
            
            # otherwise, check the distance only
            else:
                if abs(bbox[2]-next_bbox[0]) > distance:
                    cnt += 1

    return cnt > threshold


def remove_floating_blocks(blocks):
    ''' Remove floating blocks, especially images. When a text block is floating behind 
        an image block, the background image block will be deleted, considering that 
        floating elements are not supported in python-docx when re-create the document.
    '''
    # get text/image blocks seperately, and suppose no overlap between text blocks
    text_blocks = list(
        filter( lambda block: is_text_block(block),  blocks))
    image_blocks = list(
        filter( lambda block: is_image_block(block),  blocks))    

    # check image block: no significant overlap with any text/image blocks
    res_image_blocks = []
    for image_block in image_blocks:
        # 1. overlap with any text block?
        for text_block in text_blocks:            
            if utils.get_main_bbox(image_block['bbox'], text_block['bbox'], 0.75):
                overlap = True
                break
        else:
            overlap = False

        # yes, then this is an invalid image block
        if overlap: continue

        # 2. overlap with any valid image blocks?
        for valid_image in res_image_blocks:
            if utils.get_main_bbox(image_block['bbox'], valid_image['bbox'], 0.75):
                overlap = True
                break
        else:
            overlap = False
        
        # yes, then this is an invalid image block
        if overlap: continue

        # finally, add this image block
        res_image_blocks.append(image_block)

    # return all valid blocks
    res = []
    res.extend(text_blocks)
    res.extend(res_image_blocks)
    return res


def merge_blocks(blocks):
    '''merge blocks aligned horizontally.'''
    res = []
    for block in blocks:
        # convert to text block if image block
        if is_image_block(block):
            text_block = convert_image_to_text_block(block)
        else:
            text_block = block

        # add block directly if not aligned horizontally with previous block
        if not res or not utils.is_horizontal_aligned(text_block['bbox'], res[-1]['bbox']):
            res.append(text_block)

        # otherwise, append to previous block as lines
        else:
            res[-1]['lines'].extend(text_block['lines'])

            # update bbox
            res[-1]['bbox'] = (
                min(res[-1]['bbox'][0], text_block['bbox'][0]),
                min(res[-1]['bbox'][1], text_block['bbox'][1]),
                max(res[-1]['bbox'][2], text_block['bbox'][2]),
                max(res[-1]['bbox'][3], text_block['bbox'][3])
                )

    return res


def convert_image_to_text_block(image):
    '''convert image block to text block: a span'''
    # convert image as a span in line
    image_line = {
        "wmode": 0,
        "dir"  : (1, 0),
        "bbox" : image['bbox'],
        "spans": [image]
        }
    
    # insert line to block
    block = {
        'type': -1,
        'bbox': image['bbox'],
        'lines': [image_line]
    }

    # set text block
    set_text_block(block)

    return block    


def insert_image_to_text_block(image, block):
    '''insert inline image to associated text block as a span'''
    assert is_text_block(block), 'text block required.'

    # get the inserting position
    image_rect = fitz.Rect(image['bbox'])
    for i,line in enumerate(block['lines']):
        if image_rect.x0 < line['bbox'][0]:
            break
    else:
        i = 0

    # Step 1: insert image as a line in block
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

    # Step 2: merge image into span in line
    _merge_lines_in_block(block)


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