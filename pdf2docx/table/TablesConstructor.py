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
'''

from ..common.Element import Element
from ..common import constants
from ..page.Blocks import Blocks
from ..shape.Shapes import Shapes
from ..text.Lines import Lines
from .TableStructure import TableStructure
from .Border import HBorder, VBorder, Borders

class TablesConstructor:

    def __init__(self, parent):
        '''Object parsing TableBlock.'''
        self._parent = parent # Page
        self._blocks = parent.blocks if parent else None # type: Blocks
        self._shapes = parent.shapes if parent else None # type: Shapes


    def lattice_tables(self, 
            connected_border_tolerance:float, # two borders are intersected if the gap lower than this value
            min_border_clearance:float,       # the minimum allowable clearance of two borders
            max_border_width:float,           # max border width
            float_layout_tolerance:float,     # [0,1] the larger of this value, the more tolerable of flow layout
            line_overlap_threshold:float,     # [0,1] delete line if the intersection to other lines exceeds this value
            line_merging_threshold:float ,    # combine two lines if the x-distance is lower than this value
            line_separate_threshold:float     # two separate lines if the x-distance exceeds this value
            ):
        '''Parse table with explicit borders/shadings represented by rectangle shapes.'''
        # group stroke shapes: each group may be a potential table
        grouped_strokes = self._shapes.table_strokes \
            .group_by_connectivity(dx=connected_border_tolerance, dy=connected_border_tolerance)

        # all filling shapes
        fills = self._shapes.table_fillings

        # parse table with each group
        tables = Blocks()
        settings = {
            'min_border_clearance': min_border_clearance,
            'max_border_width': max_border_width,
            'float_layout_tolerance': float_layout_tolerance,
            'line_overlap_threshold': line_overlap_threshold,
            'line_merging_threshold': line_merging_threshold,
            'line_separate_threshold': line_separate_threshold
        }
        for strokes in grouped_strokes:
            # potential shadings in this table region
            group_fills = fills.contained_in_bbox(strokes.bbox)

            # parse table structure
            table = TableStructure(strokes, settings).parse(group_fills).to_table_block()
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add table to page level
            table.set_lattice_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables, settings)

        return Blocks(unique_tables) # this return is just for debug plot


    def stream_tables(self, 
                min_border_clearance:float, 
                max_border_width:float,
                float_layout_tolerance:float,
                line_overlap_threshold:float,
                line_merging_threshold:float,
                line_separate_threshold:float
            ):
        ''' Parse table with layout of text/image blocks, and update borders with explicit borders 
            represented by rectangle shapes.
        '''
        # all explicit borders and shadings
        table_strokes = self._shapes.table_strokes
        table_fillings = self._shapes.table_fillings

        # lines in potential stream tables
        tables_lines = self._blocks.collect_stream_lines(table_fillings, float_layout_tolerance, line_separate_threshold)            

        # define a function to get the vertical boundaries of given table
        X0, Y0, X1, Y1 = self._parent.bbox
        def top_bottom_boundaries(y0, y1):
            '''find the vertical boundaries of table in y-range [y0, y1]:
                - the bottom of block closest to y0
                - the top of block closest to y1

                ```
                +-------------------------+  <- Y0

                +--------------+
                +--------------+  <- y_lower

                +------------------------+  <- y0
                |         table          |
                +------------------------+  <- y1

                +-------------------------+ <- y_upper
                +-------------------------+

                +---------------------------+ <- Y1
                ```
            '''
            y_lower, y_upper = Y0, Y1
            for block in self._blocks:
                # move top border
                if block.bbox.y1 < y0: y_lower = block.bbox.y1

                # reach first bottom border
                if block.bbox.y0 > y1:
                    y_upper = block.bbox.y0
                    break
            return y_lower, y_upper

        # parse tables
        tables = Blocks()
        settings = {
            'min_border_clearance': min_border_clearance,
            'max_border_width': max_border_width,
            'float_layout_tolerance': float_layout_tolerance,
            'line_overlap_threshold': line_overlap_threshold,
            'line_merging_threshold': line_merging_threshold,
            'line_separate_threshold': line_separate_threshold
        }
        for table_lines in tables_lines:
            # bounding box
            x0 = min([rect.bbox.x0 for rect in table_lines])
            y0 = min([rect.bbox.y0 for rect in table_lines])
            x1 = max([rect.bbox.x1 for rect in table_lines])
            y1 = max([rect.bbox.y1 for rect in table_lines])
            
            # boundary borders to be finalized
            y0_margin, y1_margin = top_bottom_boundaries(y0, y1)
            inner_bbox = (x0, y0, x1, y1)
            outer_bbox = (X0, y0_margin, X1, y1_margin)
            outer_borders = TablesConstructor._outer_borders(inner_bbox, outer_bbox)

            # explicit strokes/shadings in table region
            rect = Element().update_bbox(outer_bbox)
            explicit_strokes  = table_strokes.contained_in_bbox(rect.bbox)
            # NOTE: shading with any intersections should be counted to avoid missing any candidates
            explicit_shadings, _ = table_fillings.split_with_intersection(rect.bbox) 

            # parse stream borders based on lines in cell and explicit borders/shadings
            strokes = self.stream_strokes(table_lines, outer_borders, explicit_strokes, explicit_shadings)
            if not strokes: continue

            # parse table structure
            strokes.sort_in_reading_order() # required
            table = TableStructure(strokes, settings).parse(explicit_shadings).to_table_block()
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables: 
            # set type: stream table
            table.set_stream_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables, settings)

        return Blocks(unique_tables) # this return is just for debug plot


    @staticmethod
    def stream_strokes(lines:Lines, outer_borders:tuple, showing_borders:Shapes, showing_shadings:Shapes):
        ''' Parsing borders mainly based on content lines contained in cells, and update borders 
            (position and style) with explicit borders represented by rectangle shapes.
            ---
            Args:
            - lines: Lines, contained in table cells
            - outer_borders: (top, bottom, left, right), boundary borders of table
            - showing_borders: showing borders in a stream table; can be empty.
            - showing_shadings: showing shadings in a stream table; can be empty.
        '''
        borders = Borders()

        # outer borders
        borders.extend(outer_borders)
        
        # inner borders
        inner_borders = TablesConstructor._inner_borders(lines, outer_borders)
        borders.extend(inner_borders)
        
        # finalize borders
        borders.finalize(showing_borders, showing_shadings)

        # all centerlines to rectangle shapes
        res = Shapes()
        for border in borders: 
            res.append(border.to_stroke())

        return res


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


    @staticmethod
    def _outer_borders(inner_bbox, outer_bbox):
        '''Initialize outer Border instances according to lower and upper bboxes.
            ```
            +--------------------------------->
            |
            | Y0 +------------------------+     + outer bbox
            |    |                        |     |
            |    | y0+----------------+   |     |
            |    |   |                |   +<----+
            |    |   |                +<--------+ inner bbox
            |    | y1+----------------+   |
            |    |   x0               x1  |
            | Y1 +------------------------+
            |    X0                       X1
            v
            ```
        '''
        x0, y0, x1, y1 = inner_bbox
        X0, Y0, X1, Y1 = outer_bbox
        top    = HBorder(border_range=(Y0, y0), reference=False)
        bottom = HBorder(border_range=(y1, Y1), reference=False)
        left   = VBorder(border_range=(X0, x0), reference=False)
        right  = VBorder(border_range=(x1, X1), reference=False)

        # boundary borders of each border
        top.set_boundary_borders((left, right))
        bottom.set_boundary_borders((left, right))
        left.set_boundary_borders((top, bottom))
        right.set_boundary_borders((top, bottom))

        return (top, bottom, left, right)


    @staticmethod
    def _inner_borders(lines:Lines, outer_borders:tuple):
        ''' Calculate the surrounding borders of given lines.
            ---
            Args:
            - lines: lines in table cells
            - outer_borders: boundary borders of table region

            These borders construct table cells. Considering the re-building of cell content in docx, 
            - only one bbox is allowed in a line;
            - but multi-lines are allowed in a cell.

            Two purposes of stream table: 
            - rebuild layout, e.g. text layout with two columns
            - parsing real borderless table

            It's controdictory that the former needn't to deep into row level, just 1 x N table convenient for layout recreation;
            instead, the later should, M x N table for each cell precisely. So, the principle determining stream tables borders:
            - vertical borders contributes the table structure, so border.is_reference=False
            - horizontal borders are for reference when n_column=2, border.is_reference=True
            - during deeper recursion, h-borders become outer borders: it turns valuable when count of detected columns >= 2 
        '''
        # trying: deep into cells        
        cols_lines = lines.group_by_columns()
        group_lines = [col_lines.group_by_rows() for col_lines in cols_lines]

        # horizontal borders are for reference when n_column=2 -> consider two-columns text layout
        col_num = len(cols_lines)
        is_reference = col_num==2

        # outer borders construct the table, so they're not just for reference        
        if col_num>=2: # outer borders contribute to table structure
            for border in outer_borders:
                border.is_reference = False

        borders = Borders() # final results
        
        # collect lines column by column
        right = None
        TOP, BOTTOM, LEFT, RIGHT = outer_borders 
        for i in range(col_num): 
            # left column border: after the first round the right border of the i-th column becomes 
            # left border of the (i+1)-th column
            left = LEFT if i==0 else right
            
            # right column border
            if i==col_num-1: right = RIGHT
            else:                
                x0 = cols_lines[i].bbox.x1
                x1 = cols_lines[i+1].bbox.x0
                right = VBorder(
                    border_range=(x0, x1), 
                    borders=(TOP, BOTTOM), 
                    reference=False) # vertical border always valuable
                borders.add(right) # right border of current column            
            
            # NOTE: unnecessary to split row if the count of row is 1
            rows_lines = group_lines[i]
            row_num = len(rows_lines)
            if row_num == 1: continue

            # collect bboxes row by row
            bottom = None
            for j in range(row_num):
                # top row border, after the first round, the bottom border of the i-th row becomes 
                # top border of the (i+1)-th row
                top = TOP if j==0 else bottom

                # bottom row border
                if j==row_num-1: bottom = BOTTOM
                else:                
                    y0 = rows_lines[j].bbox.y1
                    y1 = rows_lines[j+1].bbox.y0

                    # bottom border of current row
                    # NOTE: for now, this horizontal border is just for reference; 
                    # it'll becomes real border when used as an outer border
                    bottom = HBorder(
                        border_range=(y0, y1), 
                        borders=(left, right), 
                        reference=is_reference)
                    borders.add(bottom)

                # recursion to check borders further
                borders_ = TablesConstructor._inner_borders(rows_lines[j], (top, bottom, left, right))
                borders.extend(borders_)

        return borders