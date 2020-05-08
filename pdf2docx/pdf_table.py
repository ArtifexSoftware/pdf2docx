'''
extract table based on raw layout information.

Recognize table from two aspects:
- text blocks layout:
  If text blocks are aligned horizontally in a same line, it is regarded as a row in table.
- rectangles/lines layout:
  Horizontal lines and vertical lines are grouped as table borders.

However, it's difficult to dertermin a table block just by either aspect, because:
- Text blocks may not represent the right table layout, e.g. cells in a row are mergered as 
  a single text block.
- Table borders may be hidden, e.g. three-lines table.

So, a combined process:
- If table borders are detected from rectangle shapes, fill cells with text blocks.
- Otherwise, if table are detected from text blocks layout, check border/rectangle around the blocks.

---

Data structure for table layout recognized from rectangle shapes:

{
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border-color': utils.RGB_value(c),
            'bg-color': utils.RGB_value(c),
            'border-width': int,
            'merged-cells': (x,y) # this is the top-left cell of merged region: x rows, y cols
        }, # end of cell
        None,  # merged cell
        ...,   # more cells
    ], # end of row
    ...] # more rows    
}


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
        if abs(y0-v0)>0.1 or abs(y1-v1)>0.1 or x0-u1>0.1:
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
        if abs(x0-u0)>0.1 or abs(x1-u1)>0.1 or y0-v1>0.1:
            rects_v_join.append(rect)
            continue

        # now join current rect into rects_v_join[-1]
        rect_changed = True
        rects_v_join[-1]['bbox'] = (u0, v0, x1, y1)

    # update layout
    if rect_changed:
        layout['rects'] = rects_v_join

    return rect_changed




@debug_plot('Tables from Rectangles', True, 'shape')
def table_from_rects(layout, **kwargs):
    '''recognize table by parsing border layout from rectangle shapes
    '''
    # group intersected rects: a list of {'Rect': fitz.Rect(), 'rects': []}
    groups = []
    for rect in layout['rects']:
        the_rect = fitz.Rect(rect['bbox'])
        # add to group if intersected
        for group in groups:            
            if the_rect & (group['Rect'] + utils.DR):
                group['Rect'] = the_rect | group['Rect']
                group['rects'].append(rect)
                break
        # otherwise, add a new group
        else:
            groups.append({
                'Rect': the_rect,
                'rects': [rect]
            })

    # to recognize table cells
    for group in groups:
        # at lease 4 borders exists for a normal table
        if len(group['rects']) <= 4:
            continue
        # try to recognize table
        pass

    return False


