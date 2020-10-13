# -*- coding: utf-8 -*-

'''
Parsing table blocks:
- lattice table: explicit borders represented by strokes
- stream table : borderless table recognized from layout of text blocks.

Terms definition:
- from appearance aspect, we say stroke and fill, the former looks like a line, while the later an area
- from semantic aspect, we say border (cell border) and shading (cell shading)
- an explicit border is determined by a certain stroke, while a stroke may also represent an underline of text
- an explicit shading is determined by a fill, while a fill may also represent a highlight of text
- Border object is introduced to determin borders of stream table. Border instance is a virtual border adaptive 
  in a certain range, then converted to a stroke once finalized, and finally applied to detect table border.


@created: 2020-08-16
@author: train8808@gmail.com
'''

from ..common.BBox import BBox
from ..common import constants
from ..layout.Blocks import Blocks
from ..shape.Shapes import Shapes
from .TableStructure import TableStructure
from .Border import HBorder, VBorder


class TablesConstructor(TableStructure):

    def __init__(self, parent):
        '''Object parsing TableBlock.'''
        self._parent = parent # Layout
        self._blocks = parent.blocks if parent else None # type: Blocks
        self._shapes = parent.shapes if parent else None # type: Shapes


    def lattice_tables(self):
        '''Parse table with explicit borders/shadings represented by rectangle shapes.'''
        # group stroke shapes: each group may be a potential table
        groups = self._shapes.table_borders.group_by_connectivity(dx=constants.TINY_DIST, dy=constants.TINY_DIST)

        # all filling shapes
        shadings = self._shapes.table_shadings

        # parse table with each group
        tables = Blocks()
        for group in groups:
            # get potential shadings in this table region
            group_shadings = shadings.contained_in_bbox(group.bbox)

            # parse table structure based on rects in border type
            table = self.parse_structure(group, group_shadings)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add table to page level
            table.set_lattice_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return Blocks(unique_tables)


    def stream_tables(self):
        ''' Parse table with layout of text/image blocks, and update borders with explicit borders 
            represented by rectangle shapes.
        '''
        # all explicit borders and shadings
        table_borders = self._shapes.table_borders
        table_shadings = self._shapes.table_shadings

        # lines in potential stream tables
        tables_lines = self._blocks.collect_stream_lines(table_shadings)

        # parse tables
        tables = Blocks()
        X0, Y0, X1, Y1 = self._parent.bbox
        for table_lines in tables_lines:
            # bounding box
            x0 = min([rect.bbox.x0 for rect in table_lines])
            y0 = min([rect.bbox.y0 for rect in table_lines])
            x1 = max([rect.bbox.x1 for rect in table_lines])
            y1 = max([rect.bbox.y1 for rect in table_lines])
            
            # top/bottom border margin: the block before/after table
            y0_margin, y1_margin = Y0, Y1
            for block in self._blocks:
                if block.bbox.y1 < y0:
                    y0_margin = block.bbox.y1
                if block.bbox.y0 > y1:
                    y1_margin = block.bbox.y0
                    break

            # boundary borders: to be finalized, so set a valid range
            top    = HBorder(border_range=(y0_margin, y0), reference=False)
            bottom = HBorder(border_range=(y1, y1_margin), reference=False)
            left   = VBorder(border_range=(X0, x0), reference=False)
            right  = VBorder(border_range=(x1, X1), reference=False)

            top.set_boundary_borders((left, right))
            bottom.set_boundary_borders((left, right))
            left.set_boundary_borders((top, bottom))
            right.set_boundary_borders((top, bottom))

            # explicit strokes/shadings in table region
            rect = BBox().update_bbox((X0, y0_margin, X1, y1_margin))
            explicit_strokes  = table_borders.contained_in_bbox(rect.bbox) 
            explicit_shadings = table_shadings.contained_in_bbox(rect.bbox)

            # parse stream borders based on lines in cell and explicit borders/shadings
            strokes = self.stream_strokes(table_lines, (top, bottom, left, right), explicit_strokes, explicit_shadings)
            if not strokes: continue

            # parse table structure
            strokes.sort_in_reading_order() # required
            table = self.parse_structure(strokes, explicit_shadings)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables: 
            # set type: stream table
            table.set_stream_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)        

        return Blocks(unique_tables)


    @staticmethod
    def _remove_floating_tables(tables:Blocks):
        '''Delete table has intersection with previously parsed tables.'''
        unique_tables = []
        groups = tables.group_by_connectivity(dx=constants.TINY_DIST, dy=constants.TINY_DIST)
        for group in groups:
            # single table
            if len(group)==1: table = group[0]
            
            # intersected tables: keep the table with the most cells only 
            # since no floating elements are supported with python-docx
            else:
                sorted_group = sorted(group, 
                    key=lambda table: table.num_rows*table.num_cols)
                table = sorted_group[-1]
            
            unique_tables.append(table)
        
        return unique_tables