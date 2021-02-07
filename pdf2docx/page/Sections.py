# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Section` instances.
'''

from ..common import constants
from ..common.Collection import BaseCollection, Collection
from .Section import Section
from ..layout.Blocks import Blocks
from ..shape.Shapes import Shapes


class Sections(BaseCollection):

    def restore(self, raws:list):
        """Clean current instances and restore them from source dicts."""        
        self.reset()
        for raw in raws: self.append(Section(raw))
        return self
    

    def parse(self, settings:dict):
        '''Parse section layout.'''
        # detect section based on source blocks and shapes
        blocks, shapes = self.parent.blocks, self.parent.shapes
        self._create(blocks, shapes)

        # clear source blocks and shapes once finish parsing section
        blocks.reset()
        shapes.reset() 

        # parse layout under section level
        for section in self._instances:
            section.parse(settings)
        
        return self    


    def _create(self, blocks:Blocks, shapes:Shapes):
        '''Detect and create page section, especially for two-columns Section.

        ::

            +------------|--------------+ span_elements
            +------------|--------------+
                         |
            +----------+ | +------------+ v0
            |  column  | | |  elements  | 
            +----------+ | +------------+ v1
            u0           |             u1
            +------------|--------------+ 
            +------------|--------------+ span_elements
                         |
        '''
        # collect all lines and shapes
        elements = BaseCollection()
        for block in blocks: elements.extend(block.lines)
        for shape in shapes: elements.append(shape)
        
        # filter with page center line
        x0, y0, x1, y1 = self.parent.bbox
        X = (x0+x1) / 2.0
        column_elements = list(filter(
                lambda line: line.bbox[2]<X or line.bbox[0]>X, elements))
        span_elements = filter(
                lambda line: line.bbox[2]>=X>=line.bbox[0], elements)
        
        # check: intersected elements must on the top or bottom side
        u0, v0, u1, v1 = Collection(column_elements).bbox
        if not all(e.bbox[3]<v0 or e.bbox[1]>v1 for e in span_elements): return

        # create dummy strokes for table parsing        
        m0, m1 = (x0+u0)/2.0, (x1+u1)/2.0
        n0, n1 = v0-constants.MAJOR_DIST, v1+constants.MAJOR_DIST        
        strokes = [
            Stroke().update_bbox((m0, n0, m1, n0)), # top
            Stroke().update_bbox((m0, n1, m1, n1)), # bottom
            Stroke().update_bbox((m0, n0, m0, n1)), # left
            Stroke().update_bbox((m1, n0, m1, n1)), # right
            Stroke().update_bbox((X , n0, X,  n1))]   # center
        
        # parse table structure
        table = TableStructure(strokes).parse([]).to_table_block()
        tables = []
        if table:
            table.set_stream_table_block()
            tables.append(table)

        # assign blocks/shapes to each table
        self._blocks.assign_to_tables(tables)
        self._shapes.assign_to_tables(tables)




