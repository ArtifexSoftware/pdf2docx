# -*- coding: utf-8 -*-

'''
docx operation methods based on python-docx.
'''

from io import BytesIO
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.enum.text import WD_COLOR_INDEX
from docx.image.exceptions import UnrecognizedImageError
from docx.table import _Cell

from .utils import RGB_value, DM


def to_Highlight_color(sRGB:int):
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


def reset_paragraph_format(p, line_spacing:float=1.05):
    ''' Reset paragraph format, especially line spacing.
        ---
        Args:
          - p: docx paragraph instance
        
        Two kinds of line spacing, corresponding to the setting in MS Office Word:
        - line_spacing=1.05: single or multiple
        - line_spacing=Pt(1): exactly
    '''
    pf = p.paragraph_format
    pf.line_spacing = line_spacing # single by default
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.left_indent = Pt(0)
    pf.right_indent = Pt(0)
    pf.widow_control = True
    return pf


def add_stop(p, pos:float, current_pos:float):
    ''' Set horizontal position in current position with tab stop.
        ---
        Args: 
          - p: docx paragraph instance
          - pos: target position in Pt
          - current_pos: current position in Pt

        Note: multiple tab stops may exist in paragraph, 
              so tabs are added based on current position and target position.         
    '''
    # ignore small pos
    if pos < Pt(DM): return

    # add tab to reach target position
    for t in p.paragraph_format.tab_stops:
        if t.position < current_pos:
            continue
        elif t.position<pos or abs(t.position-pos)<=Pt(DM):
            p.add_run().add_tab()
        else:
            break


def add_image(p, byte_image, width):
    ''' Add image to paragraph.
        ---
        Args:
          - p: docx paragraph instance
          - byte_image: bytes for image source
          - width: image width
    '''
    # TODO: docx.image.exceptions.UnrecognizedImageError
    docx_span = p.add_run()
    try:
        docx_span.add_picture(BytesIO(byte_image), width=Pt(width))
    except UnrecognizedImageError:
        print('TODO: Unrecognized Image.')
        return
    
    # exactly line spacing will destroy image display, so set single line spacing instead
    p.paragraph_format.line_spacing = 1.00


def indent_table(table, indent:float):
    ''' indent table.
        ---
        Args:
          - table: docx table object
          - indent: indent value, the basic unit is 1/20 pt
    '''
    tbl_pr = table._element.xpath('w:tblPr')
    if tbl_pr:
        e = OxmlElement('w:tblInd')
        e.set(qn('w:w'), str(20*indent)) # basic unit 1/20 pt for openxml 
        e.set(qn('w:type'), 'dxa')
        tbl_pr[0].append(e)


def set_cell_margins(cell:_Cell, **kwargs):
    ''' Set cell margins. Provided values are in twentieths of a point (1/1440 of an inch).
        ---
        Args:
          - cell:  actual cell instance you want to modify
          - kwargs: a dict with keys: top, bottom, start, end
        
        Usage:
          - set_cell_margins(cell, top=50, start=50, bottom=50, end=50)
        
        Read more: 
          - https://blog.csdn.net/weixin_44312186/article/details/104944773
          - http://officeopenxml.com/WPtableCellMargins.php
    '''
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
 
    for m in ['top', 'start', 'bottom', 'end']:
        if m in kwargs:
            node = OxmlElement("w:{}".format(m))
            node.set(qn('w:w'), str(kwargs.get(m)))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
 
    tcPr.append(tcMar)


def set_cell_shading(cell:_Cell, RGB_value):
    ''' set cell background-color.
        ---
        Args:
          - cell:  actual cell instance you want to modify

        https://stackoverflow.com/questions/26752856/python-docx-set-table-cell-background-and-text-color
    '''
    c = hex(RGB_value)[2:].zfill(6)
    cell._tc.get_or_add_tcPr().append(parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), c)))


def set_cell_border(cell:_Cell, **kwargs):
    '''
    Set cell`s border.
    
    Reference:
     - https://stackoverflow.com/questions/33069697/how-to-setup-cell-borders-with-python-docx
     - https://blog.csdn.net/weixin_44312186/article/details/104944110

    Usage:
    ```
        _set_cell_border(
            cell,
            top={"sz": 12, "val": "single", "color": "#FF0000", "space": "0"},
            bottom={"sz": 12, "color": "#00FF00", "val": "single"},
            start={"sz": 24, "val": "dashed", "shadow": "true"},
            end={"sz": 12, "val": "dashed"},
        )
    ```
    '''
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    # check for tag existence, if none found, then create one
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)

    # list over all available tags
    for edge in ('start', 'top', 'end', 'bottom', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = 'w:{}'.format(edge)

            # check for tag existence, if none found, then create one
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)

            # looks like order of attributes is important
            for key in ["sz", "val", "color", "space", "shadow"]:
                if key in edge_data:
                    element.set(qn('w:{}'.format(key)), str(edge_data[key]))


def set_vertical_cell_direction(cell:_Cell, direction:str='btLr'):
    '''Set vertical text direction for cell.
        ---
        Args:
          - direction: tbRl -- top to bottom, btLr -- bottom to top
        
        https://stackoverflow.com/questions/47738013/how-to-rotate-text-in-table-cells
    '''
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    textDirection = OxmlElement('w:textDirection')
    textDirection.set(qn('w:val'), direction)  # btLr tbRl
    tcPr.append(textDirection)
