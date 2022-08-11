# -*- coding: utf-8 -*-

'''Parsing table blocks.

* ``lattice table``: explicit borders represented by strokes.
* ``stream table`` : borderless table recognized from layout of text blocks.

Terms definition:

* From appearance aspect, we say ``stroke`` and ``fill``, the former looks like a line, 
  while the later an area.
* From semantic aspect, we say ``border`` (cell border) and ``shading`` (cell shading).
* An explicit border is determined by a certain stroke, while a stroke may also represent 
  an underline of text.
* An explicit shading is determined by a fill, while a fill may also represent a highlight 
  of text.
* Border object is introduced to determin borders of stream table. Border instance is a 
  virtual border adaptive in a certain range, then converted to a stroke once finalized, 
  and finally applied to detect table border.
'''

from ..common import constants
from ..common.Element import Element
from ..common.Collection import Collection
from ..layout.Blocks import Blocks
from ..shape.Shapes import Shapes
from ..text.Lines import Lines
from .TableStructure import TableStructure
from .Border import Border, Borders
from .Cell import Cell


class TablesConstructor:
    '''Object parsing ``TableBlock`` for specified ``Layout``.'''

    def __init__(self, parent):
        self._parent = parent # Layout
        self._blocks = parent.blocks # type: Blocks
        self._shapes = parent.shapes # type: Shapes


    def lattice_tables(self, 
                connected_border_tolerance:float,
                min_border_clearance:float,
                max_border_width:float):
        """Parse table with explicit borders/shadings represented by rectangle shapes.

        Args:
            connected_border_tolerance (float): Two borders are intersected if the gap lower than this value.
            min_border_clearance (float): The minimum allowable clearance of two borders.
            max_border_width (float): Max border width.
        """
        if not self._shapes: return

        def remove_overlap(instances:list):
            '''Delete group when it's contained in a certain group.'''
            # group instances if contained in other instance
            fun = lambda a, b: a.bbox.contains(b.bbox) or b.bbox.contains(a.bbox)
            groups = Collection(instances).group(fun)
            unique_groups = []
            for group_instances in groups:
                if len(group_instances)==1: 
                    instance = group_instances[0]
                
                # contained groups: keep the largest one
                else:
                    sorted_group = sorted(group_instances, 
                        key=lambda instance: instance.bbox.get_area())
                    instance = sorted_group[-1]
                
                unique_groups.append(instance)
            
            return unique_groups

        # group stroke shapes: each group may be a potential table
        grouped_strokes = self._shapes.table_strokes \
            .group_by_connectivity(dx=connected_border_tolerance, dy=connected_border_tolerance)

        # ignore overlapped groups: it'll be processed in sub-layout
        grouped_strokes = remove_overlap(grouped_strokes) 

        # all filling shapes
        fills = self._shapes.table_fillings

        # parse table with each group
        tables = Blocks()
        settings = {
            'min_border_clearance': min_border_clearance,
            'max_border_width': max_border_width
        }
        for strokes in grouped_strokes:
            # potential shadings in this table region
            group_fills = fills.contained_in_bbox(strokes.bbox)

            # parse table structure
            table = TableStructure(strokes, **settings).parse(group_fills).to_table_block()
            if table:
                table.set_lattice_table_block()
                tables.append(table)            

        # assign blocks/shapes to each table
        self._blocks.assign_to_tables(tables)
        self._shapes.assign_to_tables(tables)


    def stream_tables(self, 
                min_border_clearance:float, 
                max_border_width:float,
                line_separate_threshold:float
            ):
        '''Parse table with layout of text/image blocks, and update borders with explicit borders 
        represented by rectangle shapes.

        Refer to ``lattice_tables`` for arguments description.
        '''
        # all explicit borders and shadings
        table_strokes = self._shapes.table_strokes
        table_fillings = self._shapes.table_fillings

        # lines in potential stream tables
        tables_lines = self._blocks.collect_stream_lines(table_fillings, line_separate_threshold)            

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
            'max_border_width': max_border_width
        }

        for table_lines in tables_lines:
            if not table_lines: continue
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
            explicit_shadings, _ = table_fillings.split_with_intersection(rect.bbox, threshold=constants.FACTOR_A_FEW) 

            # NOTE: ignore simple structure table, especially only one cell, which leads to infinite recursion error.
            if not (explicit_shadings or explicit_strokes) and \
                TablesConstructor._is_simple_structure(table_lines): continue

            # parse stream borders based on lines in cell and explicit borders/shadings
            strokes = self._stream_strokes(table_lines, outer_borders, explicit_strokes, explicit_shadings)
            if not strokes: continue

            # parse table structure
            strokes.sort_in_reading_order() # required
            table = TableStructure(strokes, **settings).parse(explicit_shadings).to_table_block()

            # Attention: avoid further infinite stream table detection.
            # Generally, a 1x1 stream table nested in a table cell is of no use
            if isinstance(self._parent, Cell) and \
                table.num_cols*table.num_rows==1 and table[0][0].bg_color is None:
                continue

            table.set_stream_table_block()
            tables.append(table)

        # assign blocks/shapes to each table
        self._blocks.assign_to_tables(tables)
        self._shapes.assign_to_tables(tables)


    @staticmethod
    def _is_simple_structure(lines:Lines):
        '''Whether current lines represent a simple table:        
        * only one column -> always flow layout in docx; or
        * two columns: lines are aligned in each row -> simple paragraph in docx
        '''
        num = len(lines.group_by_columns())
        if num==1:
            return True
        elif num==2:
            return len(lines.group_by_physical_rows())==len(lines.group_by_rows())
        else:
            return False


    @staticmethod
    def _stream_strokes(lines:Lines, outer_borders:tuple, explicit_strokes:Shapes, explicit_shadings:Shapes):
        '''Parsing borders mainly based on content lines contained in cells, 
        and update borders (position and style) with explicit borders represented 
        by rectangle shapes.
        
        Args:
            lines (Lines): lines contained in table cells.
            outer_borders (tuple): Boundary borders of table, ``(top, bottom, left, right)``.
            explicit_strokes (Shapes): Showing borders in a stream table; can be empty.
            explicit_shadings (Shapes): Showing shadings in a stream table; can be empty.
        
        Returns:
            Shapes: Parsed strokes representing table borders.
        '''
        borders = Borders()

        # outer borders
        borders.extend(outer_borders)
        
        # inner borders
        inner_borders = TablesConstructor._inner_borders(lines, outer_borders)
        borders.extend(inner_borders)
        
        # finalize borders
        borders.finalize(explicit_strokes, explicit_shadings)

        # all centerlines to rectangle shapes
        res = Shapes()
        for border in borders: 
            res.append(border.to_stroke())

        return res


    @staticmethod
    def _outer_borders(inner_bbox, outer_bbox):
        '''Initialize outer Border instances according to lower and upper bbox-es.

        ::
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
        '''
        x0, y0, x1, y1 = inner_bbox
        X0, Y0, X1, Y1 = outer_bbox
        top    = Border('HT', border_range=(Y0, y0), reference=False)
        bottom = Border('HB', border_range=(y1, Y1), reference=False)
        left   = Border('VL', border_range=(X0, x0), reference=False)
        right  = Border('VR', border_range=(x1, X1), reference=False)

        # boundary borders of each border
        top.set_boundary_borders((left, right))
        bottom.set_boundary_borders((left, right))
        left.set_boundary_borders((top, bottom))
        right.set_boundary_borders((top, bottom))

        return (top, bottom, left, right)


    @staticmethod
    def _inner_borders(lines:Lines, outer_borders:tuple):
        '''Calculate the surrounding borders of given ``lines``. These borders construct table cells. 

        Two purposes of stream table: 

        * Rebuild layout, e.g. text layout with two columns, and
        * parsing real borderless table.

        It's controdictory that the former needn't to deep into row level, just ``1xN`` table 
        convenient for layout recreation; instead, the later should, ``MxN`` table for each 
        cell precisely. So, the principle determining stream tables borders:

        * Vertical borders contributes the table structure, so ``border.is_reference=False``.
        * Horizontal borders are for reference when ``n_column=2``, in this case ``border.is_reference=True``.
        * During deeper recursion, h-borders become outer borders: it turns valuable when count 
          of detected columns >= 2.
        
        Args:
            lines (Lines): Lines in table cells.
            outer_borders (tuple): Boundary borders of table region.
        '''
        # trying: deep into cells
        cols_lines = lines.group_by_columns()
        group_lines = [col_lines.group_by_rows(factor=constants.FACTOR_A_FEW) for col_lines in cols_lines]

        # horizontal borders are for reference only when n_column<=2 -> 
        # consider 1-column or 2-columns text layout
        col_num = len(cols_lines)
        is_reference = col_num<=2

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
                right = Border(border_type='VI',
                    border_range=(x0, x1), 
                    borders=(TOP, BOTTOM), 
                    reference=False) # vertical border always valuable
                borders.append(right) # right border of current column            
            
            # NOTE: unnecessary to split row if the count of row is 1
            rows_lines = group_lines[i]
            row_num = len(rows_lines)
            if row_num == 1: continue

            # collect bbox-es row by row
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
                    bottom = Border(border_type='HI',
                        border_range=(y0, y1), 
                        borders=(left, right), 
                        reference=is_reference)
                    borders.append(bottom)

                # recursion to check borders further
                borders_ = TablesConstructor._inner_borders(rows_lines[j], (top, bottom, left, right))
                borders.extend(borders_)

        return borders