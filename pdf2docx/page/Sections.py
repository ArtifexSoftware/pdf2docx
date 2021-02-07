# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Section` instances.
'''

from docx.enum.section import WD_SECTION
from ..common.Collection import BaseCollection
from .Section import Section
from ..layout.Blocks import Blocks
from ..shape.Shapes import Shapes
from .Column import Column


class Sections(BaseCollection):

    def restore(self, raws:list):
        """Restore sections from source dicts."""        
        self.reset()
        for raw in raws:
            section = Section().restore(raw)
            self.append(section)
        return self
    

    def parse(self, settings:dict):
        '''Parse sections layout.'''
        # detect section based on source blocks and shapes
        blocks, shapes = self.parent.blocks, self.parent.shapes
        self._create(blocks, shapes)

        # clear source blocks and shapes once created sections
        blocks.reset()
        shapes.reset()

        # parse layout under section level
        for section in self: section.parse(settings)        
        return self


    def make_docx(self, doc):
        '''Create sections in docx.'''
        # new page section
        if doc.paragraphs:
            doc.add_section(WD_SECTION.NEW_PAGE)

        # internal sections
        for section in self:
            section.make_docx(doc)
            # add continuous section if exists next section
            if section!=self[-1]:
                doc.add_section(WD_SECTION.CONTINUOUS)


    def plot(self, page):
        '''Plot all section blocks for debug purpose.'''
        for section in self: 
            for column in section:
                column.blocks.plot(page)   


    def _create(self, blocks:Blocks, shapes:Shapes):
        '''Detect and create page sections, especially for two-columns Section.

        ::

                         |                y0
            +------------|--------------+ span_elements
            +------------|--------------+ t1
                         |
            +----------+ | +------------+ v0
            |  column  | | |  elements  | 
            +----------+ | +------------+ v1
            u0           |             u1
            +------------|--------------+ span_elements
            +------------|--------------+ t2
                         |                y1
        '''
        def create_column(bbox, blocks, shapes):
            column = Column().update_bbox(bbox)
            column.assign_blocks(blocks)
            column.assign_shapes(shapes)
            return column
    
        # collect all blocks and shapes
        elements = BaseCollection()
        for block in blocks: elements.extend(block.lines)
        elements.extend(shapes)
        
        # filter with page center line
        x0, y0, x1, y1 = self.parent.working_bbox
        X = (x0+x1) / 2.0
        column_elements = list(filter(
                lambda e: e.bbox[2]<X or e.bbox[0]>X, elements))
        span_elements = list(filter(
                lambda e: e.bbox[2]>=X>=e.bbox[0], elements))
        
        # check: intersected elements must on the top or bottom side.
        # otherwise, one section with one column.
        u0, v0, u1, v1 = BaseCollection(column_elements).bbox
        if not all(e.bbox[3]<v0 or e.bbox[1]>v1 for e in span_elements): 
            column = create_column((x0, y0, x1, y1), blocks, shapes)
            self.append(Section(space=0, columns=[column]))
            return
        
        # Now, three sections (at most) in general: top, two-columns, bottom.
        # find the separation for each section
        def top_bottom_boundaries(elements, v0, v1, y0, y1):
            t1, t2 = y0, y1
            for e in elements:
                # move top border
                if e.bbox.y1 < v0: t1 = e.bbox.y1
                # reach first bottom border
                if e.bbox.y1 > v1:
                    t2 = e.bbox.y1
                    break
            return t1, t2

        t1, t2 = top_bottom_boundaries(elements, v0, v1, y0 ,y1)

        # top section
        if t1 > y0:
            column = create_column((x0, y0, x1, t1), blocks, shapes)
            self.append(Section(space=0, columns=[column]))
        
        # middle two-columns section
        column_1 = create_column((x0, t1, X, v1), blocks, shapes)
        column_2 = create_column((X, t1, x1, v1), blocks, shapes)
        self.append(Section(space=0, columns=[column_1, column_2]))

        # bottom section
        if t2 < y1:
            column = create_column((x0, v1, x1, t2), blocks, shapes)
            self.append(Section(space=0, columns=[column]))