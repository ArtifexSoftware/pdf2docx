'''
Parse rectangles and lines, return a list of rect with structure:
{
    'type': int,
    'bbox': (x0, y0, x1, y1),
    'color': utils.RGB_value(c)
}

where, categories of type:
    - not defined   : -1
    - highlight     : 0
    - underline     : 1
    - strike-through: 2
    - table border  : 10
    - cell shading  : 11
'''

import copy
from . import utils


def rects_from_source(xref_stream, height):
    ''' Get rectangle shape by parsing page cross reference stream.

        Note: 
            these shapes are generally converted from pdf source, e.g. highlight, 
            underline, which are different from PDF comments shape.

        xref_streams:
            doc._getXrefStream(xref).decode()        
        height:
            page height for coordinate system conversion
        
        The context meaning of rectangle shape may be:
           - strike through line of text
           - under line of text
           - highlight area of text

        --------
        
        Refer to:
        - Appendix A from PDF reference for associated operators:
          https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdf_reference_archive/pdf_reference_1-7.pdf
        - https://github.com/pymupdf/PyMuPDF/issues/263

        typical mark of rectangle in xref stream:
            /P<</MCID 0>> BDC
            ...
            1 0 0 1 90.0240021 590.380005 cm
            ...
            1 1 0 rg # or 0 g
            ...
            285.17 500.11 193.97 13.44 re f*
            ...
            214 320 m
            249 322 l
            ...
            EMC

        where,
            - `MCID` indicates a Marked content, where rectangles exist
            - `cm` specify a coordinate system transformation, 
               here (0,0) translates to (90.0240021 590.380005)
            - `q`/`Q` save/restores graphic status
            - `rg` / `g` specify color mode: rgb / grey
            - `re`, `f` or `f*`: fill rectangle path with pre-defined color, 
               in this case,
                - fill color is yellow (1,1,0)
                - lower left corner: (285.17 500.11)
                - width: 193.97
                - height: 13.44
            - `m`, `l`: draw line from `m` (move to) to `l` (line to)

        Note: coordinates system transformation should be considered if text format
              is set from PDF file with edit mode. 

        return a list of rectangles:
            [{
                "bbox": (x0, y0, x1, y1),
                "color": sRGB
             }
             {...}
            ]
    '''
    res = []

    # current working CS is coincident with the absolute origin (0, 0)
    # consider scale and translation only
    ACS = [1.0, 1.0, 0.0, 0.0] # scale_x, scale_y, translate_x, tranlate_y
    WCS = [1.0, 1.0, 0.0, 0.0]

    # current graphics color is black
    Ac = utils.RGB_value((0, 0, 0))
    Wc = Ac

    # check xref stream word by word (line always changes)    
    begin_text_setting = False    
    lines = xref_stream.split()
    for (i, line) in enumerate(lines):
        # skip any lines between `BT` and `ET`, 
        # since text seeting has no effects on shape        
        if line=='BT':  # begin text
            begin_text_setting = True
       
        elif line=='ET': # end text
            begin_text_setting = False

        if begin_text_setting:
            continue        

        # CS transformation: a b c d e f cm, e.g.
        # 0.05 0 0 -0.05 0 792 cm
        # refer to PDF Reference 4.2.2 Common Transformations for detail
        if line=='cm':
            # update working CS
            sx = float(lines[i-6])
            sy = float(lines[i-3])
            tx = float(lines[i-2])
            ty = float(lines[i-1])
            WCS = [WCS[0]*sx, WCS[1]*sy, WCS[2]+tx, WCS[3]+ty]

        # painting color
        # gray mode
        elif line=='g': # 0 g
            g = float(lines[i-1])
            Wc = utils.RGB_value((g, g, g))

        # RGB mode
        elif line.upper()=='RG': # 1 1 0 rg
            r, g, b = map(float, lines[i-3:i])
            Wc = utils.RGB_value((r, g, b))

        # save or restore graphics state:
        # only consider transformation and color here
        elif line=='q': # save
            ACS = copy.copy(WCS)
            Ac = Wc
            
        elif line=='Q': # restore
            WCS = copy.copy(ACS)
            Wc = Ac

        # finally, come to the rectangle block
        elif line=='re' and lines[i+1] in ('f', 'f*'):
            # (x, y, w, h) before this line
            x0, y0, w, h = map(float, lines[i-4:i])            

            # ATTENTION: 
            # top/bottom, left/right is relative to the positive direction of CS, 
            # while a reverse direction may be performed, so be careful when calculating
            # the corner points. 
            # Coordinates in the transformed PDF CS:
            #   y1 +----------+
            #      |          | h
            #   y0 +----w-----+
            #      x0        x1
            # 
            x1 = x0 + w
            y1 = y0 + h

            # With the transformations, a bottom-left point may be transformed from a top-left
            # point in the original CS, e.g. a reverse scale with scale_y = -1
            # Coordinates in the original PDF CS:
            #   _y1 +----------+             _y0 +----------+
            #       |          |      or         |          |
            #   _y0 +----------+             _y1 +----------+
            #      _x0        _x1               _x0        _x1
            #
            # So, we have to calculate all the four coordinate components first,
            # then determin the required corner points
            # 
            sx, sy, tx, ty = WCS
            _x0 = sx*x0 + tx
            _y0 = sy*y0 + ty
            _x1 = sx*x1 + tx
            _y1 = sy*y1 + ty

            # For PyMuPDF context, we need top-left and bottom-right point
            # top means the larger one in (_y0, _y1), and it's true for left/right
            X0 = min(_x0, _x1)
            Y0 = max(_y0, _y1)
            X1 = max(_x0, _x1)
            Y1 = min(_y0, _y1)

            # add rectangle, meanwhile convert bbox to PyMuPDF coordinates system
            res.append({
                'type': -1,
                'bbox': (X0, height-Y0, X1, height-Y1), 
                'color': Wc
            })
        # line is also considered as rectangle by adding a height
        elif line=='m' and lines[i+3]=='l':
            # start point
            x_s, y_s = map(float, lines[i-2:i])
            # end point
            x_e, y_e = map(float, lines[i+1:i+3])

            # consider horizontal line only
            if y_s != y_e: continue

            # transformate to original PDF CS
            sx, sy, tx, ty = WCS            
            x0 = sx*x_s + tx
            y0 = sy*y_s + ty
            x1 = sx*x_e + tx
            y1 = sy*y_e + ty

            # convert line to rectangle with a default height 0.5pt:
            # move start point to top-left corner of a rectangle
            # move end point to bottom-right corner of rectangle
            h = 0.5
            y0 += h/2.0
            y1 -= h/2.0

            # bbox in PyMuPDF coordinates system
            res.append({
                'type': -1,
                'bbox': (x0, height-y0, x1, height-y1), 
                'color': Wc
            })
 
    return res


def rects_from_annots(annots):
    ''' get annotations(comment shapes) from PDF page
        Note: 
            consider highlight, underline, strike-through-line only. 

        annots:
            a list of PyMuPDF Annot objects        
    '''
    res = []

    # map rect type from PyMuPDF
    # Annotation types:
    # https://pymupdf.readthedocs.io/en/latest/vars/#annotationtypes    
    # PDF_ANNOT_HIGHLIGHT 8
    # PDF_ANNOT_UNDERLINE 9
    # PDF_ANNOT_SQUIGGLY 10
    # PDF_ANNOT_STRIKEOUT 11
    type_map = { 8: 0, 9: 1, 11: 2}

    for annot in annots:

        # consider highlight, underline, strike-through-line only.
        # e.g. annot.type = (8, 'Highlight')
        if not annot.type[0] in (8,9,11): 
            continue
        
        # color, e.g. {'stroke': [1.0, 1.0, 0.0], 'fill': []}
        c = annot.colors.get('stroke', (0,0,0)) # black by default

        # convert rect coordinates
        rect = annot.rect

        res.append({
            'type': type_map[annot.type[0]],
            'bbox': (rect.x0, rect.y0, rect.x1, rect.y1),
            'color': utils.RGB_value(c)
        })

    return res


def rect_to_style(rect, span_bbox):
    ''' text style based on the position between rectangle and span
        rect: {'type': int, 'bbox': (,,,), 'color': int}
    '''

    # if the type of rect is unknown (-1), recognize type first 
    # based on rect and the span it applying to
    if rect['type']==-1:
        # region height
        h_rect = rect['bbox'][3] - rect['bbox'][1]
        h_span = span_bbox[3] - span_bbox[1]

        # distance to span bootom border
        d = span_bbox[3] - rect['bbox'][1]

        # the height of rect is large enough?
        # yes, it's highlight
        if h_rect > 0.75*h_span:
            rect['type'] = 0

        # near to bottom of span? yes, underline
        elif d < 0.25*h_span:
            rect['type'] = 1

        # near to center of span? yes, strike-through-line
        elif 0.35*h_span < d < 0.75*h_span:
            rect['type'] = 2

        # unknown style
        else:
            pass

    # check rect type again
    if rect['type']==-1:
        style = {}
    else:
        style =  {
            'type': rect['type'],
            'color': rect['color']
        }
    return style


def set_cell_border(rect):
    rect['type'] = 10

def set_cell_shading(rect):
    rect['type'] = 11

def is_cell_border(rect):
    return rect.get('type', -1) == 10

def is_cell_shading(rect):
    return rect.get('type', -1) == 11