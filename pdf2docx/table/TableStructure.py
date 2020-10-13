# -*- coding: utf-8 -*-

'''
Parsing table structure based on strokes and fills.



@created: 2020-08-16
@author: train8808@gmail.com
'''

from ..common.BBox import BBox
from ..common.base import RectType
from ..common.utils import RGB_value, get_main_bbox
from ..common import constants
from ..shape.Shape import Stroke
from ..shape.Shapes import Shapes
from ..text.Lines import Lines
from .TableBlock import TableBlock
from .Row import Row
from .Cell import Cell
from .Border import HBorder, VBorder, Borders


class TableStructure:
    '''Parsing table structure based on borders/shadings.'''

    @staticmethod
    def parse_structure(strokes:Shapes, shadings:Shapes):
        ''' Parse table structure from strokes and fills shapes.
            ---
            Args:
            - strokes: Stroke shapes representing table border. For lattice table, they're retrieved from PDF raw contents; 
            for stream table, they're determined from layout of text blocks.
            - fills  : Fill shapes representing cell shading

            NOTE: strokes must be sorted in reading order in advance, required by checking merged cells.

            ```
                    x0        x1       x2        x3
                y0  +----h1---+---h2---+----h3---+
                    |         |        |         |
                    v1        v2       v3        v4
                    |         |        |         |
                y1  +----h4------------+----h5---+
                    |                  |         |
                    v5                 v6        v7
                    |                  |         |
                y2  +--------h6--------+----h7---+
            ```

            Steps to parse table structure:

            1. group horizontal and vertical strokes, e.g. 
            
            ```
                h_strokes = {
                    y0 : [h1, h2, h3],
                    y1 : [h4, h5],
                    y2 : [h6, h7]
                }
            ```
            these [x0, x1, x2, x3] x [y0, y1, y2] forms table lattices, i.e. 2 rows x 3 cols

            2. check merged cells in row/column direction

            let horizontal line y=(y0+y1)/2 cross through table, it gets intersection with v1, v2 and v3,
            indicating no merging exists for cells in the first row.
            when y=(y1+y2)/2, it has no intersection with vertical strokes at x=x1, i.e. merging status is
            [1, 0, 1], indicating Cell(2,2) is merged into Cell(2,1).

            3. use above results to construct TableBlock instance, especially the Cell instance.
        '''        
        # group horizontal/vertical strokes -> table structure        
        h_strokes, v_strokes = TableStructure._group_h_v_strokes(strokes)
        if not h_strokes or not v_strokes: return None

        # sort
        y_rows = sorted(h_strokes)
        x_cols = sorted(v_strokes)

        # check merged cells in each row / column
        merged_cells_rows = TableStructure._merging_status(v_strokes, x_cols, y_rows, 'row')
        merged_cells_cols = TableStructure._merging_status(h_strokes, y_rows, x_cols, 'column')


        # --------------------------------------------------
        # parse table properties
        # --------------------------------------------------
        table = TableBlock()
        n_rows = len(merged_cells_rows)
        n_cols = len(merged_cells_cols)

        for i in range(n_rows):
            # row object
            row = Row()
            row.height = y_rows[i+1]-y_rows[i]
            
            for j in range(n_cols):
                # if current cell is merged horizontally or vertically, set None.
                # actually, it will be counted in the top-left cell of the merged range.
                if merged_cells_rows[i][j]==0 or merged_cells_cols[j][i]==0:
                    row.append(Cell())
                    continue

                # Now, this is the top-left cell of merged range.
                # A separate cell without merging can also be treated as a merged range 
                # with 1 row and 1 colum, i.e. itself.
                #             
                # check merged columns in horizontal direction
                n_col = 1
                for val in merged_cells_rows[i][j+1:]:
                    if val==0: n_col += 1
                    else: break
                # check merged rows in vertical direction
                n_row = 1
                for val in merged_cells_cols[j][i+1:]:
                    if val==0: n_row += 1
                    else: break
                
                # cell bbox: merged cells considered
                bbox = (x_cols[j], y_rows[i], x_cols[j+n_col], y_rows[i+n_row])

                # cell border rects
                top = TableStructure._get_border_shape(bbox, h_strokes[bbox[1]], 'row')
                bottom = TableStructure._get_border_shape(bbox, h_strokes[bbox[3]], 'row')
                left = TableStructure._get_border_shape(bbox, v_strokes[bbox[0]], 'col')
                right = TableStructure._get_border_shape(bbox, v_strokes[bbox[2]], 'col')

                w_top = top.width
                w_right = right.width
                w_bottom = bottom.width
                w_left = left.width

                # shading rect in this cell
                # modify the cell bbox from border center to inner region
                inner_bbox = (bbox[0]+w_left/2.0, bbox[1]+w_top/2.0, bbox[2]-w_right/2.0, bbox[3]-w_bottom/2.0)
                target_bbox = BBox().update_bbox(inner_bbox)
                for shading in shadings:
                    if get_main_bbox(shading.bbox, target_bbox.bbox, threshold=constants.FACTOR_MOST):
                        shading.type = RectType.SHADING # ATTENTION: set shaing type
                        bg_color = shading.color
                        break
                else:
                    bg_color = None

                # Cell object
                # Note that cell bbox is calculated under real page CS, so needn't to consider rotation.
                cell = Cell({
                    'bg_color':  bg_color,
                    'border_color': (top.color, right.color, bottom.color, left.color),
                    'border_width': (w_top, w_right, w_bottom, w_left),
                    'merged_cells': (n_row, n_col),
                }).update_bbox(bbox)

                # check cell before adding to row:
                # no intersection with cells in previous row
                if i > 0:
                    for pre_cell in table[i-1]:
                        # Note the difference between methods: `intersects` and `&`
                        if cell.bbox.intersects(pre_cell.bbox): return None

                row.append(cell)
                    
            # check row before adding to table: row MUST NOT be empty
            if not row: return None

            table.append(row)


        # parse table successfully, so set border type explicitly
        for border in strokes:
            border.type = RectType.BORDER

        return table


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
        inner_borders = TableStructure._inner_borders(lines, outer_borders)
        borders.extend(inner_borders)
        
        # finalize borders
        borders.finalize(showing_borders, showing_shadings)

        # all centerlines to rectangle shapes
        res = Shapes()
        for border in borders: 
            res.append(border.to_stroke())

        return res


    @staticmethod
    def _group_h_v_strokes(strokes:Shapes):
        ''' Split strokes in horizontal and vertical groups respectively.

            According to strokes below, the grouped h-strokes looks like
            ```
                h_strokes = {
                    y0 : [h1, h2, h3],
                    y1 : [h4, h5],
                    y2 : [h6, h7]
                }
            ```

            ```
               x0        x1        x2        x3
            y0  +----h1---+---h2---+----h3---+
                |         |        |         |
                v1        v2       v3        v4
                |         |        |         |
            y1  +----h4------------+----h5---+
                |                  |         |
                v5                 v6        v7
                |                  |         |
            y2  +--------h6--------+----h7---+
            ```
        '''
        h_strokes = {} # type: dict [float, Shapes]
        v_strokes = {} # type: dict [float, Shapes]

        X0, Y0, X1, Y1 = float('inf'), float('inf'), -float('inf'), -float('inf')
        for stroke in strokes:
            # group horizontal strokes in each row
            if stroke.horizontal:
                y = round(stroke.y0, 1)

                # ignore minor error resulting from different stroke width
                for y_ in h_strokes:
                    if abs(y-y_)>constants.DW_BORDER: continue
                    y = (y_+y)/2.0 # average
                    h_strokes[y] = h_strokes.pop(y_)
                    h_strokes[y].append(stroke)
                    break
                else:
                    h_strokes[y] = Shapes([stroke])

                # update table region
                X0 = min(X0, stroke.x0)
                X1 = max(X1, stroke.x1)

            # group vertical strokes in each column
            elif stroke.vertical:
                x = round(stroke.x0, 1)
                
                # ignore minor error resulting from different stroke width
                for x_ in v_strokes:
                    if abs(x-x_)>constants.DW_BORDER: continue
                    x = (x+x_)/2.0 # average
                    v_strokes[x] = v_strokes.pop(x_)
                    v_strokes[x].append(stroke)
                    break
                else:
                    v_strokes[x] = Shapes([stroke])

                # update table region
                Y0 = min(Y0, stroke.y0)
                Y1 = max(Y1, stroke.y1)

        # at least 2 inner strokes exist
        if not h_strokes or not v_strokes: return None, None

        # Note: add dummy strokes if no outer strokes exist        
        table_bbox = BBox().update_bbox((X0, Y0, X1, Y1)) # table bbox
        TableStructure._check_outer_strokes(table_bbox, h_strokes, 'top')
        TableStructure._check_outer_strokes(table_bbox, h_strokes, 'bottom')
        TableStructure._check_outer_strokes(table_bbox, v_strokes, 'left')
        TableStructure._check_outer_strokes(table_bbox, v_strokes, 'right')

        return h_strokes, v_strokes
    

    @staticmethod
    def _check_outer_strokes(table_bbox:BBox, borders:dict, direction:str):
        '''Add missing outer borders based on table bbox and grouped horizontal/vertical borders.
            ---
            Args:
            - table_bbox: table region
            - borders: grouped horizontal (or vertical) borders at y-coordinates
            - direction: either 'top' or 'bottom' or 'left' or 'right'
        '''
        # target / real borders
        bbox = list(table_bbox.bbox)
        if direction=='top':
            idx = 1
            current = min(borders)
            borders[current].sort_in_line_order()
        elif direction=='bottom':
            idx = 3
            current = max(borders)
            borders[current].sort_in_line_order()
        elif direction=='left':
            idx = 0
            current = min(borders)
            borders[current].sort_in_reading_order()
        elif direction=='right':
            idx = 2
            current = max(borders)
            borders[current].sort_in_reading_order()
        else:
            return
        target = bbox[idx]
        
        # add missing border rects
        sample_border = Stroke({'color': RGB_value((1,1,1))})        
        bbox[idx] = target
        bbox[(idx+2)%4] = target

        # add whole border if not exist
        if abs(target-current)>constants.MAX_W_BORDER:
            borders[target] = Shapes([sample_border.copy().update_bbox(bbox)])
        
        # otherwise, check border segments
        else:
            idx_start = (idx+1)%2 # 0, 1
            start = table_bbox.bbox[idx_start]

            segments = []
            for border in borders[current]:
                end = border.bbox[idx_start]
                # not connected -> add missing border segment
                if abs(start-end)>constants.MINOR_DIST:
                    bbox[idx_start] = start
                    bbox[idx_start+2] = end
                    segments.append(sample_border.copy().update_bbox(bbox))
                
                # update ref position
                start = border.bbox[idx_start+2]
            
            borders[current].extend(segments)


    @staticmethod
    def _merging_status(strokes:dict, keys:list, y_rows:list, direction:str='row'):
        ''' Check cell merging status. taking row direction for example,
            ---
            Args:
            - strokes: a dict of strokes,  {x: [v_stroke1, v_stroke_2, ...]}
            - keys: sorted keys of `strokes`
            - y_rows: y-coordinates of row borders
            - direction: 'row' - check merged cells in row; 'column' - check merged cells in a column

            ```
                +-----+-----+-----+
                |     |     |     |
                |     |     |     |
                +-----+-----------+
                |           |     |
            ----1-----0-----1----------> [1, 0, 1]
                |           |     |
                |           |     |
                +-----------+-----+
            ```
        '''
        # check merged cells in each row/col
        merged_cells = []  # type: list[list[int]]

        for i in range(len(y_rows)-1):
            ref_y = (y_rows[i]+y_rows[i+1])/2.0
            ordered_strokes = [strokes[k] for k in keys]
            row_structure = TableStructure._check_merged_cells(ref_y, ordered_strokes, direction)
            merged_cells.append(row_structure)
        
        return merged_cells


    @staticmethod
    def _get_border_shape(cell_rect:tuple, borders:Shapes, direction:str):
        ''' Find the rect representing current cell border.
            ---
            Args:
            - cell_rect: cell bbox
            - borders: candidate stroke shapes for cell border
            - direction: either 'row' or 'col'
        '''
        if not borders: return Stroke()

        # depends on border direction
        idx = 0 if direction=='row' else 1

        # cell range
        x0, x1 = cell_rect[idx], cell_rect[idx+2]

        # check borders
        for border in borders:
            bbox = (border.x0, border.y0, border.x1, border.y1)
            t0, t1 = bbox[idx], bbox[idx+2]
            # it's the border shape if has a major intersection with cell border
            L = min(x1, t1) - max(x0, t0)
            if L / (x1-x0) >= constants.FACTOR_MAJOR:
                return border

        return borders[0]


    @staticmethod
    def _check_merged_cells(ref:float, borders:list, direction:str='row'):
        ''' Check merged cells in a row/column. 
            ---
            Args:
            - ref: y (or x) coordinate of horizontal (or vertical) passing-through line
            - borders: list[Shapes], a list of vertical (or horizontal) rects list in a column (or row)
            - direction: 'row' - check merged cells in row; 'column' - check merged cells in a column

            Taking cells in a row for example, give a horizontal line (y=ref) passing through this row, 
            check the intersection with vertical borders. The n-th cell is merged if no intersection with the n-th border.            
        '''
        res = [] # type: list[int]
        for shapes in borders[0:-1]:
            # NOTE: shapes MUST be sorted in reading order!!
            # multi-lines exist in a row/column
            for border in shapes:

                # reference coordinates depending on checking direction
                if direction=='row':
                    ref0, ref1 = border.y0, border.y1
                else:
                    ref0, ref1 = border.x0, border.x1

                # 1) intersection found
                if ref0 < ref < ref1:
                    res.append(1)
                    break
                
                # 2) reference line locates below current border:
                # still have a chance to find intersection with next border, but,
                # no chance if this is the last border, see the else-clause
                elif ref > ref1:
                    continue

                # 3) current border locates below the reference line:
                # no intersection is possible any more
                elif ref < ref0:
                    res.append(0)
                    break
            
            # see notes 2), no change any more
            else:
                res.append(0)

        return res


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
                borders_ = TableStructure._inner_borders(rows_lines[j], (top, bottom, left, right))
                borders.extend(borders_)

        return borders