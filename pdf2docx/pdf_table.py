'''
extract table
'''

import fitz
from . import utils
from .pdf_debug import debug_plot


@debug_plot('Cleaned Rectangles', True, 'shape')
def clean_rects(layout, **kwargs):
    '''clean rectangles:
        - delete rectangles with white background-color
        - delete rectangles fully contained in another one (beside, they have same bg-color)
        - join intersected and horizontally aligned rectangles with same height and bg-color
        - join intersected and vertically aligned rectangles with same width and bg-color
    '''
    # ignore rect with white bg-color
    f = lambda rect: rect['color']!=utils.RGB_value((1,1,1))
    rects = list(filter(f, layout['rects']))    

    # start main clean steps    
    rect_changed = False

    # skip rectangles with following conditions:
    #  - fully or almost contained in another rectangle
    #  - same filling color with the containing rectangle
    # sort according to bbox area: from large to small
    rects.sort(reverse=True, key=lambda rect: (
        rect['color'], 
        (rect['bbox'][2]-rect['bbox'][0])*(rect['bbox'][3]-rect['bbox'][1])))
    rects_unique = []
    for rect in rects:
        for ref_rect in rects_unique:
            if ref_rect['color']!=rect['color']:
                continue

            main_bbox = utils.get_main_bbox(rect['bbox'], ref_rect['bbox'], 0.8)

            # if current rect is the main bbox, update the reference rect
            if main_bbox==rect['bbox']:
                rect_changed = True
                ref_rect['bbox'] = main_bbox
                break
            # if current rect is 'contained' in a certain reference rect, do nothing
            elif main_bbox==ref_rect['bbox']:
                rect_changed = True
                break
        else:
            # no rect containing current rect
            rects_unique.append(rect)

    # join horizontal lines: sort with reading direction first
    rects_unique.sort(key=lambda rect: (rect['color'], 
                                rect['bbox'][1],  
                                rect['bbox'][0],
                                rect['bbox'][2]))
    rects_h_join = [rects_unique[0]]
    for rect in rects_unique[1:]:
        # new item if different bg-color
        if rect['color'] != rects_h_join[-1]['color']:
            rects_h_join.append(rect)
            continue
        
        u0, v0, u1, v1 = rects_h_join[-1]['bbox']
        x0, y0, x1, y1 = rect['bbox']

        # new item if not in same line or no intersection
        # round to avoid float error:
        # y0!=v0 or y1!=v1 or x0>u1
        if abs(y0-v0)>utils.DM/10.0 or abs(y1-v1)>utils.DM/10.0 or x0-u1>utils.DM/10.0:
            rects_h_join.append(rect)
            continue

        # now join current rect into rects_h_join[-1]
        rect_changed = True
        rects_h_join[-1]['bbox'] = (u0, v0, x1, y1)

    # join vertical lines: sort vertically first
    rects_h_join.sort(key=lambda rect: (rect['color'], 
                            rect['bbox'][0],  
                            rect['bbox'][1],
                            rect['bbox'][3]))
    rects_v_join = [rects_h_join[0]]
    for rect in rects_h_join[1:]:
        # new item if different bg-color
        if rect['color'] != rects_v_join[-1]['color']:
            rects_v_join.append(rect)
            continue       
        
        u0, v0, u1, v1 = rects_v_join[-1]['bbox']
        x0, y0, x1, y1 = rect['bbox']

        # new item if not in same vertical line or no intersection
        # note float error: 
        # x0 != u0 or x1 != u1 or y0 > v1
        if abs(x0-u0)>utils.DM/10.0 or abs(x1-u1)>utils.DM/10.0 or y0-v1>utils.DM/10.0:
            rects_v_join.append(rect)
            continue

        # now join current rect into rects_v_join[-1]
        rect_changed = True
        rects_v_join[-1]['bbox'] = (u0, v0, x1, y1)

    # update layout
    if rect_changed:
        layout['rects'] = rects_v_join

    return rect_changed


@debug_plot('Parsed Table Structure', True, 'shape')
def parse_table(layout, **kwargs):
    '''parse table with rectangle shapes and text block'''
    # clean rects
    clean_rects(layout, **kwargs)
    
    # group rects: each group may be a potential table
    groups = group_rects(layout['rects'])

    # check each group
    for group in groups:
        # at least 4 borders exist for a 'normal' table
        if len(group['rects'])<4:
            continue
        else:
            tables_from_rects(group['rects'])

    # check text block
    return True


def group_rects(rects):
    '''split rects into groups'''
    # sort in reading order
    rects.sort(key=lambda rect: (rect['bbox'][1],  
                    rect['bbox'][0],
                    rect['bbox'][2]))

    groups = []
    for rect in rects:
        fitz_rect = fitz.Rect(rect['bbox'])
        for group in groups:
            # add to the group containing current rect
            if fitz_rect & group['Rect']: 
                group['Rect'] = fitz_rect | group['Rect']
                group['rects'].append(rect)
                break

        # no any intersections: new group
        else:
            groups.append({
                'Rect': fitz_rect,
                'rects': [rect]
            })

    return groups


def tables_from_rects(rects):
    ''' Detect table structure from rects.
        These rects may be categorized as three types:
            - cell border
            - cell background
            - text format, e.g. highlight, underline
        
        Suppose all rects are cell borders, then check intersections:
            - no intersection -> text format
            - at least one point-like intersection -> cell border
            - all edge-like intersections -> cell background

        Give r = r1 & r2, then:        
            - point-like intersection: max(r.w, r.h) in (min(r1.w,r1.h), min(r2.w,r2.h))
            - edge-like intersection: max(r.w, r.h) in (max(r1.w,r1.h), max(r2.w,r2.h))
    '''
    for rect in rects:
        fitz_rect = fitz.Rect(rect['bbox'])
        # check intersection with other rects
        intersected = False
        for other_rect in rects:
            if rect==other_rect: continue

            fitz_other_rect = fitz.Rect(other_rect['bbox'])
            sect = fitz_rect & fitz_other_rect
            if not sect:
                continue
            else:
                intersected = True                

            # at least one point-like intersection -> cell border
            max_edge = round(max(sect.width, sect.height), 2)
            min_edge_1 = round(min(fitz_rect.width, fitz_rect.height), 2)
            min_edge_2 = round(min(fitz_other_rect.width, fitz_other_rect.height), 2)
            print(max_edge,min_edge_1,min_edge_2)
            if max_edge==min_edge_1 or max_edge==min_edge_2:
                rect['type'] = 10 # cell border
                break
        else:
            # all intersections are edge-like
            if intersected:
                rect['type'] = 11 # cell bg
            # no any intersections: text format -> to detect the specific type later
            else:
                pass





