# -*- coding: utf-8 -*-

'''Section of Page.

In most cases, one section per page. But in case multi-columns page, sections are used 
to distinguish these different layouts.

.. note::
    Currently, support at most two columns.

::

{
    'bbox': (x0,y0,x1,y1)
    'cols': 1,
    'space': 0,
    'columns': [{
        ... # column properties
    }, ...]
}
'''

from ..common.Element import Element
from ..common.Collection import BaseCollection
from .Column import Column


class Section(Element, BaseCollection):
    
    def __init__(self, raw:dict=None):
        raw = raw or {}
        # get bbox from raw dict, e.g. parsed result. 
        # Note no bbox provided when source dict from pdf.
        super().__init__(raw)

        self.cols  = raw.get('cols', 1) # one column by default
        self.space = raw.get('space', 0)   # space between adjacent columns

        # get each column
        BaseCollection.__init__(self)
        for raw_col in raw.get('columns', []):
            column = Column(parent=self).restore(raw_col)
            self.append(column)


    def store(self):
        '''Store parsed section layout in dict format.'''
        res = super().store()
        res.update({
            'cols'   : self.cols,
            'space'  : self.space,
            'columns': [column.store() for column in self._instances]
        })
        return res





