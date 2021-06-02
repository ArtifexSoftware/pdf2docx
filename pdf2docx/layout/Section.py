# -*- coding: utf-8 -*-

'''Section of Page.

In most cases, one section per page. But in case multi-columns page, sections are used 
to distinguish these different layouts.

.. note::
    Currently, support at most two columns.

::

    {
        'bbox': (x0,y0,x1,y1)
        'num_cols': 1,
        'space': 0,
        'columns': [{
            ... # column properties
        }, ...]
    }
'''

from docx.enum.section import WD_SECTION
from ..common.docx import set_columns
from ..common.Collection import BaseCollection
from .Column import Column


class Section(BaseCollection):
    
    def __init__(self, space:int=0, columns:list=None, parent=None):
        """Initialize Section instance.

        Args:
            space (int, optional): Space between adjacent columns. Defaults to 0.
            columns (list, optional): A list of Column instances. Defaults to None.
            parent (Sections, optional): Parent element. Defaults to None.
        """
        self.space = space
        self.before_space = 0.0
        super().__init__(columns, parent)
    

    @property
    def num_cols(self): return len(self)


    def store(self):
        '''Store parsed section layout in dict format.'''
        return {
            'bbox'   : tuple([x for x in self.bbox]),
            'num_cols'   : self.num_cols,
            'space'  : self.space,
            'before_space'  : self.before_space,
            'columns': super().store()
        }
    

    def restore(self, raw:dict):
        '''Restore section from source dict.'''
        # bbox is maintained automatically based on columns
        self.space = raw.get('space', 0)   # space between adjacent columns
        self.before_space = raw.get('before_space', 0)   # space between adjacent columns

        # get each column
        for raw_col in raw.get('columns', []):
            column = Column().restore(raw_col)
            self.append(column)

        return self


    def parse(self, **settings):
        '''Parse section layout.'''
        for column in self: column.parse(**settings)        
        return self
    

    def make_docx(self, doc):
        '''Create section in docx. 

        Args:
            doc (Document): ``python-docx`` document object
        '''
        # set section column
        section = doc.sections[-1]
        width_list = [c.bbox[2]-c.bbox[0] for c in self]
        set_columns(section, width_list, self.space)

        # add create each column
        for column in self:
            # column break to start new column
            if column != self[0]: 
                doc.add_section(WD_SECTION.NEW_COLUMN)

            # make doc
            column.make_docx(doc)