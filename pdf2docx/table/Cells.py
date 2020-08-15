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
        '''Append a cell and update bbox accordingly.
            Rewrite method of parent class, since allow empty cells, i.e. merged cells, being added.
        '''
        self._instances.append(cell)
        if not self._parent is None: # Note: `if self._parent` does not work here
            self._parent.union(cell)

