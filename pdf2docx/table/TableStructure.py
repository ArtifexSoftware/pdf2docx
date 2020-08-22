# -*- coding: utf-8 -*-

'''
Parsing table structure based on borders.

@created: 2020-08-16
@author: train8808@gmail.com
'''

from ..common.BBox import BBox
from ..common.base import RectType
from ..common import utils
from ..shape.Rectangle import Rectangle
from ..shape.Rectangles import Rectangles
from .TableBlock import TableBlock
from .Row import Row
from .Cell import Cell


class TableStructure:
    '''Parsing table structure based on borders/shadings.'''

    def parse_structure(self, rects:Rectangles, detect_border:bool=True):
        ''' Parse table structure from rects.
            ---
            Args:
            - rects: Rectangles, representing border, shading or text style
            - detect_border: to detect table border if True.

            NOTE: for stream table, table borders are determined from text blocks in advance,
            so, it's safe to set `detect_border=False`.

            NOTE: rects must be sorted in reading order in advance, which is required by checking 
            merged cells.
        '''

        # --------------------------------------------------
        # mark table borders first
        # --------------------------------------------------
        # exit if no borders exist
        if detect_border and not self._set_borders(rects, width_threshold=6.0):
            return None
        
        # --------------------------------------------------
        # group horizontal/vertical borders
        # --------------------------------------------------
        h_borders, v_borders = self._group_borders(rects)
        if not h_borders or not v_borders:
            # reset borders because it's a invalid table
            self._unset_borders(rects)
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
            row_structure = self._check_merged_cells(ref_y, ordered_v_borders, 'row')
            merged_cells_rows.append(row_structure)

        # check merged cells in each column
        merged_cells_cols = []  # type: list[list[int]]
        for i, col in enumerate(x_cols[0:-1]):
            ref_x = (col+x_cols[i+1])/2.0
            ordered_h_borders = [h_borders[k] for k in y_rows]
            col_structure = self._check_merged_cells(ref_x, ordered_h_borders, 'column')        
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

                # cell border rects: merged cells considered
                top = h_borders[y_rows[i]][0]
                bottom = h_borders[y_rows[i+n_row]][0]
                left = v_borders[x_cols[j]][0]
                right = v_borders[x_cols[j+n_col]][0]

                w_top = top.bbox.y1-top.bbox.y0
                w_right = right.bbox.x1-right.bbox.x0
                w_bottom = bottom.bbox.y1-bottom.bbox.y0
                w_left = left.bbox.x1-left.bbox.x0

                # cell bbox
                bbox = (x_cols[j], y_rows[i], x_cols[j+n_col], y_rows[i+n_row])

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
                cell_dict = {
                    'bbox': bbox,
                    'bg_color':  bg_color,
                    'border_color': (top.color, right.color, bottom.color, left.color),
                    'border_width': (w_top, w_right, w_bottom, w_left),
                    'merged_cells': (n_row, n_col),
                }
                row.append(Cell(cell_dict))
                    
            # one row finished
            # check table: the first cell in first row MUST NOT be None
            if i==0 and not row[0]:
                # reset borders because it's a invalid table
                self._unset_borders(rects)
                return None

            table.append(row)

        return table


    @staticmethod
    def _set_borders(rects:Rectangles, width_threshold:float=6.0):
        ''' Detect table borders from rects.
            ---
            Args:
            - rects: all rects in potential table region
            - width_threshold: float, suppose border width is lower than this threshold value

            Cell borders are detected based on the experiences that:
              - compared to cell shading, the size of cell border never exceeds 6 pt
              - compared to text format, cell border always has intersection with other rects

            NOTE: cell shading is determined after the table structure is parsed from these cell borders.
        '''
        # Get all rects with on condition: size < 6 Pt
        thin_rects = [] # type: list[Rectangle]
        for rect in rects:
            x0, y0, x1, y1 = rect.bbox_raw
            if min(x1-x0, y1-y0) <= width_threshold:
                thin_rects.append(rect)

        # These thin rects may be cell borders, or text format, e.g. underline within cell.
        # Compared to text format, cell border always has intersection with other rects
        borders = [] # type: list[Rectangle]
        for rect in thin_rects:
            # check intersections with other rect
            for other_rect in thin_rects:
                if rect==other_rect: continue
                # it's a cell border if intersection found
                # Note: if the intersection is an edge, method `intersects` returns False, while
                # the operator `&` return True. So, `&` is used here.
                if rect.bbox & other_rect.bbox: 
                    borders.append(rect)
                    break

        # at least two inner borders exist for a normal table
        if len(borders)>=2:
            # set table border type
            for rect in borders:
                rect.type = RectType.BORDER
            return True
        else:
            return False


    @staticmethod
    def _unset_borders(rects:Rectangles):
        '''Unset table border type.'''
        for rect in rects:
            if rect.type==RectType.BORDER:
                rect.type = RectType.UNDEFINED


    def _group_borders(self, rects:Rectangles):
        ''' Collect lattice borders in horizontal and vertical groups respectively.'''        

        h_borders = {} # type: dict [float, Rectangles]
        v_borders = {} # type: dict [float, Rectangles]
        h_outer = []   # type: list[float]
        v_outer = []   # type: list[float]

        for rect in rects.border_rects:
            # group horizontal borders in each row
            if rect.bbox.width > rect.bbox.height:
                # row centerline
                y = round((rect.bbox.y0 + rect.bbox.y1) / 2.0, 1)

                # ignore minor error resulting from different border width
                for y_ in h_borders:
                    if abs(y-y_)<utils.DM:
                        h_borders[y_].append(rect)
                        break
                else:
                    h_borders[y] = Rectangles([rect])
                
                # candidates for vertical outer border
                v_outer.extend([rect.bbox.x0, rect.bbox.x1])

            # group vertical borders in each column
            else:
                # column centerline
                x = round((rect.bbox.x0 + rect.bbox.x1) / 2.0, 1)
                
                # ignore minor error resulting from different border width
                for x_ in v_borders:
                    if abs(x-x_)<utils.DM:
                        v_borders[x_].append(rect)
                        break
                else:
                    v_borders[x] = Rectangles([rect])
                
                # candidates for horizontal outer border
                h_outer.extend([rect.bbox.y0, rect.bbox.y1])

        # at least 2 inner borders exist
        if not h_borders or not v_borders:
            return None, None

        # Note: add dummy borders if no outer borders exist
        # check whether outer borders exists in collected borders
        if h_borders:
            top_rects = h_borders[min(h_borders)]
            bottom_rects = h_borders[max(h_borders)]
            left   = min(v_outer)
            right  = max(v_outer)
        else:
            top_rects = Rectangles()
            bottom_rects = Rectangles()
            left   = None
            right  = None

        if v_borders:
            left_rects = v_borders[min(v_borders)]
            right_rects = v_borders[max(v_borders)]
            top   = min(h_outer)
            bottom  = max(h_outer)
        else:
            left_rects = Rectangles()
            right_rects = Rectangles()
            top   = None
            bottom  = None    

        c = utils.RGB_value((1,1,1))
        if not self._exist_outer_border(top_rects, top, 'h'):
            h_borders[top] = Rectangles([
                Rectangle({
                    'bbox': (left, top, right, top),
                    'color': c
                })])
        if not self._exist_outer_border(bottom_rects, bottom, 'h'):
            h_borders[bottom] = Rectangles([
                Rectangle({
                    'bbox': (left, bottom, right, bottom),
                    'color': c
                })])
        if not self._exist_outer_border(left_rects, left, 'v'):
            v_borders[left] = Rectangles([
                Rectangle({
                    'bbox': (left, top, left, bottom),
                    'color': c
                })])
        if not self._exist_outer_border(right_rects, right, 'v'):
            v_borders[right] = Rectangles([
                Rectangle({
                    'bbox': (right, top, right, bottom),
                    'color': c
                })])

        return h_borders, v_borders


    @staticmethod
    def _exist_outer_border(rects:Rectangles, target:float, direction:str='h') -> bool:
        ''' Check outer borders: whether target border exists in collected borders.
            ---
            Args:
            - rects: all rects in potential table region
            - target: float, target position of outer border
            - direction: str, 'h'->horizontal border; 'v'->vertical border
        '''
        # no target outer border needed
        if target==None: return True

        # need outer border if no borders exist
        if not rects: return False
        
        # considering direction
        idx = 1 if direction=='h' else 0
        
        # centerline of source borders
        source = round((rects[0].bbox_raw[idx+2] + rects[0].bbox_raw[idx]) / 2.0, 1)
        # max width of source borders
        width = max(map(lambda rect: rect.bbox_raw[idx+2]-rect.bbox_raw[idx], rects))

        target = round(target, 1)
        width = round(width, 1)

        return abs(target-source) <= width


    @staticmethod
    def _check_merged_cells(ref:float, borders:list, direction:str='row'):
        ''' Check merged cells in a row/column. 
            ---
            Args:
              - ref: y (or x) coordinate of horizontal (or vertical) passing-through line
              - borders: list[Rectangles], a list of vertical (or horizontal) rects list in a column (or row)
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
                    _, ref0, _, ref1 = rect.bbox_raw
                else:
                    ref0, _, ref1, _ = rect.bbox_raw

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