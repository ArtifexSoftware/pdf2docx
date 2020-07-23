# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.

@created: 2020-07-22
@author: train8808@gmail.com
---

{
    'type': int
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border_color': (sRGB,,,), # top, right, bottom, left
            'bg_color': sRGB,
            'border_width': (,,,),
            'merged_cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'blocks': [
                text blocks
            ]
        }, # end of cell

        None,  # merged cell

        ...,   # more cells
    ], # end of row

    ...] # more rows    
}

'''

import fitz

from .Cell import Cell
from ..shape.Rectangle import Rectangle
from ..common.Block import Block
from ..common.base import RectType
from ..common.utils import utils


class TableBlock(Block):
    '''Text block.'''
    def __init__(self, raw: dict={}) -> None:
        super(TableBlock, self).__init__(raw)

        self.cells = [] # type: list[list[Cell]]
        for row in raw.get('cells', []):            
            row_obj = [Cell(cell) for cell in row] # type: list [Cell]
            self.cells.append(row_obj)

        # explicit table by default
        self.set_explicit_table_block()


    def plot(self, page, style=False, content=True):
        '''Plot table block, i.e. cell/line/span.
            ---
            Args:
              - page: fitz.Page object
              - style: plot cell style if True, e.g. border width, shading
              - content: plot text blocks if True
        '''
        for row in self.cells:
            for cell in row:
                # ignore merged cells
                if not cell: continue            
                
                # plot cell style
                cell.plot(page, style, content)

    
    def parse_structure(self, rects:list[Rectangle]):
        ''' Parse table structure from rects in table border/shading type.
        '''
        # --------------------------------------------------
        # group horizontal/vertical borders
        # --------------------------------------------------
        h_borders, v_borders = self._collect_explicit_borders(rects)
        if not h_borders or not v_borders:
            return

        # sort
        rows = sorted(h_borders)
        cols = sorted(v_borders)
            
        # --------------------------------------------------
        # parse table structure, especially the merged cells
        # -------------------------------------------------- 
        # check merged cells in each row
        merged_cells_rows = []  # type: list[list[int]]
        for i, row in enumerate(rows[0:-1]):
            ref_y = (row+rows[i+1])/2.0
            ordered_v_borders = [v_borders[k] for k in cols]
            row_structure = self._check_merged_cells(ref_y, ordered_v_borders, 'row')
            merged_cells_rows.append(row_structure)

        # check merged cells in each column
        merged_cells_cols = []  # type: list[list[int]]
        for i, col in enumerate(cols[0:-1]):
            ref_x = (col+cols[i+1])/2.0
            ordered_h_borders = [h_borders[k] for k in rows]
            col_structure = self._check_merged_cells(ref_x, ordered_h_borders, 'column')        
            merged_cells_cols.append(col_structure)

        # --------------------------------------------------
        # parse table properties
        # --------------------------------------------------
        cells = []  # type: list[list[Cell]]
        n_rows = len(merged_cells_rows)
        n_cols = len(merged_cells_cols)
        for i in range(n_rows):
            cells_in_row = []    # type: list[Cell]
            for j in range(n_cols):
                # if current cell is merged horizontally or vertically, set None.
                # actually, it will be counted in the top-left cell of the merged range.
                if merged_cells_rows[i][j]==0 or merged_cells_cols[j][i]==0:
                    cells_in_row.append(None)
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
                top = h_borders[rows[i]][0]
                bottom = h_borders[rows[i+n_row]][0]
                left = v_borders[cols[j]][0]
                right = v_borders[cols[j+n_col]][0]

                w_top = top.bbox.y1-top.bbox.y0
                w_right = right.bbox.x1-right.bbox.x0
                w_bottom = bottom.bbox.y1-bottom.bbox.y0
                w_left = left.bbox.x1-left.bbox.x0

                # cell bbox
                bbox = (cols[j], rows[i], cols[j+n_col], rows[i+n_row])

                # shading rect in this cell
                # modify the cell bbox from border center to inner region
                inner_bbox = (bbox[0]+w_left/2.0, bbox[1]+w_top/2.0, bbox[2]-w_right/2.0, bbox[3]-w_bottom/2.0)
                shading_rect = self._get_rect_with_bbox(inner_bbox, rects, threshold=0.9)
                if shading_rect:
                    shading_rect.type = RectType.SHADING # set shaing type
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

                cells_in_row.append(Cell(cell_dict))
                    
            # one row finished
            # check table: the first cell in first row MUST NOT be None
            if i==0 and cells_in_row[0]==None:
                return

            cells.append(cells_in_row)

        # update table
        self.update((cols[0], rows[0], cols[-1], rows[-1]))
        self.cells = cells






    def _collect_explicit_borders(self, rects:list[Rectangle]) -> tuple[dict[float,list[Rectangle]]]:
        ''' Collect explicit borders in horizontal and vertical groups respectively.'''
        borders = list(filter(
            lambda rect: rect.type==RectType.BORDER, rects))
        h_borders = {} # type: dict [float, list[Rectangle]]
        v_borders = {} # type: dict [float, list[Rectangle]]
        h_outer = []   # type: list[float]
        v_outer = []   # type: list[float]

        for rect in borders:
            # group horizontal borders in each row
            if rect.bbox.width > rect.bbox.height:
                # row centerline
                y = round((rect.bbox.y0 + rect.bbox.y1) / 2.0, 1)
                if y in h_borders:
                    h_borders[y].append(rect)
                else:
                    h_borders[y] = [rect]
                
                # candidates for vertical outer border
                v_outer.extend([rect.bbox.x0, rect.bbox.x1])

            # group vertical borders in each column
            else:
                # column centerline
                x = round((rect.bbox.x0 + rect.bbox.x1) / 2.0, 1)
                if x in v_borders:
                    v_borders[x].append(rect)
                else:
                    v_borders[x] = [rect]
                
                # candidates for horizontal outer border
                h_outer.extend([rect.bbox.y0, rect.bbox.y1])

        # at least 2 inner borders exist
        if len(h_borders)+len(v_borders)<2:
            return None, None

        # Note: add dummy borders if no outer borders exist
        # check whether outer borders exists in collected borders
        if h_borders:
            top_rects = h_borders[min(h_borders)]
            bottom_rects = h_borders[max(h_borders)]
            left   = min(v_outer)
            right  = max(v_outer)
        else:
            top_rects = []
            bottom_rects = []
            left   = None
            right  = None

        if v_borders:
            left_rects = v_borders[min(v_borders)]
            right_rects = v_borders[max(v_borders)]
            top   = min(h_outer)
            bottom  = max(h_outer)
        else:
            left_rects = []
            right_rects = []
            top   = None
            bottom  = None    

        if not self._exist_outer_border(top, top_rects, 'h'):
            h_borders[top] = [Rectangle({
                    'bbox': (left, top, right, top),
                    'color': utils.RGB_value((1,1,1))
                })
            ]
        if not self._exist_outer_border(bottom, bottom_rects, 'h'):
            h_borders[bottom] = [Rectangle({
                    'bbox': (left, bottom, right, bottom),
                    'color': utils.RGB_value((1,1,1))
                })
            ]
        if not self._exist_outer_border(left, left_rects, 'v'):
            v_borders[left] = [Rectangle({
                    'bbox': (left, top, left, bottom),
                    'color': utils.RGB_value((1,1,1))
                })
            ]
        if not self._exist_outer_border(right, right_rects, 'v'):
            v_borders[right] = [Rectangle({
                    'bbox': (right, top, right, bottom),
                    'color': utils.RGB_value((1,1,1))
                })
            ]

        return h_borders, v_borders

    
    @staticmethod
    def _exist_outer_border(target:float, borders:list[Rectangle], direction:str='h') -> bool:
        ''' Check outer borders: whether target border exists in collected borders.
            ---
            Args:
              - target: float, target position of outer border
              - borders: list, a list of rects representing borders
              - direction: str, 'h'->horizontal border; 'v'->vertical border
        '''
        # no target outer border needed
        if target==None:
            return True

        # need outer border if no borders exist
        if not borders:
            return False
        
        if direction=='h':
            # centerline of source borders
            source = round((borders[0]['bbox'][1] + borders[0]['bbox'][3]) / 2.0, 1)
            # max width of source borders
            width = max(map(lambda rect: rect['bbox'][3]-rect['bbox'][1], borders))
        else:
            source = round((borders[0]['bbox'][0] + borders[0]['bbox'][2]) / 2.0, 1)
            width = max(map(lambda rect: rect['bbox'][2]-rect['bbox'][0], borders))

        target = round(target, 1)
        width = round(width, 1)

        return abs(target-source) <= width


    @staticmethod
    def _check_merged_cells(ref:float, borders:list[list[Rectangle]], direction:str='row') -> list[int]:
        ''' Check merged cells in a row/column. 

            Taking cells in a row (direction=0) for example, give a horizontal line (y=ref) passing through this row, 
            check the intersection with vertical borders. The n-th cell is merged if no intersection with the n-th border.

            ---
            Args:
              - ref: y (or x) coordinate of horizontal (or vertical) passing-through line
              - borders: a list of vertical (or horizontal) rects list in a column (or row)
              - direction: 
                'row' - check merged cells in row; 
                'column' - check merged cells in a column
        '''

        res = []
        for rects in borders[0:-1]:
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

    
    def _get_rect_with_bbox(bbox:tuple[float], rects:list[Rectangle], threshold:float) -> Rectangle:
        '''Get rect within given bbox.'''
        target_rect = fitz.Rect(bbox)
        for rect in rects:
            intersection = target_rect & rect.bbox
            if intersection.getArea() / target_rect.getArea() >= threshold:
                res = rect
                break
        else:
            res = None
        return res
