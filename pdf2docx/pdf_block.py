'''
`blocks` are a group of page contents. The type of blocks is extended from 
the default `text` and `image` to `list` and `table`:
    - text block: type=0
    - image block: type=1
    - list block: type=2
    - table block: type=3 (explicit) or 4 (implicit table)
'''

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