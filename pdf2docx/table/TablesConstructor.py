# -*- coding: utf-8 -*-

'''
Parsing table blocks:
- lattice table: explicit borders represented by rectangles
- stream table : borderless table recognized from layout of text blocks.

@created: 2020-08-16
@author: train8808@gmail.com
'''


from ..common.BBox import BBox
from ..common.base import RectType
from ..common.constants import DR
from ..layout.Blocks import Blocks
from ..shape.Shape import Fill
from ..shape.Shapes import Shapes
from ..text.Lines import Lines
from .TableStructure import TableStructure
from .Border import HBorder, VBorder


class TablesConstructor(TableStructure):

    def __init__(self, blocks:Blocks, shapes:Shapes):
        '''Object parsing TableBlock.'''
        self._blocks = blocks
        self._shapes = shapes


    def lattice_tables(self):
        '''Parse table with explicit borders/shadings represented by rectangle shapes.'''
        # group stroke shapes: each group may be a potential table
        groups = self._shapes.strokes.group_by_connectivity(dx=0.5, dy=0.5)

        # all filling shapes
        shadings = self._shapes.fillings

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

        return unique_tables


    def stream_tables(self):
        ''' Parse table with layout of text/image blocks, and update borders with explicit borders 
            represented by rectangle shapes.
        '''
        x0, _, x1, _ = self._blocks.parent.bbox

        # stream tables determined by outer borders
        tables = self.stream_tables_from_outer_borders()

        # stream tables from layout
        tables_ = self.stream_tables_from_layout(x0, x1)
        tables.extend(tables_)

        # set type: stream table
        for table in tables: table.set_stream_table_block()

        return tables


    def stream_tables_from_outer_borders(self):
        ''' Parse table where the main structure is determined by outer borders extracted from shading rects.            
            This table is generally to simulate the shading shape in docx. 
        '''
        shading_rects = self._shading_shapes()

        # table based on each shading rect
        tables = Blocks()
        for rect in shading_rects:
            # boundary borders: finalized by shading edge
            x0, y0, x1, y1 = rect.bbox
            top = HBorder().finalize(y0)
            bottom = HBorder().finalize(y1)
            left = VBorder().finalize(x0)
            right = VBorder().finalize(x1)

            top.set_boundary_borders((left, right))
            bottom.set_boundary_borders((left, right))
            left.set_boundary_borders((top, bottom))
            right.set_boundary_borders((top, bottom))

            # lines contained in shading rect
            table_lines = Lines()
            for block in self._blocks:
                if rect.bbox.contains(block.bbox):
                    table_lines.extend(block.lines)
            
            # parsing stream table
            table = self._stream_table(table_lines, rect, (top, bottom, left, right))
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)        

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return unique_tables


    def stream_tables_from_layout(self, X0:float, X1:float):
        ''' Parse table where the main structure is determined by layout of text/image blocks.
            ---
            Args:
            - X0, X1: left and right boundaries of allowed table region

            Since no cell borders exist in this case, there may be various probabilities of table structures. 
            Among which, we use the simplest one, i.e. 1-row and n-column, to make the docx look like pdf.
        '''
        if not self._blocks: return []

        # potential bboxes
        tables_lines = self._blocks.collect_stream_lines()

        # parse tables
        tables = Blocks()
        for table_lines in tables_lines:
            # bounding box
            x0 = min([rect.bbox.x0 for rect in table_lines])
            y0 = min([rect.bbox.y0 for rect in table_lines])
            x1 = max([rect.bbox.x1 for rect in table_lines])
            y1 = max([rect.bbox.y1 for rect in table_lines])
            
            # top/bottom border margin: the block before/after table
            y0_margin, y1_margin = y0, y1
            for block in self._blocks:
                if block.bbox.y1 < y0:
                    y0_margin = block.bbox.y1
                if block.bbox.y0 > y1:
                    y1_margin = block.bbox.y0
                    break

            # boundary borders: to be finalized, so set a valid range
            top = HBorder((y0_margin, y0))
            bottom = HBorder((y1, y1_margin))
            left = VBorder((X0, x0))
            right = VBorder((x1, X1))

            top.set_boundary_borders((left, right))
            bottom.set_boundary_borders((left, right))
            left.set_boundary_borders((top, bottom))
            right.set_boundary_borders((top, bottom))

            # table bbox
            rect = BBox().update((X0, y0_margin, X1, y1_margin))

            # parsing stream table
            table = self._stream_table(table_lines, rect, (top, bottom, left, right))
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        
        # ignore table if contains only one cell since it's unnecessary for stream table
        unique_tables = list(filter(lambda table: table.num_rows>1 or table.num_cols>1, unique_tables))

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return unique_tables


    @staticmethod
    def _remove_floating_tables(tables:Blocks):
        '''Delete table has intersection with previously parsed tables.'''
        unique_tables = []
        groups = tables.group_by_connectivity(dx=0.5, dy=0.5)
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


    def _shading_shapes(self):
        ''' Detect shading rects.

            NOTE: Shading borders are checked after parsing lattice tables.            
            
            Note to distinguish shading shape and highlight: 
            - there exists at least one text block contained in shading rect,
            - or no any intersetions with other text blocks (empty block is deleted already);
            - otherwise, highlight rect
        '''
        # lattice tables
        lattice_tables = self._blocks.lattice_table_blocks

        # check shapes
        shading_shapes = [] # type: list[Fill]
        for shape in self._shapes.fillings:

            # focus on shape not parsed yet
            if shape.type != RectType.UNDEFINED: continue

            # not in lattice table region
            for table in lattice_tables:
                if table.bbox.contains(shape.bbox):
                    skip = True
                    break
            else:
                skip = False
            if skip: continue

            # cell shading or highlight:
            # shading shape contains at least one text block
            shading = False
            expand_bbox = shape.bbox + DR / 0.2 # expand 2.5 Pt
            for block in self._blocks:
                if expand_bbox.contains(block.bbox):
                    shading = True
                    break

                # do not containing but intersecting with text block -> can't be shading shape
                elif expand_bbox.intersects(block.bbox):
                    break
                
                # no chance any more
                elif block.bbox.y0 > shape.bbox.y1: 
                    break
            
            if shading: shading_shapes.append(shape)            

        return shading_shapes


    def _stream_table(self, table_lines:Lines, bbox:BBox, outer_borders:tuple):
        '''Parsing stream table based on both block layout and parts of explicit borders.
            ---
            Args:
            - table_lines: a group of Line instances representing cell contents
            - bbox: bounding box of table
            - outer_borders: four Border instances, (top, bottom, left, right), representing outer borders
        '''
        # potentail explicit borders contained in table
        # NOTE: not yet processed rects only
        explicit_strokes = list(filter(
            lambda shape: shape.bbox & bbox.bbox and shape.type==RectType.UNDEFINED, self._shapes.strokes))
        
        # parse stream borders based on contents in cell and explicit borders
        strokes = self.stream_borders(table_lines, outer_borders, Shapes(explicit_strokes))
        if not strokes: return None

        # potential shadings in this table region
        shadings = self._shapes.fillings.contained_in_bbox(bbox.bbox)

        # parse table
        strokes.sort_in_reading_order() # required
        table = self.parse_structure(strokes, shadings)
        
        return table


