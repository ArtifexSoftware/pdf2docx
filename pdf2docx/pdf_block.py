'''
`blocks` are a group of page contents. The type of blocks is extended from 
the default `text` and `image` to `list` and `table`:
    - text block: type=0
    - image block: type=1
    - list block: type=2
    - table block: type=3 (explicit) or 4 (implicit table)
'''

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


def set_explicit_table_block(block):
    block['type'] = 3


def set_implicit_table_block(block):
    block['type'] = 4


def merge_blocks(blocks):
    '''merge blocks aligned horizontally.'''
    res = []
    for block in blocks:
        # add block directly if not aligned horizontally with previous block
        if not res or not utils.is_horizontal_aligned(block['bbox'], res[-1]['bbox']):
            res.append(block)

        # otherwise, append to previous block as lines
        else:
            res[-1]['lines'].extend(block['lines'])

            # update bbox
            res[-1]['bbox'] = (
                min(res[-1]['bbox'][0], block['bbox'][0]),
                min(res[-1]['bbox'][1], block['bbox'][1]),
                max(res[-1]['bbox'][2], block['bbox'][2]),
                max(res[-1]['bbox'][3], block['bbox'][3])
                )

    return res


def merge_lines_in_block(block):
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