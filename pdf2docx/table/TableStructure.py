# -*- coding: utf-8 -*-

'''
Parsing table structure based on borders.

@created: 2020-08-16
@author: train8808@gmail.com
'''

from ..common.BBox import BBox
from ..common.base import RectType
from ..common.utils import RGB_value
from ..common.constants import DM, DR, MAX_W_BORDER
from ..shape.Rectangle import Rectangle
from ..shape.Shapes import Shapes
from ..text.Lines import Lines
from .TableBlock import TableBlock
from .Row import Row
from .Cell import Cell
from .Border import HBorder, VBorder, Borders


class TableStructure:
    '''Parsing table structure based on borders/shadings.'''

    @staticmethod
    def parse_structure(rects:Shapes, detect_border:bool=True):
        ''' Parse table structure from rects.
            ---
            Args:
            - rects: Shapes, representing border, shading or text style
            - detect_border: to detect table border if True.

            NOTE: for stream table, table borders are determined from text blocks in advance,
            so, it's safe to set `detect_border=False`.

            NOTE: rects must be sorted in reading order in advance, which is required by checking 
            merged cells.
        '''

        # --------------------------------------------------
        # mark table borders first
        # --------------------------------------------------
        if detect_border:
            TableStructure._set_borders(rects, width_threshold=MAX_W_BORDER)
        
        # --------------------------------------------------
        # group horizontal/vertical borders
        # --------------------------------------------------
        h_borders, v_borders = TableStructure._group_borders(rects)
        if not h_borders or not v_borders:
            # reset borders because it's a invalid table
            TableStructure._unset_borders(rects)
            return None

        # sort
        y_rows = sorted(h_borders)
        x_cols = sorted(v_borders)

        # --------------------------------------------------
        # parse table structure, especially the merged cells
        # -------------------------------------------------- 
        # check merged cells in each row
        merged_cells_rows = []  # type: list[list[int]]
        for i, row in enumerate(y_rows[0:-1]):
            ref_y = (row+y_rows[i+1])/2.0
            ordered_v_borders = [v_borders[k] for k in x_cols]
            row_structure = TableStructure._check_merged_cells(ref_y, ordered_v_borders, 'row')
            merged_cells_rows.append(row_structure)

        # check merged cells in each column
        merged_cells_cols = []  # type: list[list[int]]
        for i, col in enumerate(x_cols[0:-1]):
            ref_x = (col+x_cols[i+1])/2.0
            ordered_h_borders = [h_borders[k] for k in y_rows]
            col_structure = TableStructure._check_merged_cells(ref_x, ordered_h_borders, 'column')        
            merged_cells_cols.append(col_structure)

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
                    if val==0:
                        n_col += 1
                    else:
                        break
                # check merged rows in vertical direction
                n_row = 1
                for val in merged_cells_cols[j][i+1:]:
                    if val==0:
                        n_row += 1
                    else:
                        break
                
                # cell bbox: merged cells considered
                bbox = (x_cols[j], y_rows[i], x_cols[j+n_col], y_rows[i+n_row])

                # cell border rects
                top = TableStructure._get_border_rect(bbox, h_borders[bbox[1]], 'row')
                bottom = TableStructure._get_border_rect(bbox, h_borders[bbox[3]], 'row')
                left = TableStructure._get_border_rect(bbox, v_borders[bbox[0]], 'col')
                right = TableStructure._get_border_rect(bbox, v_borders[bbox[2]], 'col')

                w_top = top.bbox.y1-top.bbox.y0
                w_right = right.bbox.x1-right.bbox.x0
                w_bottom = bottom.bbox.y1-bottom.bbox.y0
                w_left = left.bbox.x1-left.bbox.x0                

                # shading rect in this cell
                # modify the cell bbox from border center to inner region
                inner_bbox = (bbox[0]+w_left/2.0, bbox[1]+w_top/2.0, bbox[2]-w_right/2.0, bbox[3]-w_bottom/2.0)
                target_bbox = BBox().update(inner_bbox)
                shading_rect = rects.get_contained_rect(target_bbox, threshold=0.9)
                if shading_rect:
                    shading_rect.type = RectType.SHADING # ATTENTION: set shaing type
                    bg_color = shading_rect.color
                else:
                    bg_color = None

                # Cell object
                # Note that cell bbox is calculated under real page CS, so needn't to consider rotation.
                cell = Cell({
                    'bg_color':  bg_color,
                    'border_color': (top.color, right.color, bottom.color, left.color),
                    'border_width': (w_top, w_right, w_bottom, w_left),
                    'merged_cells': (n_row, n_col),
                }).update(bbox)
                row.append(cell)
                    
            # check table when each row finished: 
            # - the first cell in first row MUST NOT be empty
            # - a certain row MUST NOT be empty
            if not row :
                # reset borders because it's a invalid table
                TableStructure._unset_borders(rects)
                return None

            table.append(row)

        return table


    @staticmethod
    def stream_borders(lines:Lines, outer_borders:tuple, showing_borders:Shapes):
        ''' Parsing borders mainly based on content lines contained in cells, and update borders 
            (position and style) with explicit borders represented by rectangle shapes.
            ---
            Args:
            - lines: Lines, contained in table cells
            - outer_borders: (top, bottom, left, right), boundary borders of table
            - showing_borders: showing borders in a stream table; can be empty.
        '''
        borders = Borders()

        # outer borders
        borders.extend(outer_borders)
        
        # inner borders
        inner_borders = TableStructure._inner_borders(lines, outer_borders)
        borders.extend(inner_borders)
        
        # finalize borders
        borders.finalize(showing_borders)

        # all centerlines to rectangle shapes
        res = Shapes()
        for border in borders: 
            res.append(border.to_rect())

        return res


    @staticmethod
    def _set_borders(rects:Shapes, width_threshold:float):
        ''' Detect table borders from rects extracted directly from pdf file.
            ---
            Args:
            - rects: all rects in potential table region
            - width_threshold: float, suppose border width is lower than this threshold value

            Cell borders are detected based on the experiences that:
              - compared to cell shading, the size of cell border never exceeds 6 pt
              - compared to text format, cell border always has intersection with other rects
        '''
        # potential border rects: min-width <= 6 Pt
        thin_rects = [] # type: list[Rectangle]
        for rect in rects:
            x0, y0, x1, y1 = rect.bbox
            if min(x1-x0, y1-y0) <= width_threshold:
                thin_rects.append(rect)

        # These thin rects may be cell borders, or text format, e.g. underline within cell.
        # Compared to text format, cell border always has intersection with other rects
        borders = [] # type: list[Rectangle]
        for rect in thin_rects:
            # NOTE: consider margin due to small gap between borders
            rect_with_margin = rect.bbox + DR

            # check intersections with other rect
            for other_rect in thin_rects:
                if rect==other_rect: continue
                # it's a cell border if intersection found
                # Note: if the intersection is an edge, method `intersects` returns False, while
                # the operator `&` return True. So, `&` is used here.
                if rect_with_margin & other_rect.bbox: 
                    borders.append(rect)
                    break

        # at least two inner borders exist for a normal table
        if len(borders)>=2:
            # set table border type
            for rect in borders:
                rect.type = RectType.BORDER
            return True
            
        return False


    @staticmethod
    def _unset_borders(rects:Shapes):
        '''Unset table border type.'''
        for rect in rects:
            if rect.type==RectType.BORDER:
                rect.type = RectType.UNDEFINED


    @staticmethod
    def _group_borders(rects:Shapes):
        ''' Collect lattice borders in horizontal and vertical groups respectively.'''
        h_borders = {} # type: dict [float, Shapes]
        v_borders = {} # type: dict [float, Shapes]

        X0, Y0, X1, Y1 = 9999.0, 9999.0, 0.0, 0.0
        for rect in rects.borders:
            # group horizontal borders in each row
            if rect.bbox.width > rect.bbox.height:
                # row centerline
                y = round((rect.bbox.y0 + rect.bbox.y1) / 2.0, 1)

                # ignore minor error resulting from different border width
                for y_ in h_borders:
                    if abs(y-y_)<2.0*DM:
                        y = (y_+y)/2.0 # average
                        h_borders[y] = h_borders.pop(y_)
                        h_borders[y].append(rect)
                        break
                else:
                    h_borders[y] = Shapes([rect])

                # update table region
                X0 = min(X0, rect.bbox.x0)
                X1 = max(X1, rect.bbox.x1)

            # group vertical borders in each column
            else:
                # column centerline
                x = round((rect.bbox.x0 + rect.bbox.x1) / 2.0, 1)
                
                # ignore minor error resulting from different border width
                for x_ in v_borders:
                    if abs(x-x_)<2.0*DM:
                        x = (x+x_)/2.0 # average
                        v_borders[x] = v_borders.pop(x_)
                        v_borders[x].append(rect)
                        break
                else:
                    v_borders[x] = Shapes([rect])

                # update table region
                Y0 = min(Y0, rect.bbox.y0)
                Y1 = max(Y1, rect.bbox.y1)

        # at least 2 inner borders exist
        if not h_borders or not v_borders:
            return None, None

        # Note: add dummy borders if no outer borders exist        
        table_bbox = BBox().update((X0, Y0, X1, Y1)) # table bbox
        TableStructure._check_outer_borders(table_bbox, h_borders, 'top')
        TableStructure._check_outer_borders(table_bbox, h_borders, 'bottom')
        TableStructure._check_outer_borders(table_bbox, v_borders, 'left')
        TableStructure._check_outer_borders(table_bbox, v_borders, 'right')

        return h_borders, v_borders
    

    @staticmethod
    def _check_outer_borders(table_bbox:BBox, borders:dict, direction:str):
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
        sample_rect = Rectangle({'color': RGB_value((1,1,1))})        
        bbox[idx] = target
        bbox[(idx+2)%4] = target

        # add whole border if not exist
        if abs(target-current)>MAX_W_BORDER:
            borders[target] = Shapes([sample_rect.copy().update(bbox)])
        
        # otherwise, check border segments
        else:
            idx_start = (idx+1)%2 # 0, 1
            start = table_bbox.bbox[idx_start]

            segments = []
            for rect in borders[current]:
                end = rect.bbox[idx_start]
                # not connected -> add missing border segment
                if abs(start-end)>DM:
                    bbox[idx_start] = start
                    bbox[idx_start+2] = end
                    segments.append(sample_rect.copy().update(bbox))
                
                # update ref position
                start = rect.bbox[idx_start+2]
            
            borders[current].extend(segments)


    @staticmethod
    def _get_border_rect(cell_rect:tuple, rects:Shapes, direction:str):
        ''' Find the rect representing current cell border.
            ---
            Args:
            - x: cell border coordinate, e.g. y for top border
            - rects: candidate rects for cell border
            - direction: either 'row' or 'col'
        '''
        if not rects: return Rectangle()

        # depends on border direction
        idx = 0 if direction=='row' else 1

        # cell range
        x0, x1 = cell_rect[idx], cell_rect[idx+2]

        # check rects
        for rect in rects:
            t0, t1 = rect.bbox[idx], rect.bbox[idx+2]
            # it's the border rect if has a main intersection with cell border
            L = min(x1, t1) - max(x0, t0)
            if L / (x1-x0) >= 0.75:
                return rect

        return rects[0]


    @staticmethod
    def _check_merged_cells(ref:float, borders:list, direction:str='row'):
        ''' Check merged cells in a row/column. 
            ---
            Args:
              - ref: y (or x) coordinate of horizontal (or vertical) passing-through line
              - borders: list[Shapes], a list of vertical (or horizontal) rects list in a column (or row)
              - direction: 'row' - check merged cells in row; 'column' - check merged cells in a column

            Taking cells in a row (direction=0) for example, give a horizontal line (y=ref) passing through this row, 
            check the intersection with vertical borders. The n-th cell is merged if no intersection with the n-th border.
            
        '''
        res = [] # type: list[int]
        for rects in borders[0:-1]:
            # NOTE: rects MUST be sorted in reading order!!
            # multi-lines exist in a row/column
            for rect in rects:

                # reference coordinates depending on checking direction
                if direction=='row':
                    _, ref0, _, ref1 = rect.bbox
                else:
                    ref0, _, ref1, _ = rect.bbox

                # 1) intersection found
                if ref0 < ref < ref1:
                    res.append(1)
                    break
                
                # 2) reference line locates below current rect:
                # still have a chance to find intersection with next rect, but,
                # no chance if this is the last rect, see the else-clause
                elif ref > ref1:
                    continue

                # 3) current rect locates below the reference line:
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
            instead, the later should, M x N table for each cell precisely.
            So, the principle determining borders for stream tables here:
            - two columns: layout if the rows count in each column is different; otherwise, it's a real table
            - otherwise: real table -> deep into rows
        '''
        # trying: deep into cells        
        cols_lines = lines.group_by_columns()
        group_lines = [col_lines.group_by_rows() for col_lines in cols_lines]

        # real table or just text layout?
        col_num = len(cols_lines)
        real_table = True # table by default
        if col_num==2:
            # it's layout if row count is different or the count is 1
            left_count, right_count = len(group_lines[0]), len(group_lines[1])
            if left_count!=right_count or left_count==1:
                real_table = False

        # detect borders based on table/layout mode
        borders = Borders()
        TOP, BOTTOM, LEFT, RIGHT = outer_borders 
        
        # collect lines column by column
        for i in range(col_num): 
            # left column border
            if i==0: left = LEFT

            # right column border
            if i==col_num-1:
                right = RIGHT
            else:                
                x0 = cols_lines[i].bbox.x1
                x1 = cols_lines[i+1].bbox.x0
                right = VBorder(border_range=(x0, x1), borders=(TOP, BOTTOM))
                borders.add(right) # right border of current column
            
            # NOTE: unnecessary to split row if the count of row is 1
            rows_lines = group_lines[i]
            row_num = len(rows_lines)
            if row_num > 1:        
                # collect bboxes row by row 
                for j in range(row_num): 

                    # top row border
                    if j==0: top = TOP

                    # bottom row border
                    if j==row_num-1:
                        bottom = BOTTOM
                    else:                
                        y0 = rows_lines[j].bbox.y1
                        y1 = rows_lines[j+1].bbox.y0
                        bottom = HBorder(border_range=(y0, y1), borders=(left, right))
                        
                        if real_table: borders.add(bottom) # bottom border of current row
                    
                    # needn't go to row level if layout mode
                    if real_table:
                        # recursion to check borders further
                        borders_ = TableStructure._inner_borders(rows_lines[j], (top, bottom, left, right))
                        borders.extend(borders_)
                    
                    # update for next row:
                    # the bottom border of the i-th row becomes top border of the (i+1)-th row
                    top = bottom
                
            # update for next column:
            # the right border of the i-th column becomes left border of the (i+1)-th column
            left = right

        return borders