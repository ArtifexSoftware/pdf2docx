# -*- coding: utf-8 -*-

'''
PDF operations, e.g. extract rectangles, based on PyMuPDF

@created: 2020-07-22
@author: train8808@gmail.com
'''

import fitz
from . import utils


def new_page_section(doc, width:float, height:float, title:str):
    '''New page with title shown in page center.
        ---
        Args:
          - doc: fitz.Document
          - width, height: page size
          - title: page title shown in page
    '''
    # insert a new page
    page = doc.newPage(width=width, height=height)

    # plot title in page center
    gray = utils.RGB_component_from_name('gray')
    f = 10.0
    page.insertText((width/4.0, (height+height/f)/2.0), title, color=gray, fontsize=height/f)
    return page


def new_page_with_margin(doc, width:float, height:float, margin:tuple, title:str):
    '''Insert a new page and plot margin borders.
        ---
        Args:
          - doc: fitz.Document
          - width, height: page size
          - margin: page margin
          - title: page title shown in page
    '''
    # insert a new page
    page = doc.newPage(width=width, height=height)
    
    # plot borders if page margin is provided
    if margin:
        blue = utils.RGB_component_from_name('blue')
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
    gray = utils.RGB_component_from_name('gray')
    page.insertText((5, 16), title, color=gray, fontsize=15)
    
    return page


def rects_from_annotations(annotations:list):
    ''' Get shapes, e.g. Line, Square, Highlight, from annotations(comment shapes) in PDF page.
        ---
        Args:
          - annotations: a list of PyMuPDF Annot objects, refering to link below
        
        There are stroke and fill properties for each shape, representing border and filling area respectively.
        So, a square annotation with both stroke and fill will be converted to five rectangles here:
        four borders and one filling area.

        read more:
            - https://pymupdf.readthedocs.io/en/latest/annot.html
            - https://pymupdf.readthedocs.io/en/latest/vars.html#annotation-types
    '''
    rects = []
    for annot in annotations:

        # annot type, e.g. (8, 'Highlight')
        key = annot.type[0]

        # color, e.g. {'stroke': [1.0, 1.0, 0.0], 'fill': []}
        c = annot.colors
        sc = utils.RGB_value(c['stroke']) if c['stroke'] else None
        fc = utils.RGB_value(c['fill']) if c['fill'] else None

        # width
        w = annot.border.get('width', 1.0) # width=-1 if not set
        w = 1.0 if w==-1 else w # 1.0 by default            

        # bbox
        rect = annot.rect

        # considering the contributions to text format and table borders, 
        # only the following types are processed.
        # PDF_ANNOT_LINE 3
        # PDF_ANNOT_SQUARE 4
        # PDF_ANNOT_HIGHLIGHT 8
        # PDF_ANNOT_UNDERLINE 9
        # PDF_ANNOT_STRIKEOUT 11
        stroke_bboxes, fill_bboxes = [], []

        # Line: a space of 1.5*w around each border
        # 
        # +----------------------------+
        # |         space              |
        # |     +--------------+       |
        # |     |   border     | 1.5w  |
        # |     +--------------+       |
        # |         1.5w               |
        # +----------------------------+
        # 
        if key==3: 
            stroke_bboxes.append((
                rect.x0+1.5*w,
                rect.y0+1.5*w,
                rect.x1-1.5*w,
                rect.y1-1.5*w
            ))

        # Square: a space of 0.5*w around eah border
        # border rects and filling rects are to be extracted from original square
        # 
        # +------------------------------------------+
        # |                space                     |
        # |      +----------------------------+      |
        # |      |         border             |      |
        # |      |     +--------------+       |      |
        # |            |     fill     |  w    | 0.5w |
        # |      |     +--------------+       |      |
        # |      |            w               |      |
        # |      +----------------------------+      |
        # |                  0.5w                    |
        # +------------------------------------------+
        # 
        elif key==4:
            # stroke rectangles
            if not sc is None:
                x0, y0, x1, y1 = (
                    rect.x0+0.5*w,
                    rect.y0+0.5*w,
                    rect.x1-0.5*w,
                    rect.y1-0.5*w
                )
                stroke_bboxes.extend([
                    (x0, y0, x1, y0+w), # top
                    (x0, y1-w, x1, y1), # bottom
                    (x0, y0, x0+w, y1), # left
                    (x1-w, y0, x1, y1)  # right
                ])

            # fill rectangle
            if not fc is None:
                fill_bboxes.append((
                    rect.x0+1.5*w,
                    rect.y0+1.5*w,
                    rect.x1-1.5*w,
                    rect.y1-1.5*w
                ))
        
        # highlight, underline, strikethrough: on space
        # For these shapes, `annot.rect` is a combination of all sub-highlights, especially 
        # the highlight is continuous in multi-lines.
        # So, `annot.vertices` should be used here, i.e. vertices marked with `+` below.
        #          +------------------------+
        #          +------------------------+
        # +-----------+
        # +-----------+
        # NOTE: Though underline and strikethrough are just lines, the affected areas are same as
        # highlights, as illustrated above.
        # 
        # https://github.com/pymupdf/PyMuPDF/issues/318
        # 
        elif key in (8,9,11):
            points = annot.vertices
            for i in range(int(len(points)/4.0)): # four points in a group
                # highlight: whole bbox
                if key==8:
                    x0, y0 = points[4*i]
                    x1, y1 = points[4*i+3]
                    bbox = (x0, y0, x1, y1)
                
                # underline: bottom edge
                elif key==9:
                    start, end = points[4*i+2], points[4*i+3]
                    bbox = utils.expand_centerline(start, end, w)
                
                # strikethrough: average of top and bottom edge
                else:
                    x0, x1 = points[4*i][0], points[4*i+1][0]
                    y_ = (points[4*i][1]+points[4*i+2][1])/2.0
                    start = x0, y_
                    end = x1, y_
                    bbox = utils.expand_centerline(start, end, w)    
                
                # add shape distributed in each line
                if bbox:
                    stroke_bboxes.append(bbox)

        # create Rectangle
        for bbox in stroke_bboxes:
            rects.append({
                    'bbox': bbox,
                    'color': sc
                })

        for bbox in fill_bboxes:
            rects.append({
                    'bbox': bbox,
                    'color': fc
                })

    return rects


def rects_from_stream(xref_stream:str, matrix:fitz.Matrix):
    ''' Get rectangle shapes by parsing page cross reference stream.

        Note: these shapes are generally converted from pdf source, e.g. highlight, underline, 
        which are different from PDF comments shape.

        ---
        Args:
            - xref_streams: doc._getXrefStream(xref).decode()        
            - matrix: transformation matrix for coordinate system conversion from pdf to fitz 

        --------            
        References:
            - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdf_reference_archive/pdf_reference_1-7.pdf
            - Appendix A for associated operators
            - Section 8.5 Path Construction and Painting
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
            - `re`, `f` or `f*`: fill rectangle path with pre-defined color. If no `f`/`f*` coming after
        `re`, it's a rectangle with borders only (no filling).
        in this case,
            - fill color is yellow (1,1,0)
            - lower left corner: (285.17 500.11)
            - width: 193.97
            - height: 13.44
            - `m`, `l`: draw line from `m` (move to) to `l` (line to)

        Note: coordinates system transformation should be considered if text format
            is set from PDF file with edit mode. 
    '''
    # Graphic States:
    # - working CS is coincident with the absolute origin (0, 0)
    # Refer to PDF reference v1.7 4.2.3 Transformation Metrices
    #                        | a b 0 |
    # [a, b, c, d, e, f] =>  | c b 0 |
    #                        | e f 1 |
    ACS = fitz.Matrix(0.0) # identity matrix
    WCS = fitz.Matrix(0.0)

    # - graphics color: 
    #   - stroking color
    Acs = utils.RGB_value((0.0, 0.0, 0.0)) # stored value
    Wcs = Acs                              # working value
    #   - filling color
    Acf = utils.RGB_value((0.0, 0.0, 0.0))
    Wcf = Acf

    # - stroke width
    Ad = 0.0
    Wd = 0.0

    # In addition to lines, rectangles are also processed with border path
    paths = [] # a list of path, each path is a list of points

    # check xref stream word by word (line always changes)    
    lines = xref_stream.split()
    rects = []
    for (i, line) in enumerate(lines):

        # CS transformation: a b c d e f cm, e.g.
        # 0.05 0 0 -0.05 0 792 cm
        # refer to PDF Reference 4.2.2 Common Transformations for detail
        if line=='cm':
            # update working CS
            components = list(map(float, lines[i-6:i]))
            Mt = fitz.Matrix(*components)
            WCS = Mt * WCS # M' = Mt x M

        # painting color
        # - reset color space
        elif line.upper()=='CS':
            Wcs = utils.RGB_value((0.0, 0.0, 0.0))
            Wcf = utils.RGB_value((0.0, 0.0, 0.0))

        # - gray mode
        elif line.upper()=='G':  # 0 g
            g = float(lines[i-1])
            # nonstroking color, i.e. filling color here
            if line=='g':
                Wcf = utils.RGB_value((g, g, g))
            # stroking color
            else:
                Wcs = utils.RGB_value((g, g, g))

        # - RGB mode
        elif line.upper()=='RG': # 1 1 0 rg
            r, g, b = map(float, lines[i-3:i])

            #  nonstroking color
            if line=='rg':
                Wcf = utils.RGB_value((r, g, b))
            # stroking color
            else:
                Wcs = utils.RGB_value((r, g, b))

        # - CMYK mode
        elif line.upper()=='K': # c m y k K
            c, m, y, k = map(float, lines[i-4:i])
            #  nonstroking color
            if line=='k':
                Wcf = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)
            # stroking color
            else:
                Wcs = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)

        # - set color: either gray, or RGB or CMYK mode
        elif line.upper()=='SC': # c1 c2 ... cn SC
            c = _RGB_from_color_components(lines[i-4:i])
            #  nonstroking color
            if line=='sc':
                Wcf = c
            # stroking color
            else:
                Wcs = c

        # - set color: either gray, or RGB or CMYK mode
        elif line.upper()=='SCN': # c1 c2 ... cn [name] SC
            if utils.is_number(lines[i-1]):
                c = _RGB_from_color_components(lines[i-4:i])
            else:
                c = _RGB_from_color_components(lines[i-5:i-1])

            #  nonstroking color
            if line=='scn':
                Wcf = c
            # stroking color
            else:
                Wcs = c

        # stroke width
        elif line=='w':
            Wd = float(lines[i-1])

        # save or restore graphics state:
        # only consider transformation and color here
        elif line=='q': # save
            ACS = fitz.Matrix(WCS) # copy as new matrix
            Acf = Wcf
            Acs = Wcs
            Ad = Wd
            
        elif line=='Q': # restore
            WCS = fitz.Matrix(ACS) # copy as new matrix
            Wcf = Acf
            Wcs = Acs
            Wd = Ad

        # rectangle block:
        # x y w h re is equivalent to
        # x   y   m
        # x+w y   l
        # x+w y+h l
        # x   y+h l
        # h          # close the path
        elif line=='re': 
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

            # (x, y, w, h) before this line            
            x0, y0, w, h = map(float, lines[i-4:i])
            path = []
            path.append((x0, y0))
            path.append((x0+w, y0))
            path.append((x0+w, y0+h))
            path.append((x0, y0+h))
            path.append((x0, y0))

            paths.append(path)

        # lines: m -> move to point to start a path
        elif line=='m':
            x0, y0 = map(float, lines[i-2:i])
            paths.append([(x0, y0)])
        
        # lines: l -> straight line to point
        elif line=='l':
            x0, y0 = map(float, lines[i-2:i])
            paths[-1].append((x0, y0))

        # close the path
        elif line=='h': 
            for path in paths: _close_path(path)

        # close and stroke the path
        elif line.upper()=='S':
            # close
            if line=='s':
                for path in paths: _close_path(path)

            # stroke path
            for path in paths:
                rects_ = _stroke_path(path, WCS, Wcs, Wd, matrix)
                rects.extend(rects_)

            # reset path
            paths = []

        # fill the path
        elif line in ('f', 'F', 'f*'):            
            for path in paths: 
                # close the path implicitly
                _close_path(path)
            
                # fill path
                rect = _fill_rect_path(path, WCS, Wcf, matrix)
                if rect: rects.append(rect)

            # reset path
            paths = []

        # close, fill and stroke the path
        elif line.upper() in ('B', 'B*'): 
            for path in paths: 
                # close path
                _close_path(path)
                
                # fill path
                rect = _fill_rect_path(path, WCS, Wcf, matrix)
                if rect: rects.append(rect)

                # stroke path
                rects_ = _stroke_path(path, WCS, Wcs, Wd, matrix)
                rects.extend(rects_)

            # reset path
            paths = []

        # TODO: clip the path
        elif line in ('W', 'W*'):
            pass

        # end the path without stroking or filling
        elif line=='n':
            paths = []

    return rects


def _transform_path(path:list, WCS:fitz.Matrix, M0:fitz.Matrix):
    ''' Transform path to page coordinate system. 
        ---
        Args:
        - path: a list of (x,y) point
        - WCS: transformation matrix within pdf
        - M0: tranformation matrix from pdf to fitz

        ```
                              | a b 0 |
        [x' y' 1] = [x y 1] x | c d 0 |
                              | e f 1 |
        ```
    '''
    # transformed PDF -> standard PDF -> PyMuPDF
    M = WCS * M0
    
    # transforming
    res = []
    for (x0, y0) in path:
        P = fitz.Point(x0, y0) * M
        res.append((P.x, P.y))

    return res


def _close_path(path:list):
    if not path: return
    if path[-1]!=path[0]:
        path.append(path[0])


def _stroke_path(path:list, WCS:fitz.Matrix, color:int, width:float, page_height:float):
    ''' Stroke path with a given width. Only horizontal/vertical paths are considered.
    '''
    # CS transformation
    t_path = _transform_path(path, WCS, page_height)

    rects = []
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
            rects.append({
                'bbox': bbox,
                'color': color
            })
    
    return rects


def _fill_rect_path(path:list, WCS:fitz.Matrix, color:int, page_height:float):
    ''' Fill bbox of path with a given color. Only horizontal/vertical paths are considered.
    '''
    # CS transformation
    t_path = _transform_path(path, WCS, page_height)

    # find bbox of path region
    X = [p[0] for p in t_path]
    Y = [p[1] for p in t_path]
    x0, x1 = min(X), max(X)
    y0, y1 = min(Y), max(Y)

    # filled rectangle
    return {
        'bbox': (x0, y0, x1, y1), 
        'color': color
    }


def _RGB_from_color_components(components:list):
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