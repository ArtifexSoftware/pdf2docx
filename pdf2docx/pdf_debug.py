'''
Plot PDF layout for debug
'''

import fitz
from . import utils
from .pdf_shape import (is_cell_border, is_cell_shading)
from .pdf_block import (is_text_block, is_image_block, is_table_block, is_implicit_table_block, is_explicit_table_block)


def debug_plot(title, plot=True, category='layout'):
    ''' plot layout / shapes for debug mode when the following conditions are all satisfied:
          - plot=True
          - layout has been changed: the return value of `func` is True
          - debug mode: kwargs['debug']=True
          - the pdf file to plot layout exists: kwargs['doc'] is not None
        
        args:
            - title: page title
            - plot: plot layout/shape if true
            - category: 
                - 'layout': plot all blocks
                - 'table' : plot explicit table blocks only
                - 'implicit_table' : plot implicit table blocks only
                - 'shape' : plot rectangle shapes                
                - or a combinaton list, e.g. ['layout', 'shape'] plots both layout and shape
    '''
    # function map
    plot_map = {
        'layout': plot_layout,
        'table' : plot_explicit_table_blocks,
        'implicit_table': plot_implicit_table_blocks,
        'shape' : plot_rectangles        
    }
    if isinstance(category, str): category = [category]

    def wrapper(func):
        def inner(*args, **kwargs):
            # execute function
            res = func(*args, **kwargs)

            # check if plot layout
            debug = kwargs.get('debug', False)
            doc = kwargs.get('doc', None)
            if plot and res and debug and doc is not None:
                layout = args[0]                
                # plot layout or shapes                           
                for c in category:
                    if c in plot_map:
                        plot_map[c](doc, layout, title)        
        return inner
    return wrapper


def plot_explicit_table_blocks(doc, layout, title):
    ''' plot table blocks layout with PyMuPDF.'''
    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # plot table block one by one
    for block in layout['blocks']:

        # consider explicit table blocks only
        if not is_explicit_table_block(block): continue

        # plot each cells: format and text
        _plot_table_block(page, block, style=True, content=False)


def plot_implicit_table_blocks(doc, layout, title):
    ''' plot table blocks layout with PyMuPDF.'''
    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # plot table block one by one
    for block in layout['blocks']:

        # consider implicit table blocks only
        if not is_implicit_table_block(block): continue

        # plot each cells: format and text
        _plot_table_block(page, block, style=False, content=False)


def plot_layout(doc, layout, title):
    ''' plot all blocks layout with PyMuPDF
    '''
    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw each block
    for block in layout['blocks']:

        # text and image block
        if is_text_block(block) or is_image_block(block):
            _plot_text_block(page, block)
        
        # table block
        elif is_table_block(block):
            _plot_table_block(page, block, style=False, content=True)


def plot_rectangles(doc, layout, title):
    ''' plot rectangle shapes with PyMuPDF
    '''
    if not layout['rects']: return

    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw rectangle one by one
    for rect in layout['rects']:       
        c = utils.RGB_component(rect['color'])
        c = [_/255.0 for _ in c]
        page.drawRect(rect['bbox'], color=c, fill=c, width=0, overlay=False)


def new_page_section(doc, layout, title):
    '''New page with title shown in page center.'''
    # insert a new page
    w, h = layout['width'], layout['height']
    page = doc.newPage(width=w, height=h)

    # plot title in page center
    gray = utils.getColor('gray')
    f = 10.0
    page.insertText((w/4.0, (h+h/f)/2.0), title, color=gray, fontsize=h/f)


def _new_page_with_margin(doc, layout, title):
    ''' insert a new page and plot margin borders'''
    # insert a new page
    w, h = layout['width'], layout['height']
    page = doc.newPage(width=w, height=h)
    
    # page margin must be calculated already
    blue = utils.getColor('blue')
    args = {
        'color': blue,
        'width': 0.5
    }
    dL, dR, dT, dB = layout['margin']
    page.drawLine((dL, 0), (dL, h), **args) # left border
    page.drawLine((w-dR, 0), (w-dR, h), **args) # right border
    page.drawLine((0, dT), (w, dT), **args) # top
    page.drawLine((0, h-dB), (w, h-dB), **args) # bottom

    # plot title within the top margin
    gray = utils.getColor('gray')
    page.insertText((dL, dT*0.66), title, color=gray, fontsize=dT/3.0)    
    
    return page


def _plot_text_block(page, block):
    '''Plot text/image block, i.e. block/line/span area, in PDF page'''
    # block border in blue
    blue = utils.getColor('blue')    
    if is_image_block(block):
        _plot_image(page, block['bbox'], blue)
    else:
        page.drawRect(block['bbox'], color=blue, fill=None, overlay=False)

    # lines and spans
    _plot_lines_and_spans(page, block.get('lines', []))


def _plot_table_block(page, block, style=True, content=True):
    '''Plot table block, i.e. cell/line/span, in PDF page.'''
    for rows in block['cells']:
        for cell in rows:
            # ignore merged cells
            if not cell: continue            
            
            # plot cell style
            if style:
                # border color and width
                bc = [x/255.0 for x in utils.RGB_component(cell['border-color'][0])]
                w = cell['border-width'][0]

                # shading color
                if cell['bg-color'] != None:
                    sc = [x/255.0 for x in utils.RGB_component(cell['bg-color'])] 
                else:
                    sc = None
                page.drawRect(cell['bbox'], color=bc, fill=sc, width=w, overlay=False)
            
            # or just an illustration
            else:
                bc = (1,0,0) if is_explicit_table_block(block) else (0.6,0.7,0.8)
                page.drawRect(cell['bbox'], color=bc, fill=None, width=1, overlay=False)

            # plot blocks in cell
            if content:
                for cell_block in cell['blocks']:
                    _plot_text_block(page, cell_block)


def _plot_lines_and_spans(page, lines):
    '''Plot lines and spans bbox'''    
    for line in lines:
        # line border in red
        red = utils.getColor('red')
        r = fitz.Rect(line['bbox'])
        page.drawRect(r, color=red, fill=None, overlay=False)

        # span regions
        for span in line.get('spans', []):
            c = utils.getColor('')
            bbox = span['bbox']

            # image span: diagonal lines
            if 'image' in span:
                _plot_image(page, bbox, c)
            
            # text span: filled with random color
            else:
                page.drawRect(bbox, color=c, fill=c, width=0, overlay=False)


def _plot_image(page, bbox, color):
    '''Plot image bbox with diagonal lines'''
    x0, y0, x1, y1 = bbox
    page.drawLine((x0, y0), (x1, y1), color=color, width=1)
    page.drawLine((x0, y1), (x1, y0), color=color, width=1)
    page.drawRect(bbox, color=color, fill=None, overlay=False)