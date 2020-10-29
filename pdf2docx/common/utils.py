# -*- coding: utf-8 -*-

import random
from collections import deque
from collections.abc import Iterable
from fitz.utils import getColorList, getColorInfoList


def is_number(str_number):
    try:
        float(str_number)
    except ValueError:
        return False
    else:
        return True


def flatten(items, klass):
    '''Yield items from any nested iterable.'''
    for item in items:
        if isinstance(item, Iterable) and not isinstance(item, klass):
            yield from flatten(item, klass)
        else:
            yield item


# -------------------------
# color methods
# -------------------------
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


def RGB_to_value(rgb:list):
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
    res = RGB_to_value([r, g, b]) # type: int
    return res


def RGB_value(components:list):
    '''Gray/RGB/CMYK mode components to color value.'''
    num = len(components)
    # CMYK mode
    if num==4:
        c, m, y, k = map(float, components)
        color = CMYK_to_RGB(c, m, y, k, cmyk_scale=1.0)
    # RGB mode
    elif num==3:
        r, g, b = map(float, components)
        color = RGB_to_value([r, g, b])
    # gray mode
    elif num==1:
        g = float(components[0])
        color = RGB_to_value([g,g,g])    
    else:
        color = 0

    return color


# -------------------------
# pdf plot
# -------------------------
def new_page(doc, width:float, height:float, title:str):
    ''' Insert a new page with given title.
        ---
        Args:
        - doc: fitz.Document
        - width, height: page size
        - title: page title shown in page
    '''
    # insert a new page
    page = doc.newPage(width=width, height=height)    

    # plot title at the top-left corner
    gray = RGB_component_from_name('gray')
    page.insertText((5, 16), title, color=gray, fontsize=15)
    
    return page


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
                page = new_page(doc, layout.width, layout.height, title)

                # plot objects, e.g. text blocks, shapes, tables...
                objects.plot(page)

            return objects
        return inner
    return wrapper


# -------------------------------------------------------------------------------------------
# Implementation of solving Rectangle-Intersection Problem according algorithm proposed in
# paper titled "A Rectangle-Intersection Algorithm with Limited Resource Requirements".
# https://ieeexplore.ieee.org/document/5578313
# - Performance
# O(nlog n + k) time and O(n) space, where k is the count of intersection pairs
# - Input
# The rectangle is represented by its corner points, (x0, y0, x1, y1)
# - Output
# The output is an Adjacent List of each rect, which could be used to initialize a GRAPH.
# -------------------------------------------------------------------------------------------
# procedure report(S, n)
# 1 Let V be the list of x-coordinates of the 2n vertical edges in S sorted in non-decreasing order.
# 2 Let H be the list of n y-intervals corresponding to the bottom and top y-coordinates of each rectangle.
# 3 Sort the elements of H in non-decreasing order by their bottom y-coordinates.
# 4 Call procedure detect(V, H, 2n).

def solve_rects_intersection(V:list, num:int, index_groups:list):
    ''' divide and conque in x-direction.
        ---
        Args:
        - V: rectangle-related x-edges data, [(index, Rect, x), (...), ...]
        - num: count of V instances, equal to len(V)
        - index_groups: target adjacent list for connectivity between rects
        
        ```
        procedure detect(V, H, m):
        if m < 2 then return else
        - let V1 be the first ⌊m/2⌋ and let V2 be the rest of the vertical edges in V in the sorted order;
        - let S11 and S22 be the set of rectangles represented only in V1 and V2 but not spanning V2 and V1,
            respectively;
        - let S12 be the set of rectangles represented only in V1 and spanning V2; 
        - let S21 be the set of rectangles represented only in V2 and spanning V1
        - let H1 and H2 be the list of y-intervals corresponding to the elements of V1 and V2 respectively
        - stab(S12, S22); stab(S21, S11); stab(S12, S21)
        - detect(V1, H1, ⌊m/2⌋); detect(V2, H2, m − ⌊m/2⌋)
        ```
    '''
    if num < 2: return
    
    # start/end points of left/right intervals
    center_pos = int(num/2.0)
    X0, X, X1 = V[0][-1], V[center_pos-1][-1], V[-1][-1] 

    # split into two groups
    left = V[0:center_pos]
    right = V[center_pos:]

    # filter rects according to their position to each intervals
    S11 = list(filter( lambda item: item[1][2]<=X, left ))
    S12 = list(filter( lambda item: item[1][2]>=X1, left ))
    S22 = list(filter( lambda item: item[1][0]>X, right ))
    S21 = list(filter( lambda item: item[1][0]<=X0, right ))
    
    # intersection in x-direction is fullfilled, so check y-direction further
    stab(S12, S22, index_groups)
    stab(S21, S11, index_groups)
    stab(S12, S21, index_groups)

    # recursive process
    solve_rects_intersection(left,  center_pos,     index_groups)
    solve_rects_intersection(right, num-center_pos, index_groups)


def stab(S1:list, S2:list, index_groups:list):
    '''Check interval intersection in y-direction.

        ```
        procedure stab(A, B)
            i := 1; j := 1
            while i ≤ |A| and j ≤ |B|
              if ai.y0 < bj.y0 then
                k := j
                while k ≤ |B| and bk.y0 < ai.y1
                  reportPair(air, bks)
                  k := k + 1
                i := i + 1
              else
                k := i
                while k ≤ |A| and ak.y0 < bj.y1
                  reportPair(bjs, akr)
                  k := k + 1
                j := j + 1
        ```
    '''
    if not S1 or not S2: return

    # sort
    S1.sort(key=lambda item: item[1][1])
    S2.sort(key=lambda item: item[1][1])

    i, j = 0, 0
    while i<len(S1) and j<len(S2):
        m, a, _ = S1[i]
        n, b, _ = S2[j]
        if a[1] < b[1]:
            k = j
            while k<len(S2) and S2[k][1][1] < a[3]:
                report_pair(int(m/2), int(S2[k][0]/2), index_groups)
                k += 1
            i += 1
        else:
            k = i
            while k<len(S1) and S1[k][1][1] < b[3]:
                report_pair(int(S1[k][0]/2), int(n/2), index_groups)
                k += 1
            j += 1


def report_pair(i:int, j:int, index_groups:list):
    '''add pair (i,j) to adjacent list.'''
    index_groups[i].add(j)
    index_groups[j].add(i)


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