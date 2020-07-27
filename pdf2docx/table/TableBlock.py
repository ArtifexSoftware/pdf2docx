# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.

@created: 2020-07-22
@author: train8808@gmail.com
---

{
    'type': int
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border_color': (sRGB,,,), # top, right, bottom, left
            'bg_color': sRGB,
            'border_width': (,,,),
            'merged_cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'blocks': [
                text blocks
            ]
        }, # end of cell

        None,  # merged cell

        ...,   # more cells
    ], # end of row

    ...] # more rows    
}

'''

from .Cell import Cell
from ..common.Block import Block
from ..common import docx



class TableBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(TableBlock, self).__init__(raw)

        self.cells = [] # type: list[list[Cell]]
        for row in raw.get('cells', []):            
            row_obj = [Cell(cell) for cell in row] # type: list [Cell]
            self.cells.append(row_obj)

        # explicit table by default
        self.set_explicit_table_block()

    @property
    def num_rows(self):
        return len(self.cells)

    @property
    def num_cols(self):
        return len(self.cells[0]) if self.num_rows else 0

    @property
    def text(self) -> list:
        '''Get text contained in each cell.'''
        return [ [cell.text for cell in row] for row in self.cells ]

    
    def append_row(self, row:list):
        '''Append row to table and update bbox accordingly.
            ---
            Args:
              - row: list[Cell], a list of cells
        '''
        self.cells.append(row)
        for cell in row:
            self.union(cell.bbox)


    def store(self) -> dict:
        res = super().store()
        res.update({
            'cells': [ [cell.store() for cell in row] for row in self.cells]
        })
        return res


    def plot(self, page, content=True, style=False):
        '''Plot table block, i.e. cell/line/span.
            ---
            Args:
              - page: fitz.Page object
              - style: plot cell style if True, e.g. border width, shading
              - content: plot text blocks if True
        '''
        for row in self.cells:
            for cell in row:
                # ignore merged cells
                if not cell: continue            
                
                # plot different border colors for explicit / implicit tables when style=False, 
                # i.e. table illustration, rather than real style of explicit table
                bc = (1,0,0) if self.is_explicit_table_block() else (0.6,0.7,0.8)
                cell.plot(page, content=content, style=style, color=bc)

    
    def parse_text_format(self, rects) -> bool:
        '''Parse text format for blocks contained in each cell.
            ---
            Args:
              - rects: Rectangles, format styles are represented by these rectangles.
        '''
        for row in self.cells:
            for cell in row:
                if not cell: continue
                cell.blocks.parse_text_format(rects)
        
        return True # always return True if table is parsed


    def parse_vertical_spacing(self):
        ''' Calculate vertical space for blocks contained in table cells.'''
        for row in self.cells:
            for cell in row:
                if not cell: continue
                y0 = cell.bbox.y0
                w_top = cell.border_width[0]
                cell.blocks.parse_vertical_spacing(y0+w_top/2.0)


    def make_docx(self, table, page_margin:tuple):
        '''Create docx table.
            ---
            Args:
              - table: docx table instance
              - page_margin: page margin (left, right, top, bottom)
        '''
        # set indent
        left, *_ = page_margin
        pos = self.bbox.x0-left
        docx.indent_table(table, pos)

        # cell format and contents
        border_style = self.is_explicit_table_block() # set border style for explicit table only
        for i in range(len(table.rows)):
            for j in range(len(table.columns)):           

                # ignore merged cells
                block_cell = self.cells[i][j] # type: Cell
                if not block_cell: continue
                
                # set cell style
                # no borders for implicit table
                block_cell.set_style(table, (i,j), border_style)

                # clear cell margin
                # NOTE: the start position of a table is based on text in cell, rather than left border of table. 
                # They're almost aligned if left-margin of cell is zero.
                cell = table.cell(i, j)
                docx.set_cell_margins(cell, start=0, end=0)

                # insert text            
                first = True
                x0, _, x1, _ = block_cell.bbox_raw
                for block in block_cell.blocks:
                    if first:
                        p = cell.paragraphs[0]
                        first = False
                    else:
                        p = cell.add_paragraph()
                    block.make_docx(p, x0)
