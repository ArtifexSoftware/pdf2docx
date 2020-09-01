# -*- coding: utf-8 -*-

import random

import fitz
from fitz.utils import getColorList, getColorInfoList
from .base import PlotControl


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


def compare_layput(filename_source, filename_target, filename_output, threshold=0.7):
    ''' Compare layout of two pdf files:
        It's difficult to have an exactly same layout of blocks, but ensure they
        look like each other. So, with `extractWORDS()`, all words with bbox 
        information are compared.

        ```
        (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        ```
    '''
    # fitz document
    source = fitz.open(filename_source) # type: fitz.Document
    target = fitz.open(filename_target) # type: fitz.Document

    # check count of pages
    # --------------------------
    if len(source) != len(target):
        msg='Page count is inconsistent with source file.'
        print(msg)
        return False
    
    flag = True
    errs = []
    for i, (source_page, target_page) in enumerate(zip(source, target)):

        # check position of each word
        # ---------------------------
        source_words = source_page.getText('words')
        target_words = target_page.getText('words')

        # sort by word
        source_words.sort(key=lambda item: (item[4], round(item[1],1), round(item[0],1)))
        target_words.sort(key=lambda item: (item[4], round(item[1],1), round(item[0],1)))

        if len(source_words) != len(target_words):
            msg='Words count is inconsistent with source file.'
            print(msg)
            return False

        # check each word and bbox
        for sample, test in zip(source_words, target_words):
            source_rect, target_rect = fitz.Rect(sample[0:4]), fitz.Rect(test[0:4])

            # draw bbox based on source layout
            source_page.drawRect(source_rect, color=(1,1,0), overlay=True) # source position
            source_page.drawRect(target_rect, color=(1,0,0), overlay=True) # current position

            # check bbox word by word: ignore small bbox, e.g. single letter bbox
            if not get_main_bbox(source_rect, target_rect, threshold):
                flag = False
                errs.append((f'{sample[4]} ===> {test[4]}', target_rect, source_rect))
        
    # save and close
    source.save(filename_output)
    target.close()
    source.close()

    # outputs
    for word, target_rect, source_rect in errs:
        print(f'Word "{word}": \nsample bbox: {source_rect}\ncurrent bbox: {target_rect}\n')

    return flag