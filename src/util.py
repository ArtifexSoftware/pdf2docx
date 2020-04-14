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


def parse_font_name(font_name):
    '''parse raw font name extracted with pymupdf, e.g.
        BCDGEE+Calibri-Bold, BCDGEE+Calibri
    '''
    font_name = font_name.split('+')[-1]
    font_name = font_name.split('-')[0]
    return font_name


def is_word_in_rect(word, rect):
    ''' word format: (x0, y0, x1, y1, 'word', 6, 1, 1)
        word in words may come together with a punctuation, e.g. 'word.',
        but the rect applies only on the 'word' part, so the rect can't cover the
        whole word, even though a tolerance is included. On the other hand, using 
        intersection may be an overkill.

        so, a compromise is they have intersection, but the gap is small
    '''
    w_rect = fitz.Rect(word[:4])

    # word in rect?
    if w_rect in rect:
        return True
    else:
        # intersection?
        b1 = w_rect.intersects(rect)
        
        # the gap small enough?
        if w_rect.x1 > rect.x1:
            gap = w_rect.x1 - rect.x1
        else:
            gap = abs(rect.x0 - w_rect.x0)
        b2 = gap / (rect.x1-rect.x0) < 0.15

        return b1 and b2


def rect_to_style(rect, span_bbox):
    ''' text style based on the position between rectangle and span
        rect: {'bbox': (,,,), 'color': int}
    '''
    # region height
    h_rect = rect['bbox'][3] - rect['bbox'][1]
    h_span = span_bbox[3] - span_bbox[1]

    # distance to span bootom border
    d = span_bbox[3] - rect['bbox'][1]

    # the height of rect is large enough?
    # yes, it's highlight
    if h_rect > 0.75*h_span:
        style = {
            'type': 0,
            'color': rect['color']
        }
    # near to bottom of span? yes, underline
    elif d < 0.25*h_span:
        style = {
            'type': 1,
            'color': rect['color']
        }
    # near to center of span? yes, strike-through-line
    elif 0.35*h_span < d < 0.75*h_span:
        style = {
            'type': 2,
            'color': rect['color']
        }
    # unknown style
    else:
        style = None

    return style


def is_end_sentence(text):
    '''simple rule to check the completence of text
       - sentence delimiter at the end of a sentence
    '''
    text = text.strip()
    if not text:
        return True # keep empy line

    return text[-1].endswith(('.', '?', '!', ':'))

def is_start_sentence(text):
    text = text.strip()
    if not text:
        return True

    # generally not starts with a digit 
    elif text[0].isdigit():
        return False		

    # not starts with a low case alphabet
    else:
        return not text[0].islower() # conservatively

def is_vertical_aligned(bbox1, bbox2, horizontal=True, factor=0.5):
    '''check whether two boxes have enough intersection in vertical direction.
       vertical direction is perpendicular to reading direction

       an enough intersection is defined based on the minimum width of two boxes:
       L1+L2-L>factor*min(L1,L2)
    '''
    if horizontal: # reading direction: x
        L1 = bbox1[2]-bbox1[0]
        L2 = bbox2[2]-bbox2[0]
        L = max(bbox1[2], bbox2[2]) - min(bbox1[0], bbox2[0])
    else:
        L1 = bbox1[3]-bbox1[1]
        L2 = bbox2[3]-bbox2[1]
        L = max(bbox1[3], bbox2[3]) - min(bbox1[1], bbox2[1])

    return L1+L2-L>factor*min(L1,L2)


def is_horizontal_aligned(bbox1, bbox2, horizontal=True):
    '''it is opposite to vertical align situation'''
    return is_vertical_aligned(bbox1, bbox2, not horizontal)
