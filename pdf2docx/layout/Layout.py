# -*- coding: utf-8 -*-

'''
Layout objects based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---

The raw page content extracted with PyMuPDF, `page.getText('rawdict')` is described per link:
https://pymupdf.readthedocs.io/en/latest/textpage.html

In addition to the raw layout dict, some new features are also included, e.g.
    - page margin
    - rectangle shapes, for text format, annotations and table border/shading
    - new block in table type

{
    # raw dict
    ----------------------------
    "width" : w,
    "height": h,    
    "blocks": [{...}, {...}, ...],

    # introduced dict
    ----------------------------
    "margin": [left, right, top, bottom],
    "rects" : [{...}, {...}, ...]
}
'''

import json
from .Blocks import Blocks
from ..common.Block import Block
from ..common import utils
from ..shape.Rectangles import Rectangles
from ..table.TableBlock import TableBlock
from ..table.functions import set_table_borders


class Layout:
    ''' Object representing the whole page, e.g. margins, blocks, shapes, spacing.'''

    def __init__(self, raw: dict) -> None:
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.blocks = Blocks(raw.get('blocks', []))

        # introduced attributes
        self._margin = None
        self.rects = Rectangles()


    def store(self) -> dict:
        return {
            'width': self.width,
            'height': self.height,
            'margin': self._margin,
            'blocks': self.blocks.store(),
            'rects': self.rects.store(),
        }


    def serialize(self, filename:str):
        '''Write layout to specified file.'''
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.store(), indent=4))


    def plot(self, doc, title:str, key:str='layout'):
        '''Plot specified type of blocks layout with PyMuPDF.
            ---
            Args:
              - doc: fitz.Document object
        '''
        # get objects to plot
        #  - all blocks
        if key == 'layout': 
            objects = list(self.blocks)
        
        #  - explicit table structure only
        elif key == 'table': 
            objects = list(filter(
                lambda block: block.is_explicit_table_block(), self.blocks
            ))
        
        #  - implicit table structure only
        elif key == 'implicit_table': 
            objects = list(filter(
                lambda block: block.is_implicit_table_block(), self.blocks
            ))
        
        #  - rectangle shapes
        elif key == 'shape': 
            objects = list(self.rects)

        else:
            objects = []

        # do nothing if no objects
        if not objects: return

        # insert a new page
        page = utils.new_page_with_margin(doc, self.width, self.height, self.margin, title)

        # plot styled table but no text blocks in cell
        if key=='table': 
            for item in objects:
                item.plot(page, style=True, content=False)
        
        # plot non-styled table and no text blocks in cell
        elif key=='implicit_table': 
            for item in objects:
                item.plot(page, style=False, content=False)
        
        else:
            for item in objects:
                item.plot(page) # default args for TableBlock.plot


    @property
    def margin(self):
        return self._margin


    def parse(self, **kwargs):
        ''' Parse page layout.
            ---
            Args:
              - kwargs: dict for layout plotting
                    kwargs = {
                        'debug': bool,
                        'doc': fitz.Document object or None,
                        'filename': str
                    }
        '''

        # preprocessing, e.g. change block order, clean negative block
        self.blocks.preprocessing(**kwargs)

        # calculate page margin based on preprocessed layout
        self.page_margin()
    
        # parse table blocks: 
        #  - table structure/format recognized from rectangles    
        self.rects.clean(**kwargs) # clean rects
        self.parse_table_structure_from_rects(**kwargs)    
        parse_table_content(layout, **kwargs) # cell contents
        
        #  - cell contents extracted from text blocks
        parse_table_structure_from_blocks(layout, **kwargs)    
        parse_table_content(layout, **kwargs) # cell contents

        # parse text format, e.g. highlight, underline
        parse_text_format(layout, **kwargs)
        
        # paragraph / line spacing
        self.parse_vertical_spacing()



    @utils.debug_plot('Explicit Table Structure', plot=True, category='table')
    def parse_table_structure_from_rects(self, **kwargs) -> bool:
        '''parse table structure from rectangle shapes'''
        # group rects: each group may be a potential table
        groups = self.rects.group()

        # check each group
        tables = [] # type: list[TableBlock]
        for group in groups:
            # skip if not a table group
            if not set_table_borders(group):
                continue

            # parse table structure based on rects in border type
            table = TableBlock()
            table.parse_structure(group)
            if table: 
                table.set_explicit_table_block()
                tables.append(table)
            # reset border type if parse table failed
            else:
                for rect in group:
                    rect['type'] = -1

        # add parsed table structure to blocks list
        if tables:
            self.blocks.extend(tables)
            return True
        else:
            return False


    @utils.debug_plot('Parsed Table', plot=False, category='layout')
    def parse_table_content(self, **kwargs) -> bool:
        '''Add block lines to associated cells.'''

        # table blocks
        table_found = False
        tables = list(filter(lambda block: block.is_table_block(), self.blocks))
        if not tables: return table_found

        # collect blocks in table region
        blocks = []   # type: list[Block]
        blocks_in_tables = [[] for _ in tables] # type: list[list[Block]]
        for block in self.blocks:
            # ignore table block
            if block.is_table_block(): continue

            # collect blocks contained in table region
            for table, blocks_in_table in zip(tables, blocks_in_tables):
                if table.bbox.intersects(block.bbox):
                    blocks_in_table.append(block)
                    break
            # normal blocks
            else:
                blocks.append(block)

        # assign blocks to associated cells
        # ATTENTION: no nested table is considered
        for table, blocks_in_table in zip(tables, blocks_in_tables):
            for row in table.cells:
                for cell in row:
                    if not cell: continue

                    # check candidate blocks
                    blocks_in_cell = []
                    fitz_cell = fitz.Rect(cell['bbox'])
                    for block in blocks_in_table:
                        cell_block = _assign_block_to_cell(block, fitz_cell)
                        if cell_block:
                            blocks_in_cell.append(cell_block)

                    # merge blocks if contained blocks found
                    if blocks_in_cell: 
                        cell_blocks = merge_blocks(blocks_in_cell)
                        cell['blocks'].extend(cell_blocks)
                        table_found = True

        # sort in natural reading order and update layout blocks
        blocks.extend(tables)
        blocks.sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
        self.blocks = blocks

        return table_found


    def parse_vertical_spacing(self):
        ''' Calculate external and internal vertical space for paragraph blocks under page context 
            or table context. It'll used as paragraph spacing and line spacing when creating paragraph.
        '''
        # blocks in page level
        top, bottom = self.margin[-2:]
        self.blocks.parse_vertical_spacing(top, self.height-bottom)

        # blocks in table cell level
        tables = list(filter(lambda block: block.is_table_block(), self.blocks))
        for table in tables:
            for row in table.cells:
                for cell in row:
                    if not cell: continue
                    _, y0, _, y1 = cell.bbox_raw
                    w_top, _, w_bottom, _ = cell.border_width
                    cell.blocks.parse_vertical_spacing(y0+w_top/2.0, y1-w_bottom/2.0)


    def page_margin(self):
        '''Calculate page margin:
            - left: MIN(bbox[0])
            - right: MIN(left, width-max(bbox[2]))
            - top: MIN(bbox[1])
            - bottom: height-MAX(bbox[3])
        '''
        # return normal page margin if no blocks exist
        if not self.blocks:
            self._margin = (utils.ITP, ) * 4 # 1 Inch = 72 pt
            return

        # check candidates for left margin:
        list_bbox = list(map(lambda x: x.bbox, self.blocks))

        # left margin 
        left = min(map(lambda x: x.x0, list_bbox))

        # right margin
        x_max = max(map(lambda x: x.x1, list_bbox))
        right = self.width-x_max-utils.DM*2.0 # consider tolerance: leave more free space
        right = min(right, left)     # symmetry margin if necessary
        right = max(right, 0.0)      # avoid negative margin

        # top/bottom margin
        top = min(map(lambda x: x.y0, list_bbox))
        bottom = self.height-max(map(lambda x: x.y1, list_bbox))
        bottom = max(bottom, 0.0)

        # reduce calculated bottom margin -> more free space left,
        # to avoid page content exceeding current page
        bottom *= 0.5

        # use normal margin if calculated margin is large enough
        self._margin = (
            min(utils.ITP, left), 
            min(utils.ITP, right), 
            min(utils.ITP, top), 
            min(utils.ITP, bottom)
            )