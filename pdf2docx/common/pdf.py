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


def recover_pixmap(doc:fitz.Document, item:list):
    '''Restore pixmap with soft mask considered.
        ---
        - doc: fitz document
        - item: an image item got from page.getImageList()

        Read more:
        - https://pymupdf.readthedocs.io/en/latest/document.html#Document.getPageImageList        
        - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-handle-stencil-masks
        - https://github.com/pymupdf/PyMuPDF/issues/670
    '''
    # data structure of `item`:
    # (xref, smask, width, height, bpc, colorspace, ...)
    x = item[0]  # xref of PDF image
    s = item[1]  # xref of its /SMask

    # base image
    pix = fitz.Pixmap(doc, x)

    # reconstruct the alpha channel with the smask if exists
    if s > 0:        
        # copy of base image, with an alpha channel added
        pix = fitz.Pixmap(pix, 1)  
        
        # create pixmap of the /SMask entry
        ba = bytearray(fitz.Pixmap(doc, s).samples)
        for i in range(len(ba)):
            if ba[i] > 0: ba[i] = 255
        pix.setAlpha(ba)

    # we may need to adjust something for CMYK pixmaps here -> 
    # recreate pixmap in RGB color space if necessary
    # NOTE: pix.colorspace may be None for images with alpha channel values only
    if pix.colorspace and not pix.colorspace.name in (fitz.csGRAY.name, fitz.csRGB.name):
        pix = fitz.Pixmap(fitz.csRGB, pix)

    return pix


def paths_from_annotations(page:fitz.Page):
    ''' Get shapes, e.g. Line, Square, Highlight, from annotations(comment shapes) in PDF page.
        ---
        Args:
        - page: fitz.Page, current page
        
        There are stroke and fill properties for each shape, representing border and filling area respectively.
        So, a square annotation with both stroke and fill will be converted to five rectangles here:
        four borders and one filling area.

        read more:
            - https://pymupdf.readthedocs.io/en/latest/annot.html
            - https://pymupdf.readthedocs.io/en/latest/vars.html#annotation-types
    '''
    res = []
    for annot in page.annots():

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
            x0 = rect.x0+1.5*w
            x1 = rect.x1-1.5*w
            y0 = y1 = (rect.y0+rect.y1)/2.0
            path = _add_stroke_line((x0, y0), (x1, y1), sc, w)
            res.append(path)

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
                x0, y0 = rect.x0+w, rect.y0+w
                x1, y1 = rect.x1-w, rect.y1-w
                path = _add_stroke_rect((x0, y0), (x1, y1), sc, w)
                res.append(path)

            # fill rectangle
            if not fc is None:
                d = 1.5*w
                x0, y0 = rect.x0+d, rect.y0+d
                x1, y1 = rect.x1-d, rect.y1-d
                path = _add_fill_rect((x0, y0), (x1, y1), fc)
                res.append(path)
        
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

                    # NOTE: this indded a stroke for PyMuPDF -> no fill color but stroke color !!
                    path = _add_fill_rect((x0, y0), (x1, y1), sc)
                    res.append(path)

                else:                
                    # underline: bottom edge
                    if key==9:
                        start, end = points[4*i+2], points[4*i+3]                        
                    
                    # strikethrough: average of top and bottom edge
                    else:
                        x0, x1 = points[4*i][0], points[4*i+1][0]
                        y_ = (points[4*i][1]+points[4*i+2][1])/2.0
                        start = x0, y_
                        end = x1, y_

                    path = _add_stroke_line(start, end, sc, w)
                    res.append(path)

    return res


def paths_from_stream(page:fitz.Page):
    ''' Get paths, e.g. highlight, underline and table borders, from page source contents.
        ---
        Args:
        - page: fitz.Page, current page

        The page source is represented as contents of stream object. For example,
        ```
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
            426 630 425 630 422 630 c
            ...
            EMC
        ```
        where,
        - `cm` specify a coordinate system transformation, here (0,0) translates to (90.0240021 590.380005)
        - `q`/`Q` save/restores graphic status
        - `rg` / `g` specify color mode: rgb / grey
        - `re`, `f` or `f*`: fill rectangle path with pre-defined color
        - `m` (move to) and `l` (line to) defines a path
        - `c` draw cubic Bezier curve with given control points
        
        In this case,
        - a rectangle with:
            - fill color is yellow (1,1,0)
            - lower left corner: (285.17 500.11)
            - width: 193.97
            - height: 13.44
        - a line from (214, 320) to (249, 322)
        - a Bezier curve with control points (249,322), (426,630), (425,630), (422,630)

        Read more:        
        - https://github.com/pymupdf/PyMuPDF/issues/263
        - https://github.com/pymupdf/PyMuPDF/issues/225
        - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdf_reference_archive/pdf_reference_1-7.pdf
    '''
    # Each object in PDF has a cross-reference number (xref):
    # - to get its source contents: `doc.xrefObject()` or low level API `doc._getXrefString()`; but for stream objects, only the non-stream part is returned
    # - to get the stream data: `doc.xrefStream(xref)` or low level API `doc._getXrefStream(xref)`
    # - the xref for a page object itself: `page.xref`
    # - all stream xref contained in one page: `page.getContents()`
    # - combine all stream object contents together: `page.readContents()` with PyMuPDF>=1.17.0
    # 
    # Clean contents first:
    # syntactically correct, standardize and pretty print the contents stream
    page.cleanContents()
    xref_stream = page.readContents().decode(encoding="ISO-8859-1") 

    # transformation matrix for coordinate system conversion from pdf to fitz
    # NOTE: transformation matrix converts PDF CS to UNROTATED PyMuPDF page CS, 
    #       so need further rotation transformation to the real page CS (applied in Object BBox)
    # https://github.com/pymupdf/PyMuPDF/issues/619
    matrix = page.transformationMatrix

    # Graphic States: working CS is coincident with the absolute origin (0, 0)
    # Refer to PDF reference v1.7 4.2.3 Transformation Metrics
    #                        | a b 0 |
    # [a, b, c, d, e, f] =>  | c b 0 |
    #                        | e f 1 |
    ACS = [fitz.Matrix(0.0)] # identity matrix
    WCS = fitz.Matrix(0.0)

    # Graphics color: 
    # - color space: PDF Reference Section 4.5 Color Spaces
    # NOTE: it should have to calculate color value under arbitrary color space, but it's really hard work for now.
    # So, consider device color space only like DeviceGray, DeviceRGB, DeviceCMYK, and set black for all others.
    device_space = True
    color_spaces = _check_device_cs(page)

    # - stroking color
    Acs = [utils.RGB_value((0.0, 0.0, 0.0))] # stored value -> stack
    Wcs = Acs[0]                             # working value
    # - filling color
    Acf = [utils.RGB_value((0.0, 0.0, 0.0))]
    Wcf = Acf[0]

    # Stroke width
    Ad = [0.0]
    Wd = Ad[0]

    # collecting paths: each path is a list of points
    paths = []           # a list of path

    # clip path
    Acp = [] # stored clipping path
    Wcp = [] # working clipping path

    # Check line by line
    # Cleaned by `page.cleanContents()`, operator and operand are aligned in a same line;
    # otherwise, have to check stream contents word by word (line always changes)
    lines = xref_stream.splitlines()

    res = [] # final results
    for line in lines:

        words = line.split()
        if not words: continue

        op = words[-1] # operator always at the end after page.cleanContents()

        # -----------------------------------------------
        # Color Operators: PDF Reference Table 4.24
        # -----------------------------------------------
        # - set color space:
        #   color_space_name cs  # specify color space
        #   c1 c2 ... SC/SCN     # components under defined color space
        if op.upper()=='CS':
            Wcs = utils.RGB_value((0.0, 0.0, 0.0))
            Wcf = utils.RGB_value((0.0, 0.0, 0.0))

            # Consider normal device cs only
            device_space = color_spaces.get(words[0], False)

        # - set color: color components under specified color space
        elif op.upper()=='SC': # c1 c2 ... cn SC
            c = _RGB_from_color_components(words[0:-1], device_space)
            #  non-stroking color
            if op=='sc':
                Wcf = c
            # stroking color
            else:
                Wcs = c

        # - set color: color components under specified color space
        elif op.upper()=='SCN': # c1 c2 ... cn [name] SC
            if utils.is_number(words[-2]):
                c = _RGB_from_color_components(words[0:-1], device_space)
            else:
                c = _RGB_from_color_components(words[0:-2], device_space)

            #  non-stroking color
            if op=='scn':
                Wcf = c
            # stroking color
            else:
                Wcs = c

        # - DeviceGray space, equal to:
        # /DeviceGray cs
        # c sc
        elif op.upper()=='G':  # 0 g
            g = float(words[0])
            # nonstroking color, i.e. filling color here
            if op=='g':
                Wcf = utils.RGB_value((g, g, g))
            # stroking color
            else:
                Wcs = utils.RGB_value((g, g, g))

        # - DeviceRGB space
        elif op.upper()=='RG': # 1 1 0 rg
            r, g, b = map(float, words[0:-1])

            #  nonstroking color
            if op=='rg':
                Wcf = utils.RGB_value((r, g, b))
            # stroking color
            else:
                Wcs = utils.RGB_value((r, g, b))

        # - DeviceCMYK space
        elif op.upper()=='K': # c m y k K
            c, m, y, k = map(float, words[0:-1])
            #  nonstroking color
            if op=='k':
                Wcf = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)
            # stroking color
            else:
                Wcs = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)        

        # -----------------------------------------------
        # Graphics State Operators: PDF References Table 4.7
        # -----------------------------------------------
        # CS transformation: a b c d e f cm, e.g.
        # 0.05 0 0 -0.05 0 792 cm
        # refer to PDF Reference 4.2.2 Common Transformations for detail
        elif op=='cm':
            # update working CS
            components = list(map(float, words[0:-1]))
            Mt = fitz.Matrix(*components)
            WCS = Mt * WCS # M' = Mt x M

        # stroke width
        elif op=='w': # 0.5 w
            Wd = float(words[0])

        # save or restore graphics state:
        # only consider transformation and color here
        elif op=='q': # save
            ACS.append(fitz.Matrix(WCS)) # copy as new matrix
            Acf.append(Wcf)
            Acs.append(Wcs)
            Ad.append(Wd)
            Acp.append(Wcp)
            
        elif op=='Q': # restore
            WCS = fitz.Matrix(ACS.pop()) # copy as new matrix
            Wcf = Acf.pop()
            Wcs = Acs.pop()
            Wd = Ad.pop()
            Wcp = Acp.pop()

        # -----------------------------------------------
        # Path Construction Operators: PDF References Table 4.9
        # -----------------------------------------------
        # rectangle block:
        # x y w h re is equivalent to
        # x   y   m
        # x+w y   l
        # x+w y+h l
        # x   y+h l
        # h          # close the path
        elif op=='re': 
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
            x0, y0, w, h = map(float, words[0:-1])
            path = []
            path.append((x0, y0))
            path.append((x0+w, y0))
            path.append((x0+w, y0+h))
            path.append((x0, y0+h))
            path.append((x0, y0))

            paths.append(path)

        # path: m -> move to point to start a path
        elif op=='m': # x y m
            x0, y0 = map(float, words[0:-1])
            paths.append([(x0, y0)])
        
        # path: l -> straight line to point
        elif op=='l': # x y l            
            x0, y0 = map(float, words[0:-1])
            paths[-1].append((x0, y0))            

        # path: c -> cubic Bezier curve with control points
        elif op in ('c', 'v', 'y'):
            coords = list(map(float, words[0:-1]))
            P = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
            x0, y0 = paths[-1][-1]

            # x1 y1 x2 y2 x3 y3 c -> (x1,y1), (x2,y2) as control points
            if op=='c': 
                P.insert(0, (x0, y0))

            # x2 y2 x3 y3 v -> (x0,y0), (x2,y2) as control points
            elif op=='v': 
                P.insert(0, (x0, y0))
                P.insert(0, (x0, y0))
            
            # x1 y1 x3 y3 y -> (x1,y1), (x3,y3) as control points
            else: 
                P.insert(0, (x0, y0))
                P.append(P[-1])
            
            # calculate points on Bezier points with parametric equation
            bezier = _bezier_paths(P, segments=5)
            paths[-1].extend(bezier)

        # close the path
        elif op=='h': 
            for path in paths: _close_path(path)

        # -----------------------------------------------
        # Path-painting Operatores: PDF Reference Table 4.10
        # -----------------------------------------------
        # close and stroke the path
        elif op.upper()=='S':
            # close
            if op=='s':
                for path in paths: _close_path(path)

            # stroke path
            for path in paths:
                p = _stroke_path(path, WCS, Wcs, Wd, matrix)
                res.append(p)

            # reset path
            paths = []

        # fill the path
        elif line in ('f', 'F', 'f*'):            
            for path in paths:
                # close the path implicitly
                _close_path(path)
            
                # fill path
                p = _fill_rect_path(path, WCS, Wcf, matrix)
                res.append(p)

            # reset path
            paths = []

        # close, fill and stroke the path
        elif op.upper() in ('B', 'B*'): 
            for path in paths:
                # close path
                _close_path(path)
                
                # fill path
                p = _fill_rect_path(path, WCS, Wcf, matrix)
                res.append(p)

                # stroke path
                p = _stroke_path(path, WCS, Wcs, Wd, matrix)
                res.append(p)

            # reset path
            paths = []

        # TODO: clip the path
        # https://stackoverflow.com/questions/17003171/how-to-identify-which-clip-paths-apply-to-a-path-or-fill-in-pdf-vector-graphics
        elif line in ('W', 'W*'):
            Wcp = paths[-1] if paths else []
            paths = []

        # end the path without stroking or filling
        elif op=='n':
            paths = []

    return res


def _check_device_cs(page:fitz.Page):
    '''Get all color space name used in current page and check if they're device based color space.'''
    # pdf document
    doc = page.parent

    # default device based cs
    cs = {
        '/DeviceGray': True, 
        '/DeviceRGB' : True, 
        '/DeviceCMYK': True
    }

    # content of page object, e.g.
    # <<
    # ...
    # /Resources <<
    #     ...
    #     /ColorSpace <<
    #     /Cs6 14 0 R
    #     >>
    # >>
    # /Rotate 0
    # /Type /Page
    # >>
    obj_contents = doc.xrefObject(page.xref)

    cs_found = False
    for line_ in obj_contents.splitlines():
        line = line_.strip()

        # check start/end of color space block
        if not cs_found and line.startswith('/ColorSpace'):
            cs_found = True
            continue

        if not cs_found:
            continue
        elif line=='>>':
            break

        # now within cs block
        cs_name, xref, *_ = line.split()

        # check color space referring to device-dependent color space, e.g. /CSp /DeviceRGB
        if xref in cs:
            cs[cs_name] = cs[xref]
            continue

        # check color space definition array, e.g. /Cs6 14 0 R
        cs[cs_name] = _is_device_cs(int(xref), doc)

    return cs


def _is_device_cs(xref, doc:fitz.Document):
    '''Check whether object xref is a device based color space.
    '''
    # cs definition
    obj_contents = doc.xrefObject(xref)

    # for now, just check /ICCBased CS:
    # it's treated as a device based cs if /Device[Gray|RGB|CMYK] exists in /Alternate.
    # 
    # [ /ICCBased 15 0 R ]
    # 
    # <<
    #   /Alternate /DeviceRGB
    #   /Filter /FlateDecode
    #   /Length 2597
    #   /N 3
    # >>
    if '/ICCBased' in obj_contents:
        name, x, *_ = obj_contents[1:-1].strip().split()
        ICC_contents = doc.xrefObject(int(x))
        return '/Alternate /Device' in ICC_contents

    # ignore all other color spaces, may include if facing associated cases
    return False


def _bezier_paths(points, segments=5):
    '''calculate points on Bezier curve.
        ---
        Args:
        - points: a list of 4 points, [P0, P1, P2, P3], of which P1 and P2 are control points
        - segments: int, count of sample points
    '''
    # R(t) = (1-t)**3*P0 + 3*t*(1-t)**2*P1 + 3*t**2*(1-t)*P2 + t**3*P3  (0<=t<=1)
    res = []
    for i in range(1, segments+1):
        t = i/segments
        factors = ((1-t)**3, 3*t*(1-t)**2, 3*t**2*(1-t), t**3)

        x, y = 0.0, 0.0
        for P, f in zip(points, factors):
            x += P[0]*f
            y += P[1]*f
        res.append((x,y))

    return res


def _transform_path(path:list, WCS:fitz.Matrix, M0:fitz.Matrix):
    ''' Transform path to page coordinate system. 
        ---
        Args:
        - path: a list of (x,y) point
        - WCS: transformation matrix within pdf
        - M0: tranformation matrix from pdf to fitz (unrotated page CS)

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
    if path[-1]!=path[0]: path.append(path[0])


def _stroke_path(path:list, WCS:fitz.Matrix, color:int, width:float, M0:fitz.Matrix):
    ''' Stroke path.'''
    # CS transformation
    t_path = _transform_path(path, WCS, M0)

    # NOTE: the directly extracted width is affected by the transformation matrix, especially the scale components.
    # an average width is used for simplification
    fx, fy = abs(WCS.a), abs(WCS.d) # use absolute value!!
    w = width*(fx+fy)/2.0

    return {
        'stroke': True,
        'points': t_path,
        'color' : color,
        'width' : w
    }


def _fill_rect_path(path:list, WCS:fitz.Matrix, color:int, M0:fitz.Matrix):
    ''' Fill path.'''
    # CS transformation
    t_path = _transform_path(path, WCS, M0)

    return {
        'stroke': False,
        'points': t_path,
        'color' : color
    }


def _RGB_from_color_components(components:list, device_cs:bool=True):
    ''' Get color based on color components and color space.
        ---
        Args:
        - components: color components in various color space, e.g. grey, RGB, CMYK
        - device_cs: whether this is under device color space
    '''
    # black by default
    color = utils.RGB_value((0.0,0.0,0.0)) # type: int

    # NOTE: COnsider only the device color space, i.e. Gray, RGB, CMYK.
    if not device_cs:
        return color

    # if device cs, decide the cs with length of color components
    num = len(components)

    # CMYK mode
    if num==4:
        c, m, y, k = map(float, components)
        color = utils.CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)

    # RGB mode
    elif num==3:
        r, g, b = map(float, components)
        color = utils.RGB_value((r, g, b))

    # gray mode
    elif num==1:
        g = float(components[0])
        color = utils.RGB_value((g,g,g))

    return color


def _add_stroke_line(start:list, end:list, color:int, width:float):
    '''add stroke line defined with start and end points.'''
    return {
        'stroke': True,
        'points': [start, end],
        'color' : color,
        'width' : width
        }

        
def _add_stroke_rect(top_left:list, bottom_right:list, color:int, width:float):
    '''add stroke lines from rect defined with top-left and bottom-right points.'''
    x0, y0 = top_left
    x1, y1 = bottom_right

    points = [
        (x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)
        ]
    return {
        'stroke': True,
        'points': points,
        'color' : color,
        'width' : width
        }


def _add_fill_rect(top_left:list, bottom_right:list, color:int):
    '''add fill from rect defined with top-left and bottom-right points.'''
    x0, y0 = top_left
    x1, y1 = bottom_right

    points = [
        (x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)
        ]
    return {
        'stroke': False,
        'points': points,
        'color' : color
        }
