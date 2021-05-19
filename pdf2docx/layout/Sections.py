# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.layout.Section` instances.
'''

from docx.enum.section import WD_SECTION
from docx.shared import Pt
from ..common.Collection import BaseCollection
from ..common.docx import reset_paragraph_format
from .Section import Section


class Sections(BaseCollection):

    def restore(self, raws:list):
        """Restore sections from source dicts."""        
        self.reset()
        for raw in raws:
            section = Section().restore(raw)
            self.append(section)
        return self
    

    def parse(self, settings:dict):
        '''Parse layout under section level.'''
        for section in self:
            section.parse(settings)        
        return self


    def make_docx(self, doc):
        '''Create sections in docx.'''
        # -----------------
        # new page
        # -----------------
        if doc.paragraphs:
            doc.add_section(WD_SECTION.NEW_PAGE)

        # -----------------
        # first section
        # -----------------
        # vertical position
        p = doc.add_paragraph()
        line_height = min(self[0].before_space, 11)
        pf = reset_paragraph_format(p, line_spacing=Pt(line_height))
        pf.space_after = Pt(self[0].before_space-line_height)
        if self[0].cols==2: 
            doc.add_section(WD_SECTION.CONTINUOUS)
        
        # create first section
        self[0].make_docx(doc)        

        # -----------------
        # more sections
        # -----------------
        for section in self[1:]:
            # create new section symbol
            doc.add_section(WD_SECTION.CONTINUOUS)

            # set after space of last paragraph to define the vertical
            # position of current section
            p = doc.paragraphs[-2] # -1 is the section break
            pf = p.paragraph_format
            pf.space_after = Pt(section.before_space)
            
            # section content
            section.make_docx(doc)


    def plot(self, page):
        '''Plot all section blocks for debug purpose.'''
        for section in self: 
            for column in section:
                column.blocks.plot(page)