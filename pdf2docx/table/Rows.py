# -*- coding: utf-8 -*-

'''
A group of Rows objects in a table.

@created: 2020-08-15
@author: train8808@gmail.com
'''

from .Row import Row
from ..common.Collection import Collection


class Rows(Collection):
    '''A group of Rows.'''

    def from_dicts(self, raws:list):
        for raw in raws:
            row = Row(raw)
            self.append(row)
        return self
