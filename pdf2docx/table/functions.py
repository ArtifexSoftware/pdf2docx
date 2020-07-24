# -*- coding: utf-8 -*-

'''
Table Processing methods.
'''

import fitz
from ..common.base import RectType
from ..common import utils
from ..shape.Rectangle import Rectangle


def collect_explicit_borders(rects:list[Rectangle]) -> tuple[dict[float,list[Rectangle]]]:
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

    if not _exist_outer_border(top, top_rects, 'h'):
        h_borders[top] = [Rectangle({
                'bbox': (left, top, right, top),
                'color': utils.RGB_value((1,1,1))
            })
        ]
    if not _exist_outer_border(bottom, bottom_rects, 'h'):
        h_borders[bottom] = [Rectangle({
                'bbox': (left, bottom, right, bottom),
                'color': utils.RGB_value((1,1,1))
            })
        ]
    if not _exist_outer_border(left, left_rects, 'v'):
        v_borders[left] = [Rectangle({
                'bbox': (left, top, left, bottom),
                'color': utils.RGB_value((1,1,1))
            })
        ]
    if not _exist_outer_border(right, right_rects, 'v'):
        v_borders[right] = [Rectangle({
                'bbox': (right, top, right, bottom),
                'color': utils.RGB_value((1,1,1))
            })
        ]

    return h_borders, v_borders


def check_merged_cells(ref:float, borders:list[list[Rectangle]], direction:str='row') -> list[int]:
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


def get_rect_with_bbox(bbox:tuple[float], rects:list[Rectangle], threshold:float) -> Rectangle:
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


def set_table_borders(rects:list[Rectangle], border_threshold:float=6.0) -> bool:
    ''' Detect table borders from rects.

        Cell borders are detected based on the experiences that:
            - compared to cell shading, the size of cell border never exceeds 6 pt
            - compared to text format, cell border always has intersection with other rects

        Note: cell shading is determined after the table structure is parsed from these cell borders.
    '''
    # Get all rects with on condition: size < 6 Pt
    thin_rects = [] # type: list[Rectangle]
    for rect in rects:
        x0, y0, x1, y1 = rect.bbox_raw
        if min(x1-x0, y1-y0) <= border_threshold:
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

