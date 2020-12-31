# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.

@created: 2020-07-22

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
    '''Table block.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}
        super().__init__(raw)

        # collect rows
        self._rows = Rows(parent=self).restore(raw.get('rows', []))

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


    def plot(self, page, content:bool, style:bool, color:tuple):
        '''Plot table block, i.e. cell/line/span.
            ---
            Args:
            - page   : fitz.Page object
            - content: plot text blocks contained in cells if True
            - style  : plot cell style if True, e.g. border width, shading
            - color  : border stroke color if style=False
        '''
        for row in self._rows:
            for cell in row:                
                if not cell: continue  # ignore merged cells   
                cell.plot(page, content=content, style=style, color=color)


    def set_table_contents(self, blocks:list, settings:dict):
        '''Assign `blocks` to associated cell.'''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                # check candidate blocks
                for block in blocks: cell.add(block)

                # rearrange blocks lines
                cell.blocks.join_horizontally(text_direction=True, 
                			line_overlap_threshold=settings['line_overlap_threshold'],
                			line_merging_threshold=settings['line_merging_threshold']).split_vertically()

                # for lattice table, check cell blocks layout further
                if self.is_lattice_table_block() and \
                    cell.blocks.collect_stream_lines([], settings['float_layout_tolerance'], settings['line_separate_threshold']):
                    cell.set_stream_table_layout(settings)                


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


    def parse_spacing(self, *args):
        ''' Calculate vertical space for blocks contained in table cells.'''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.blocks.parse_spacing(*args)


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