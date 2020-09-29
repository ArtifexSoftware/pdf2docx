# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.

@created: 2020-07-22
@author: train8808@gmail.com
---

{
    'type': int
    'bbox': (x0, y0, x1, y1),
    'rows': [
        {
            "bbox": (x0, y0, x1, y1),
            "height": float,
            "cells": [
                {
                    'bbox': (x0, y0, x1, y1),
                    'border_color': (sRGB,,,), # top, right, bottom, left
                    'bg_color': sRGB,
                    'border_width': (,,,),
                    'merged_cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
                    'blocks': [ {text blocks} ]
                }, # end of cell
                {},
                None, # merged cell
                ...
            ]
        }, # end of row
        {...} # more rows
    ] # end of row
}
'''


from .Row import Row
from .Rows import Rows
from ..common.Block import Block
from ..common import docx


class TableBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict={}):
        super().__init__(raw)

        # collect rows
        self._rows = Rows(parent=self).from_dicts(raw.get('rows', []))

        # lattice table by default
        self.set_lattice_table_block()

    def __getitem__(self, idx):
        try:
            row = self._rows[idx]
        except IndexError:
            msg = f'Row index {idx} out of range'
            raise IndexError(msg)
        else:
            return row

    def __iter__(self):
        return (row for row in self._rows)

    def __len__(self):
        return len(self._rows)

    @property
    def num_rows(self):
        return len(self._rows)

    @property
    def num_cols(self):
        return len(self._rows[0]) if self.num_rows else 0

    @property
    def text(self):
        '''Get text contained in each cell.'''
        return [ [cell.text for cell in row] for row in self._rows ]

    
    def append(self, row:Row):
        '''Append row to table and update bbox accordingly.'''
        self._rows.append(row)


    def store(self):
        res = super().store()
        res.update({
            'rows': self._rows.store()
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
        for row in self._rows:
            for cell in row:
                # ignore merged cells
                if not cell: continue            
                
                # plot different border colors for lattice / stream tables when style=False, 
                # i.e. table illustration, rather than real style of lattice table
                bc = (1,0,0) if self.is_lattice_table_block() else (0.6,0.7,0.8)
                cell.plot(page, content=content, style=style, color=bc)

    
    def parse_text_format(self, rects):
        '''Parse text format for blocks contained in each cell.
            ---
            Args:
              - rects: Shapes, format styles are represented by these rectangles.
        '''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.blocks.parse_text_format(rects)
        
        return True # always return True if table is parsed


    def parse_spacing(self):
        ''' Calculate vertical space for blocks contained in table cells.'''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.blocks.parse_spacing()


    def make_docx(self, table):
        '''Create docx table.
            ---
            Args:
              - table: docx table instance
        '''
        # set left indent
        docx.indent_table(table, self.left_space)

        # set format and contents row by row
        for idx_row in range(len(table.rows)):
            self._rows[idx_row].make_docx(table, idx_row)