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

from ..common.Collection import Collection
from ..layout.Layout import Layout
from ..shape.Shape import Shape
from ..text.Line import Line


class Column(Layout):
    '''Column of Section.'''

    @property
    def working_bbox(self): return self.bbox


    def add_elements(self, elements:Collection):
        '''Add candidate elements, i.e. lines or shapes, to current column.'''
        blocks = [e for e in elements if isinstance(e, Line)]
        shapes = [e for e in elements if isinstance(e, Shape)]
        self.assign_blocks(blocks)
        self.assign_shapes(shapes)


    def make_docx(self, doc):
        '''Create Section Column in docx.

        Args:
            doc (Document): ``python-docx`` document object
        '''
        self.blocks.make_docx(doc)
