# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Section` instances.
'''

from docx.enum.section import WD_SECTION
from ..common.Collection import Collection, BaseCollection
from ..common.Block import Block
from ..layout.Blocks import Blocks
from ..shape.Shapes import Shapes
from ..shape.Shape import Shape
from .Section import Section
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
        self._parse(blocks, shapes)

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
    

    def _parse(self, blocks:Blocks, shapes:Shapes):
        '''Detect and create page sections based on initial layout extracted from ``PyMuPDF``.

        Args:
            blocks (Blocks): source blocks after cleaning up.
            shapes (SHapes): source shapes after cleaning up.

        .. note::
            Consider two-columns Section only.
        '''
        # bbox
        X0, _, X1, _ = self.parent.working_bbox        
    
        # collect all blocks and shapes
        elements = Collection()
        elements.extend(blocks)
        elements.extend(shapes)
        
        # check section row by row
        pre_section = Collection()
        pre_num_col = 1
        for row in elements.group_by_rows():
            # check column col by col
            cols = row.group_by_columns()
            current_num_col = len(cols)

            # consider 2-cols only
            if current_num_col>2: current_num_col = 1 

            # further check 2-cols -> the height
            x0, y0, x1, y1 = pre_section.bbox
            if pre_num_col==2 and current_num_col==1 and y1-y0<20:
                pre_num_col = 1

            # TODO:
            # 1. pre_num_col==2 and current_num_col==1, but current row in the left side
            # 2. pre_num_col==2 and current_num_col==2, but not aligned

            # finalize pre-section if different to current section
            if current_num_col!=pre_num_col:
                # create pre-section
                self._create_section(pre_num_col, pre_section, (X0, X1))

                # start new section                
                pre_section = Collection(row)
                pre_num_col = current_num_col

            # otherwise, append to pre-section
            else:
                pre_section.extend(row)

        # the final section
        self._create_section(current_num_col, pre_section, (X0, X1))


    @staticmethod
    def _create_column(bbox, elements:Collection):
        '''Create column based on bbox and candidate elements: blocks and shapes.'''
        if not bbox: return None
        column = Column().update_bbox(bbox)
        blocks = [e for e in elements if isinstance(e, Block)]
        shapes = [e for e in elements if isinstance(e, Shape)]
        column.assign_blocks(blocks)
        column.assign_shapes(shapes)
        return column


    def _create_section(self, num_col:int, elements:Collection, h_range:tuple):
        '''Create section based on column count, candidate elements and horizontal boundary.'''
        if not elements: return
        X0, X1 = h_range
        x0, y0, x1, y1 = elements.bbox

        if num_col==1:
            column = self._create_column((X0, y0, X1, y1), elements)
            self.append(Section(space=0, columns=[column]))
        else:
            cols = elements.group_by_columns()
            *_, u1, _ = cols[0].bbox
            u0, *_ = cols[1].bbox
            u = (u0+u1)/2.0
            column_1 = self._create_column((X0, y0, u, y1), elements)
            column_2 = self._create_column((u, y0, X1, y1), elements)
            self.append(Section(space=0, columns=[column_1, column_2]))
                