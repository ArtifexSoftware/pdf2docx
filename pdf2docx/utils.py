import random
import fitz
from fitz.utils import getColorList, getColorInfoList
from docx.enum.text import WD_COLOR_INDEX

# border margin
DM = 1.0

# inch to point
ITP = 72.0

# tolerant rectangle area
DR = fitz.Rect(-DM, -DM, DM, DM) / 2.0


def getColor(name=None):
    '''get a named RGB color (or random color) from fitz predefined colors'''
    # get color index
    if name and name.upper() in getColorList():
        pos = getColorList().index(name.upper())
    else:
        pos = random.randint(0, len(getColorList())-1)
        
    c = getColorInfoList()[pos]
    return (c[1] / 255.0, c[2] / 255.0, c[3] / 255.0)


def RGB_component(srgb):
    '''srgb value to R,G,B components, e.g. 16711680 -> (255, 0, 0)'''
    # decimal to hex: 0x...
    s = hex(srgb)[2:].zfill(6)
    return [int(s[i:i+2], 16) for i in [0, 2, 4]]


def RGB_value(rgb):
    '''RGB components to decimal value, e.g. (1,0,0) -> 16711680'''
    res = 0
    for (i,x) in enumerate(rgb):
        res += int(x*(16**2-1)) * 16**(4-2*i)
    return int(res)


def to_Highlight_color(sRGB):
    '''pre-defined color index for highlighting text with python-docx'''
    # part of pre-defined colors
    color_map = {        
        RGB_value((1,0,0)): WD_COLOR_INDEX.RED,
        RGB_value((0,1,0)): WD_COLOR_INDEX.BRIGHT_GREEN,
        RGB_value((0,0,1)): WD_COLOR_INDEX.BLUE,
        RGB_value((1,1,0)): WD_COLOR_INDEX.YELLOW,
        RGB_value((1,0,1)): WD_COLOR_INDEX.PINK,
        RGB_value((0,1,1)): WD_COLOR_INDEX.TURQUOISE
    }
    return color_map.get(sRGB, WD_COLOR_INDEX.YELLOW)


def get_main_bbox(bbox_1, bbox_2, threshold=0.95):
    ''' If the intersection of bbox_1 and bbox_2 exceeds the threshold, return the union of
        these two bbox-es; else return None.
    '''
    # rects
    b1 = fitz.Rect(bbox_1)
    b2 = fitz.Rect(bbox_2)
    b = b1 & b2

    # areas    
    a1, a2, a = b1.getArea(), b2.getArea(), b.getArea()

    # no intersection
    if not b: return None

    # Note: if b1 and b2 intersects with only an edge, b is not empty but b.getArea()=0
    # so give a small value when they're intersected but the area is zero
    factor = a/min(a1,a2) if a else 1e-6
    if factor >= threshold:
        u = b1 | b2
        return tuple([round(x,1) for x in (u.x0, u.y0, u.x1, u.y1)])
    else:
        return None


def parse_font_name(font_name):
    '''parse raw font name extracted with pymupdf, e.g.
        BCDGEE+Calibri-Bold, BCDGEE+Calibri
    '''
    font_name = font_name.split('+')[-1]
    font_name = font_name.split('-')[0]
    return font_name


def is_char_in_rect(char, rect):
    ''' whether a char locates in a rect, or
        they have a intersection larger than a half of the char bbox

        char: a dict with keys bbox
        rect: fitz.Rect instance
    '''
    # char in rect?
    c_rect = fitz.Rect(char['bbox'])
    if c_rect in rect:
        return True

    # intersection?
    intsec = c_rect & rect
    return intsec.width > 0.5*c_rect.width


def is_vertical_aligned(bbox1, bbox2, horizontal=True, factor=0.0):
    ''' check whether two boxes have enough intersection in vertical direction.
        vertical direction is perpendicular to reading direction

        - bbox1, bbox2: bbox region defined by top-left, bottom-right corners,
                       e.g. (x0, y0, x1, y1).
        - horizontal  : is reading direction from left to right? True by default.
        - factor      : threshold of overlap ratio, the larger it is, the higher
                       probability the two bbox-es are aligned.

        An enough intersection is defined based on the minimum width of two boxes:
        L1+L2-L>factor*min(L1,L2)
    '''
    if not bbox1 or not bbox2:
        return False

    if horizontal: # reading direction: x
        L1 = bbox1[2]-bbox1[0]
        L2 = bbox2[2]-bbox2[0]
        L = max(bbox1[2], bbox2[2]) - min(bbox1[0], bbox2[0])
    else:
        L1 = bbox1[3]-bbox1[1]
        L2 = bbox2[3]-bbox2[1]
        L = max(bbox1[3], bbox2[3]) - min(bbox1[1], bbox2[1])

    return L1+L2-L>=factor*max(L1,L2)


def is_horizontal_aligned(bbox1, bbox2, horizontal=True, factor=0.0):
    ''' it is opposite to vertical align situation
        - bbox1, bbox2: bbox region defined by top-left, bottom-right corners,
                       e.g. (x0, y0, x1, y1).
        - horizontal  : is reading direction from left to right? True by default.
        - factor      : threshold of overlap ratio, the larger it is, the higher
                        probability the two bbox-es are aligned.
    '''
    return is_vertical_aligned(bbox1, bbox2, not horizontal, factor)


def in_same_row(bbox1, bbox2):
    ''' Check whether two boxes are in same row/line:
        - yes: the bottom edge of each box is lower than the centerline of the other one;
        - otherwise, not in same row.

        Note the difference with `is_horizontal_aligned`. They may not in same line, though
        aligned horizontally.
    '''
    if not bbox1 or not bbox2:
        return False

    c1 = (bbox1[1] + bbox1[3]) / 2.0
    c2 = (bbox2[1] + bbox2[3]) / 2.0

    # Note y direction under PyMuPDF context
    return c1<bbox2[3] and c2<bbox1[3]


def check_concurrent_points(p1, p2, square_tolerance=0.0):
    ''' check if p1(x1,y1) and p2(x2,y2) are concurrent points with given tolerance
    '''
    x1, y1 = p1
    x2, y2 = p2
    return (x1-x2)**2+(y1-y2)**2 <= square_tolerance
