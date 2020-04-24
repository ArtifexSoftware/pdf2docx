'''
Plot PDF layout for debug
'''

import fitz
from . import utils


def debug_plot(title, plot=True):
    ''' plot layout for debug mode when the following conditions are all satisfied:
          - plot=True
          - layout has been changed: the return value of `func` is True
          - debug mode: kwargs['debug']=True
          - the pdf file to plot layout exists: kwargs['doc'] is not None
    '''
    def wrapper(func):
        def inner(*args, **kwargs):
            # execute function
            res = func(*args, **kwargs)

            # check if plot layout
            debug = kwargs.get('debug', False)
            doc = kwargs.get('doc', None)
            if plot and res and debug and doc is not None:
                layout = args[0]
                plot_layout(doc, layout, title)
        
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
        page.drawRect(r, color=blue, fill=None, width=0.5, overlay=False)

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
                    page.drawRect(r, color=c, fill=c, overlay=False)


def plot_rectangles(doc, layout, title):
    ''' plot rectangles with PyMuPDF
    '''
    if not layout['rects']: return

    # insert a new page
    page = _new_page_with_margin(doc, layout, title)

    # draw rectangle one by one
    for rect in layout['rects']:
        # fill color
        c = utils.RGB_component(rect['color'])
        c = [_/255.0 for _ in c]
        page.drawRect(rect['bbox'], color=c, fill=c, overlay=False)


def _new_page_with_margin(doc, layout, title):
    ''' insert a new page and plot margin borders'''
    # insert a new page
    w, h = layout['width'], layout['height']
    page = doc.newPage(width=w, height=h)
    
    # If layout has been processed, e.g. calculated page margin,
    # plot page margin and title.
    blue = utils.getColor('blue')
    if 'margin' in layout:
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
    
    # otherwise, raw layout, plot title only
    else:
        dL, dT, *_ = layout['blocks'][0]['bbox']
        page.insertText((dL, dT*0.75), title, color=blue, fontsize=dT/2.0)


    return page