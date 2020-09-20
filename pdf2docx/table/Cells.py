# -*- coding: utf-8 -*-

'''
Collection of Cell instances.

@created: 2020-08-15
@author: train8808@gmail.com
'''

from .Cell import Cell
from ..common.Collection import Collection


class Cells(Collection):
    '''A group of Cells.'''
    def from_dicts(self, raws:list):
        for raw in raws:
            cell = Cell(raw)
            self.append(cell)
        return self
    
    def append(self, cell:Cell):
        '''Override. Append a cell (allow empty cell, i.e. merged cells) and update bbox accordingly.'''
        self._instances.append(cell)
        self._update(cell)
