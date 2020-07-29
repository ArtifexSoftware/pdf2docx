# -*- coding: utf-8 -*-

import random

import fitz
from fitz.utils import getColorList, getColorInfoList
from .base import PlotControl

# border margin
DM = 1.0

# inch to point
ITP = 72.0

# tolerant rectangle area
DR = fitz.Rect(-DM, -DM, DM, DM) / 2.0


def is_number(str_number):
    try:
        float(str_number)
    except:
        return False
    else:
        return True


def RGB_component_from_name(name:str=''):
    '''Get a named RGB color (or random color) from fitz predefined colors, e.g. 'red' -> (1.0,0.0,0.0).'''
    # get color index
    if name and name.upper() in getColorList():
        pos = getColorList().index(name.upper())
    else:
        pos = random.randint(0, len(getColorList())-1)
        
    c = getColorInfoList()[pos]
    return (c[1] / 255.0, c[2] / 255.0, c[3] / 255.0)


def RGB_component(srgb:int):
    '''srgb value to R,G,B components, e.g. 16711680 -> (255, 0, 0)'''
    # decimal to hex: 0x...
    s = hex(srgb)[2:].zfill(6)
    return [int(s[i:i+2], 16) for i in [0, 2, 4]]


def RGB_value(rgb:list):
    '''RGB components to decimal value, e.g. (1,0,0) -> 16711680'''
    res = 0
    for (i,x) in enumerate(rgb):
        res += int(x*(16**2-1)) * 16**(4-2*i)
    return int(res)


def CMYK_to_RGB(c:float, m:float, y:float, k:float, cmyk_scale:float=100):
    ''' CMYK components to GRB value.'''
    r = (1.0 - c / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    g = (1.0 - m / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    b = (1.0 - y / float(cmyk_scale)) * (1.0 - k / float(cmyk_scale))
    res = RGB_value((r, g, b)) # type: int
    return res


def get_main_bbox(bbox_1:fitz.Rect, bbox_2:fitz.Rect, threshold:float=0.95):
    ''' If the intersection of bbox_1 and bbox_2 exceeds the threshold, return the union of
        these two bbox-es; else return None.
    '''
    # areas
    b = bbox_1 & bbox_2
    a1, a2, a = bbox_1.getArea(), bbox_2.getArea(), b.getArea()

    # no intersection
    if not b: return fitz.Rect()

    # Note: if bbox_1 and bbox_2 intersects with only an edge, b is not empty but b.getArea()=0
    # so give a small value when they're intersected but the area is zero
    factor = a/min(a1,a2) if a else 1e-6
    if factor >= threshold:
        return bbox_1 | bbox_2
    else:
        return fitz.Rect()


def is_vertical_aligned(bbox1:fitz.Rect, bbox2:fitz.Rect, horizontal:bool=True, factor:float=0.0):
    ''' Check whether two boxes have enough intersection in vertical direction, i.e. perpendicular to reading direction.
        An enough intersection is defined based on the minimum width of two boxes:
        L1+L2-L>factor*min(L1,L2)
        ---
        Args:
        - bbox1, bbox2: bbox region in fitz.Rect type.
        - horizontal  : is reading direction from left to right? True by default.
        - factor      : threshold of overlap ratio, the larger it is, the higher probability the two bbox-es are aligned.

        
    '''
    if not bbox1 or not bbox2:
        return False

    if horizontal: # reading direction: x
        L1 = bbox1.x1-bbox1.x0
        L2 = bbox2.x1-bbox2.x0
        L = max(bbox1.x1, bbox2.x1) - min(bbox1.x0, bbox2.x0)
    else:
        L1 = bbox1.y1-bbox1.y0
        L2 = bbox2.y1-bbox2.y0
        L = max(bbox1.y1, bbox2.y1) - min(bbox1.y0, bbox2.y0)

    res = L1+L2-L>=factor*max(L1,L2) # type: bool

    return res


def is_horizontal_aligned(bbox1:fitz.Rect, bbox2:fitz.Rect, horizontal:bool=True, factor:float=0.0):
    ''' Check whether two boxes have enough intersection in horizontal direction, i.e. the reading direction.
        An enough intersection is defined based on the minimum width of two boxes:
        L1+L2-L>factor*min(L1,L2)
        ---
        Args:
        - bbox1, bbox2: bbox region in fitz.Rect type.
        - horizontal  : is reading direction from left to right? True by default.
        - factor      : threshold of overlap ratio, the larger it is, the higher probability the two bbox-es are aligned.
    '''
    # it is opposite to vertical align situation
    return is_vertical_aligned(bbox1, bbox2, not horizontal, factor)


def in_same_row(bbox1:fitz.Rect, bbox2:fitz.Rect):
    ''' Check whether two boxes are in same row/line:
        - yes: the bottom edge of each box is lower than the centerline of the other one;
        - otherwise, not in same row.

        Note the difference with `is_horizontal_aligned`. They may not in same line, though
        aligned horizontally.
    '''
    if not bbox1 or not bbox2:
        return False

    c1 = (bbox1.y0 + bbox1.y1) / 2.0
    c2 = (bbox2.y0 + bbox2.y1) / 2.0

    # Note y direction under PyMuPDF context
    res = c1<bbox2.y1 and c2<bbox1.y1 # type: bool
    return res


def expand_centerline(start: list, end: list, width:float=2.0):
    ''' convert centerline to rectangle shape.
        centerline is represented with start/end points: (x0, y0), (x1, y1).
    '''
    h = width / 2.0
    x0, y0 = start
    x1, y1 = end

    # consider horizontal or vertical line only
    if x0==x1 or y0==y1:
        res = (x0-h, y0-h, x1+h, y1+h)
    else:
        res = None

    return res


def new_page_section(doc:fitz.Document, width:float, height:float, title):
    '''New page with title shown in page center.'''
    # insert a new page
    page = doc.newPage(width=width, height=height)

    # plot title in page center
    gray = RGB_component_from_name('gray')
    f = 10.0
    page.insertText((width/4.0, (height+height/f)/2.0), title, color=gray, fontsize=height/f)
    return page


def new_page_with_margin(doc:fitz.Document, width:float, height:float, margin:tuple, title:str):
    '''Insert a new page and plot margin borders.'''
    # insert a new page
    page = doc.newPage(width=width, height=height)
    
    # plot borders if page margin is provided
    if margin:
        blue = RGB_component_from_name('blue')
        args = {
            'color': blue,
            'width': 0.5
        }
        dL, dR, dT, dB = margin
        page.drawLine((dL, 0), (dL, height), **args) # left border
        page.drawLine((width-dR, 0), (width-dR, height), **args) # right border
        page.drawLine((0, dT), (width, dT), **args) # top
        page.drawLine((0, height-dB), (width, height-dB), **args) # bottom

    # plot title at the top-left corner
    gray = RGB_component_from_name('gray')
    page.insertText((5, 16), title, color=gray, fontsize=15)
    
    return page


def debug_plot(title:str, plot:bool=True, category:PlotControl=PlotControl.LAYOUT):
    ''' Plot layout / shapes for debug mode when the following conditions are all satisfied:
          - plot=True
          - layout has been changed: the return value of `func` is True
          - debug mode: kwargs['debug']=True
          - the pdf file to plot layout exists: kwargs['doc'] is not None        
        ---        
        Args:
          - title: page title
          - plot: plot layout/shape if true
          - category: PlotControl, what to plot
    '''
    def wrapper(func):
        def inner(*args, **kwargs):
            # execute function
            res = func(*args, **kwargs)

            # check if plot layout
            debug = kwargs.get('debug', False)
            doc = kwargs.get('doc', None)
            layout = args[0] # assert Layout object
            if plot and res and debug and doc is not None:                
                layout.plot(doc, title, category)
            return layout
        return inner
    return wrapper