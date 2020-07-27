# -*- coding: utf-8 -*-

'''
Shape related methods.
'''


from ..common import utils
from .Rectangle import Rectangle


def transform_path(path: list, WCS: list, height: float):
    ''' Transform path to page coordinate system. 
        ---
        Args:
            - path: a list of (x,y) point
            - WCS: transformation matrix
            - height: page height for converting CS from pdf to fitz
    '''
    res = []
    sx, sy, tx, ty = WCS
    for (x0, y0) in path:
        # transformate to original PDF CS                    
        x = sx*x0 + tx
        y = sy*y0 + ty

        # pdf to PyMuPDF CS
        y = height-y
        
        res.append((x, y))

    return res


def close_path(path:list):
    if not path: return
    if path[-1]!=path[0]:
        path.append(path[0])


def stroke_path(path: list, WCS: list, color: int, width: float, page_height: float):
    ''' Stroke path with a given width. Only horizontal/vertical paths are considered.
    '''
    # CS transformation
    t_path = transform_path(path, WCS, page_height)

    rects = [] # type: list[Rectangle]
    for i in range(len(t_path)-1):
        # start point
        x0, y0 = t_path[i]
        # end point
        x1, y1 = t_path[i+1]

        # ensure from top-left to bottom-right
        if x0>x1 or y0>y1:
            x0, y0, x1, y1 = x1, y1, x0, y0

        # convert line to rectangle
        bbox = utils.expand_centerline((x0, y0), (x1, y1), width)
        if bbox:
            rect = Rectangle({
                'bbox': bbox,
                'color': color
            })
            rects.append(rect)
    
    return rects


def fill_rect_path(path:list, WCS:list, color:int, page_height:float):
    ''' Fill bbox of path with a given color. Only horizontal/vertical paths are considered.
    '''
    # CS transformation
    t_path = transform_path(path, WCS, page_height)

    # find bbox of path region
    X = [p[0] for p in t_path]
    Y = [p[1] for p in t_path]
    x0, x1 = min(X), max(X)
    y0, y1 = min(Y), max(Y)

    # filled rectangle
    rect = Rectangle({
        'bbox': (x0, y0, x1, y1), 
        'color': color
    })
        
    return rect


def RGB_from_color_components(components:list):
    ''' Detect color mode from given components and calculate the RGB value.
        ---
        Args:
            - components: a list with 4 elements
    '''
    color = utils.RGB_value((0.0,0.0,0.0)) # type: int

    # CMYK mode
    if all(map(utils.is_number, components)):
        c, m, y, k = map(float, components)
        color = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)

    # RGB mode
    elif all(map(utils.is_number, components[1:])):
        r, g, b = map(float, components[1:])
        color = utils.RGB_value((r, g, b))

    # gray mode
    elif utils.is_number(components[-1]):
        g = float(components[-1])
        color = utils.RGB_value((g,g,g))

    return color

