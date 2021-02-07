# -*- coding: utf-8 -*-

'''Column of Section.

In most cases, one section per page. But in case multi-columns page, sections are used 
to distinguish these different layouts.

.. note::
    Currently, support at most two columns.

::

{
    'bbox': (x0, y0, x1, y1),
    'blocks': [{
        ... # block instances
    }, ...],
    'shapes': [{
        ... # shape instances
    }, ...]
}
'''

from ..common.Element import Element
from ..layout.Layout import Layout


class Column(Element, Layout):

    def __init__(self, parent=None):
        '''Initialize empty column.'''
        # Call the first parent class constructor only if omitting constructor. 
        # Unified constructor should be used (with *args, **kwargs) if using super().__init__().
        Element.__init__(self, parent=parent)
        Layout.__init__(self, blocks=None, shapes=None) # init empty layout


    @property
    def working_bbox(self): return self.bbox # accommodate Cell api


    def store(self):
        '''Store parsed section layout in dict format.'''
        res = Element.store(self)
        res.update({
            Layout.store(self)
        })
        return res





