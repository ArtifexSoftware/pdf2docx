# -*- coding: utf-8 -*-

import random
from collections import deque
import fitz
from fitz.utils import getColorList, getColorInfoList
from . import pdf


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
    ''' srgb value to R,G,B components, e.g. 16711680 -> (255, 0, 0).
        
        Equal to PyMuPDF built-in method: [int(255*x) for x in fitz.sRGB_to_pdf(x)]
    '''
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


def debug_plot(title:str):
    ''' Plot the returned objects of inner function.
        ---        
        Args:
        - title: page title
    '''
    def wrapper(func):
        def inner(*args, **kwargs):
            # execute function
            objects = func(*args, **kwargs)

            # check if plot layout
            debug = kwargs.get('debug', False)
            doc = kwargs.get('doc', None)
            layout = args[0] # Layout object

            if objects and debug and doc is not None:                
                # create a new page
                page = pdf.new_page(doc, layout.width, layout.height, title)

                # plot objects, e.g. text blocks, shapes, tables...
                objects.plot(page)

            return objects
        return inner
    return wrapper


def graph_BFS(graph):
    '''Breadth First Search graph (may be disconnected graph), return a list of connected components.
        ---
        Args:
        - graph: GRAPH represented by adjacent list, [set(1,2,3), set(...), ...]
    '''
    # search graph
    # NOTE: generally a disconnected graph
    counted_indexes = set() # type: set[int]
    groups = []
    for i in range(len(graph)):
        if i in counted_indexes: continue
        # connected component starts...
        indexes = set(graph_BFS_from_node(graph, i))
        groups.append(indexes)
        counted_indexes.update(indexes)

    return groups


def graph_BFS_from_node(graph, start):
    '''Breadth First Search connected graph with start node.
        ---
        Args:
        - graph: GRAPH represented by adjacent list, [set(1,2,3), set(...), ...]
        - start: index of any start vertex
    '''
    search_queue = deque()    
    searched = set()

    search_queue.append(start)
    while search_queue:
        cur_node = search_queue.popleft()
        if cur_node in searched: continue
        yield cur_node
        searched.add(cur_node)
        for node in graph[cur_node]:
            search_queue.append(node)