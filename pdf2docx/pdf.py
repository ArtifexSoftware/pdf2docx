'''
Recognize content and format from PDF file with PyMuPDF
@created: 2019-06-24
@author: train8808@gmail.com
---

The raw page content extracted with with PyMuPDF, especially in JSON 
format is described per link:
https://pymupdf.readthedocs.io/en/latest/textpage.html

The parsed results of this module is similar to the raw layout dict, 
but with some new features added, e.g.
 - add rectangle shapes (for text format, annotations)
 - add page margin
 - regroup lines in adjacent blocks considering context
 - recognize list format: block.type=2
 - recognize table format: block.type=3

An example of processed layout result:
    {
    "width" : 504.0,
    "height": 661.5,
    "margin": [20.4000, 574.9200, 37.5600, 806.4000], # left, right, top, bottom
    "blocks": [{...}, {...}, ...],
    "rects" : [{...}, {...}, ...]
    }

where:

`rects` are a list of rectangle shapes extracted from PDF xref_stream and
annotations:
    {
        'bbox' : [float,float,float,float], 
        'color': int,
        'type' : int or None
    }

`blocks` are a group of page contents. The type of blocks is extended from 
the default `text` and `image` to `list` and `table`:

- text block: type=0
- image block: type=1
- list block: type=2
- table block: type=3 (explicit) or 4 (implicit table)

Note: The length unit for each boundary box is pt, which is 1/72 Inch.

'''

import fitz
from .pdf_debug import debug_plot
from .pdf_table import (parse_explicit_table, parse_implicit_table)
from .pdf_text import merge_inline_images, parse_text_format
from .pdf_block import (is_text_block, is_image_block, is_table_block, is_explicit_table_block, block_text, remove_floating_blocks)
from . import utils


def layout(layout, **kwargs):
    ''' processed page layout:
            - split block with multi-lines into seperated blocks
            - merge blocks vertically to complete sentence
            - merge blocks horizontally for convenience of docx generation

        args:
            layout: raw layout data extracted from PDF with `getText('rawdict')`,
                and with rectangles included.            

            kwargs: dict for layout plotting
                kwargs = {
                    'debug': bool,
                    'doc': fitz document or None,
                    'filename': str
                }
    '''

    # preprocessing, e.g. change block order, clean negative block, 
    # get span text by joining chars
    preprocessing(layout, **kwargs)

    # calculate page margin based on preprocessed layout
    page_margin(layout)
   
    # parse table blocks: 
    #  - table structure/format recognized from rectangles    
    parse_explicit_table(layout, **kwargs)
    
    #  - cell contents extracted from text blocks
    parse_implicit_table(layout, **kwargs)

    # parse text format, e.g. highlight, underline
    parse_text_format(layout, **kwargs)
    
    # paragraph / line spacing
    parse_vertical_spacing(layout)


def extract_tables(layout):
    ''' extract content from explicit table.'''
    # parsing explicit table
    preprocessing(layout)
    parse_explicit_table(layout)

    # check table
    tables = []
    for table_block in filter(lambda block: is_explicit_table_block(block), layout['blocks']):
        table = []
        # check each row
        for row_block in table_block['cells']:
            row = []
            # check each cell
            for cell_block in row_block:
                if cell_block:
                    cell = '\n'.join([block_text(block) for block in cell_block['blocks']])
                else:
                    cell = None
    
                # add cell to row
                row.append(cell)
            
            # add row to table
            table.append(row)

        # add to tables
        tables.append(table)

    return tables                    


@debug_plot('Preprocessing', plot=False)
def preprocessing(layout, **kwargs):
    '''preprocessing for the raw layout of PDF page'''

    # remove negative blocks
    blocks = list(filter(
        lambda block: all(x>0 for x in block['bbox']), layout['blocks']))

    # remove blocks with transformed text: text direction is not (1, 0)
    blocks = list(filter(
        lambda block: 'lines' not in block or all(line['dir'][0]==1.0 for line in block['lines']), layout['blocks']))

    # remove overlap blocks: no floating elements are supported
    blocks = remove_floating_blocks(blocks)
    
    # joining chars in text span
    for block in blocks:
        # skip image
        if is_image_block(block): continue

        # join chars: apply on original text block only
        for line in block['lines']:
            for span in line['spans']:
                chars = [char['c'] for char in span['chars']]
                span['text'] = ''.join(chars)
    
    # sort in reading direction: from up to down, from left to right
    blocks.sort(
        key=lambda block: (block['bbox'][1], block['bbox'][0]))
        
    # merge inline images into text block
    merge_inline_images(blocks)
    
    layout['blocks'] = blocks

    # round bbox of rectangles: one decimal place is enough, 
    # otherwise, probally to encounter float error, especially get intersection of two bbox-es
    for rect in layout['rects']:
        rect['bbox'] = tuple([round(x,1) for x in rect['bbox']])    

    return True


def parse_vertical_spacing(layout):
    ''' Calculate external and internal vertical space for paragraph blocks under page context 
        or table context. It'll used as paragraph spacing and line spacing when creating paragraph.
    '''
    # blocks in page level
    top, bottom = layout['margin'][-2:]
    _parse_paragraph_and_line_spacing(layout['blocks'], top, layout['height']-bottom)

    # blocks in table cell level
    tables = list(filter(lambda block: is_table_block(block), layout['blocks']))
    for table in tables:
        for row in table['cells']:
            for cell in row:
                if not cell: continue
                _, y0, _, y1 = cell['bbox']
                w_top, _, w_bottom, _ = cell['border-width']
                _parse_paragraph_and_line_spacing(cell['blocks'], y0+w_top/2.0, y1-w_bottom/2.0)


def page_margin(layout):
    '''get page margin:
       - left: MIN(bbox[0])
       - right: MIN(left, width-max(bbox[2]))
       - top: MIN(bbox[1])
       - bottom: height-MAX(bbox[3])
    '''
    # return normal page margin if no blocks exist
    if not layout['blocks']:
        layout['margin'] = (utils.ITP, ) * 4 # 1 Inch = 72 pt
        return

    # check candidates for left margin:
    list_bbox = list(map(lambda x: x['bbox'], layout['blocks']))

    # left margin 
    left = min(map(lambda x: x[0], list_bbox))

    # right margin
    x_max = max(map(lambda x: x[2], list_bbox))
    w, h = layout['width'], layout['height']
    right = w-x_max-utils.DM*2.0 # consider tolerance: leave more free space
    right = min(right, left)     # symmetry margin if necessary
    right = max(right, 0.0)      # avoid negative margin

    # top/bottom margin
    top = min(map(lambda x: x[1], list_bbox))
    bottom = h-max(map(lambda x: x[3], list_bbox))
    bottom = max(bottom, 0.0)

    # reduce calculated bottom margin -> more free space left,
    # to avoid page content exceeding current page
    bottom *= 0.5

    # use normal margin if calculated margin is large enough
    layout['margin'] = (
        min(utils.ITP, left), 
        min(utils.ITP, right), 
        min(utils.ITP, top), 
        min(utils.ITP, bottom)
        )


def _parse_paragraph_and_line_spacing(blocks, Y0, Y1):
    ''' Calculate external and internal vertical space for text blocks.
     
        - paragraph spacing is determined by the vertical distance to previous block. 
          For the first block, the reference position is top margin.
        
            It's easy to set before-space or after-space for a paragraph with python-docx,
            so, if current block is a paragraph, set before-space for it; if current block 
            is not a paragraph, e.g. a table, set after-space for previous block (generally, 
            previous block should be a paragraph).
        
        - line spacing is defined as the average line height in current block.

        ---
        Args:
            - blocks: a list of block within a page/table cell
            - Y0, Y1: the blocks are restricted in a vertical range within (Y0, Y1)
    '''
    if not blocks: return

    ref_block = blocks[0]
    ref_pos = Y0
    for block in blocks:

        dw = 0.0

        # NOTE: the table bbox is counted on center-line of outer borders, so a half of top border
        # size should be excluded from the calculated vertical spacing
        if is_table_block(block) and block['cells'][0][0]:
            dw = block['cells'][0][0]['border-width'][0] / 2.0 # use top border of the first cell

        start_pos = block['bbox'][1] - dw
        para_space = start_pos - ref_pos

        # ref to current (paragraph): set before-space for paragraph
        if is_text_block(block):

            # spacing before this paragraph
            block['before_space'] = para_space

            # calculate average line spacing in paragraph
            # e.g. line-space-line-space-line, excepting first line -> space-line-space-line,
            # so an average line height = space+line
            # then, the height of first line can be adjusted by updating paragraph before-spacing.
            # 
            ref_bbox = None
            count = 0
            for line in block['lines']:
                # count of lines
                if not utils.in_same_row(line['bbox'], ref_bbox):
                    count += 1
                # update reference line
                ref_bbox = line['bbox']            
            
            _, y0, _, y1 = block['lines'][0]['bbox']   # first line
            first_line_height = y1 - y0
            block_height = block['bbox'][3]-block['bbox'][1]
            if count > 1:
                line_space = (block_height-first_line_height)/(count-1)
            else:
                line_space = block_height
            block['line_space'] = line_space

            # if only one line exists, don't have to set line spacing, use default setting,
            # i.e. single line instead
            if count > 1:
                # since the line height setting in docx may affect the original bbox in pdf, 
                # it's necessary to update the before spacing:
                # taking bottom left corner of first line as the reference point                
                para_space = para_space + first_line_height - line_space
                block['before_space'] = para_space

            # adjust last block to avoid exceeding current page <- seems of no use
            free_space = Y1-(ref_pos+para_space+block_height) 
            if free_space<=0:
                block['before_space'] = para_space+free_space-utils.DM*2.0

        # if ref to current (image): set before-space for paragraph
        elif is_image_block(block):
            block['before_space'] = para_space

        # ref (paragraph/image) to current: set after-space for ref paragraph        
        elif is_text_block(ref_block) or is_image_block(ref_block):
            ref_block['after_space'] = para_space

        # situation with very low probability, e.g. table to table
        else:
            pass

        # update reference block        
        ref_block = block
        ref_pos = block['bbox'][3] + dw
