# -*- coding: utf-8 -*-

'''Table block object parsed from raw image and text blocks.

Data Structure::

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
        '''Count of rows.'''
        return len(self._rows)

    @property
    def num_cols(self):
        '''Count of columns.'''
        return len(self._rows[0]) if self.num_rows else 0

    @property
    def text(self):
        '''Get text contained in each cell.

        Returns:
            list: 2D-list with each element representing text in cell.
        '''
        return [ [cell.text for cell in row] for row in self._rows ]

    
    def append(self, row:Row):
        '''Append row to table and update bbox accordingly.

        Args:
            row (Row): Target row to add.
        '''
        self._rows.append(row)


    def store(self):
        res = super().store()
        res.update({
            'rows': self._rows.store()
        })
        return res


    def assign_blocks(self, blocks:list):
        '''Assign ``blocks`` to associated cell.

        Args:
            blocks (list): A list of text/table blocks.
        '''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.assign_blocks(blocks)


    def assign_shapes(self, shapes:list):
        '''Assign ``shapes`` to associated cell.

        Args:
            shapes (list): A list of Shape.
        '''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.assign_shapes(shapes)


    def parse(self, settings:dict):
        '''Parse layout under cell level.

        Args:
            settings (dict): Layout parsing parameters.
        '''
        for row in self._rows:
            for cell in row:
                if not cell: continue
                cell.layout.parse(settings)


    def plot(self, page):
        '''Plot table block, i.e. cell/line/span, for debug purpose.
        
        Args:
            page (fitz.Page): pdf page.
            content (bool): Plot text blocks contained in cells if True.
            style (bool): Plot cell style if True, e.g. border width, shading.
            color (bool): Plot border stroke color if ``style=False``.
        '''
        for row in self._rows:
            for cell in row:                
                if not cell: continue  # ignore merged cells   
                cell.plot(page)


    def make_docx(self, table):
        '''Create docx table.
        
        Args:
            table (Table): ``python-docx`` table instance.
        '''
        # set left indent
        docx.indent_table(table, self.left_space)

        # set format and contents row by row
        for idx_row in range(len(table.rows)):
            self._rows[idx_row].make_docx(table, idx_row)