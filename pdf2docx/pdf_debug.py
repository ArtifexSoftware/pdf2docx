'''
Plot PDF layout for debug
'''

import fitz
from . import utils
from .pdf_shape import (is_cell_border, is_cell_shading)


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
                - 'layout': plot layout
                - 'shape': plot shape, especially, rectangles
                - 'table': plot table border/shading, i.e. rectangles marked as table type
                - or a combinaton list, e.g. ['layout', 'shape'] plots both layout and shape
    '''
    # function map
    plot_map = {
        'layout': plot_layout,
        'shape': plot_rectangles,
        'table': plot_tables
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


def plot_layout(doc, layout, title):
    '''plot layout with PyMuPDF
       doc: fitz document object
    '''
    # insert a new page with borders
    page = _new_page_with_margin(doc, layout, title)    

    # plot blocks
    for block in layout['blocks']:
        # block border in blue
        blue = utils.getColor('blue')
        r = fitz.Rect(block['bbox'])
        page.drawRect(r, color=blue, fill=None, overlay=False)

        # line border in red
        for line in block.get('lines', []): # TODO: other types, e.g. image, list, table            
            red = utils.getColor('red')
            r = fitz.Rect(line['bbox'])
            page.drawRect(r, color=red, fill=None, overlay=False)

            # span regions
            for span in line.get('spans', []):
                c = utils.getColor('')
                r = fitz.Rect(span['bbox'])
                # image span: diagonal lines
                if 'image' in span:
                    page.drawLine((r.x0, r.y0), (r.x1, r.y1), color=c, width=1)
                    page.drawLine((r.x0, r.y1), (r.x1, r.y0), color=c, width=1)
                    page.drawRect(r, color=c, fill=None, overlay=False)
                 # text span: filled with random color
                else:
                    page.drawRect(r, color=c, fill=c, width=0, overlay=False)


def plot_rectangles(doc, layout, title):
    ''' plot rectangles with PyMuPDF
    '''
    if not layout['rects']: return

    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw rectangle one by one
    for rect in layout['rects']:       
        c = utils.RGB_component(rect['color'])
        c = [_/255.0 for _ in c]
        page.drawRect(rect['bbox'], color=c, fill=c, width=0, overlay=False)


def plot_tables(doc, layout, title):
    ''' plot rectangles with PyMuPDF
    '''
    if not layout['tables']: return

    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw cell one by one
    for table in layout['tables']:
        for rows in table['cells']:
            for cell in rows:
                # ignore merged cells
                if not cell: continue

                # border color and width
                bc = [x/255.0 for x in utils.RGB_component(cell['border-color'][0])]
                w = cell['border-width'][0]

                # shading color
                if cell['bg-color'] != None:
                    sc = [x/255.0 for x in utils.RGB_component(cell['bg-color'])] 
                else:
                    sc = None
                
                # plot cell
                page.drawRect(cell['bbox'], color=bc, fill=sc, width=w, overlay=False)


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
    page.insertText((dL, dT*0.75), title, color=blue, fontsize=dT/2.0)    
    
    return page