# -*- coding: utf-8 -*-

'''Collection of Cell instances.
'''

from .Cell import Cell
from ..common.Collection import ElementCollection


class Cells(ElementCollection):
    '''A group of Cells.'''
    def restore(self, raws:list):
        '''Restore Cells from source dict.

        Args:
            raws (list): A list of source dict.
        '''
        for raw in raws:
            cell = Cell(raw)
            self.append(cell)
        return self
    
    def append(self, cell:Cell):
        '''Override. Append a cell (allow empty cell, i.e. merged cells) and update bbox accordingly.'''
        self._instances.append(cell)
        self._update_bbox(cell)
        cell.parent = self._parent # set parent
