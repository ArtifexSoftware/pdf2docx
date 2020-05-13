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

Data structure for table block recognized from rectangle shapes and text blocks:
{
    'type': 3,
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border-color': (utils.RGB_value(c),,,), # top, right, bottom, left
            'bg-color': utils.RGB_value(c),
            'border-width': (,,,),
            'merged-cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'lines': [
                # same structure with lines in text block
            ]
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
from .pdf_shape import (set_cell_border, set_cell_shading, is_cell_border, is_cell_shading)


@debug_plot('Cleaned Rectangle Shapes', True, 'shape')
def clean_rects(layout, **kwargs):
    '''clean rectangles:
        - delete rectangles with white background-color
        - delete rectangles fully contained in another one (beside, they have same bg-color)
        - join intersected and horizontally aligned rectangles with same height and bg-color
        - join intersected and vertically aligned rectangles with same width and bg-color
    '''
    # ignore rect in white bg-color
    f = lambda rect: rect['color']!=utils.RGB_value((1,1,1))
    rects = list(filter(f, layout['rects']))
    
    # sort in reading order
    rects.sort(key=lambda rect: (rect['bbox'][1],  
                    rect['bbox'][0],
                    rect['bbox'][2]))

    # skip rectangles with the following two conditions:
    #  - fully or almost contained in another rectangle
    #  - same filling color with the containing rectangle
    rects_unique = []
    rect_changed = False
    for rect in rects:
        for ref_rect in rects_unique:
            # Do nothing if these two rects in different bg-color
            if ref_rect['color']!=rect['color']: continue     

            # combine two rects in a same row if any intersection exists
            if utils.is_horizontal_aligned(rect['bbox'], ref_rect['bbox'], True, 1.0):
                main_bbox = utils.get_main_bbox(rect['bbox'], ref_rect['bbox'], 0.0)

            # combine two rects in a same column if any intersection exists
            elif utils.is_vertical_aligned(rect['bbox'], ref_rect['bbox'], True, 1.0):
                main_bbox = utils.get_main_bbox(rect['bbox'], ref_rect['bbox'], 0.0)

            # combine two rects if they have a large intersection, e.g. 85%
            else:
                main_bbox = utils.get_main_bbox(rect['bbox'], ref_rect['bbox'], 0.5)

            if main_bbox:
                rect_changed = True
                ref_rect['bbox'] = main_bbox
                break            
        else:
            rects_unique.append(rect)
            
    # update layout
    if rect_changed:
        layout['rects'] = rects_unique

    return rect_changed


@debug_plot('Parsed Table Structure', True, 'table')
def parse_table_structure(layout, **kwargs):
    '''parse table structure from rectangle shapes'''
    # clean rects
    clean_rects(layout, **kwargs)
    
    # group rects: each group may be a potential table
    groups = _group_rects(layout['rects'])

    # check each group
    tables = []
    for group in groups:
        # at least 4 borders exist for a 'normal' table
        if len(group['rects'])<4:
            continue
        else:
            # identify rect type: table border or cell shading
            _set_table_borders_and_shading(group['rects'])

            # parse table structure based on rects in border type
            table = _parse_table_structure_from_rects(group['rects'])
            if table: tables.append(table)

    # add parsed table structure to blocks list
    if tables:
        layout['blocks'].extend(tables)
        return True
    else:
        return False


@debug_plot('Parsed Table', True, 'layout')
def parse_table_content(layout, **kwargs):
    '''Add block lines to associated cells.'''

    # table blocks
    tables = list(filter(lambda block: block['type']==3, layout['blocks']))
    if not tables: return False

    # collect blocks in table region
    blocks = []
    lines_in_tables = [[] for _ in tables]
    for block in layout['blocks']:
        # ignore table block
        if block['type']==3: continue

        # collect blocks contained in table region
        for table, lines in zip(tables, lines_in_tables):
            fitz_table = fitz.Rect(table['bbox'])
            if fitz_table.contains(block['bbox']):
                # text block
                if block['type']==0:
                    lines.extend(block['lines'])
                
                # image block: convert to a image span in line
                elif block['type']==1:
                    lines.append({
                        'wmode': 0,
                        'dir': [1,0],
                        'bbox': block['bbox'],
                        'spans': [
                            block
                        ]
                    })
                
                # done for this block
                break
        # normal blocks
        else:
            blocks.append(block)

    # assign collected lines to associated cells
    for table, lines in zip(tables, lines_in_tables):
        for rows in table['cells']:
            for cell in rows:
                if not cell: continue
                fitz_cell = fitz.Rect(cell['bbox'])
                cell_lines = list(filter(
                    lambda line: fitz_cell.contains(line['bbox']), lines
                ))
                cell['lines'].extend(cell_lines)

    # sort in natural reading order and update layout blocks
    blocks.extend(tables)
    blocks.sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
    layout['blocks'] = blocks

    return True


def _group_rects(rects):
    '''split rects into groups'''
    # sort in reading order
    rects.sort(key=lambda rect: (rect['bbox'][1],  
                    rect['bbox'][0],
                    rect['bbox'][2]))

    # group intersected rects: a list of {'Rect': fitz.Rect(), 'rects': []}
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


def _set_table_borders_and_shading(rects):
    ''' Detect table structure from rects.
        These rects may be categorized as three types:
            - cell border
            - cell shading
            - text format, e.g. highlight, underline

        The rect type is decided based on the experience that:            
            - cell shading has a larger size than border
            - cell shading is surrounded by borders
        
        For a certain rect r, get all intersected rects with it, say R:
            - R is empty -> r is text format
            - r is surrounded by R -> cell shading
            - otherwise  -> cell border

        How to decide that r is surrounded by R?
        The major dimensions of intersections between r and each rect in R are right the
        width/height of r.
    '''
    for rect in rects:
        fitz_rect = fitz.Rect(rect['bbox'])
        w0 = round(fitz_rect.width, 1)
        h0 = round(fitz_rect.height, 1)

        # get all intersected rects
        intersection_found = False
        for other_rect in rects:            
            if rect==other_rect: continue

            fitz_other_rect = fitz.Rect(other_rect['bbox'])
            intersection = fitz_rect & fitz_other_rect
            if not intersection: continue

            intersection_found = True            

            # this is a border if larger rect exists
            w1 = round(fitz_other_rect.width, 1)
            h1 = round(fitz_other_rect.height, 1)
            if min(w0, h0) < min(w1, h1):
                set_cell_border(rect)
                break

            # this is a cell shading if the major dimension is surrounded, 
            # which means the intersection dimension is larger enough, say 90% of current rect
            w = round(intersection.width, 1)
            h = round(intersection.height, 1)
            if max(w, h) >= 0.9*max(w0, h0):
                set_cell_shading(rect)
                break
        
        else:
            if intersection_found:
                set_cell_border(rect)
            # no any intersections: text format -> to detect the specific type later
            else:
                pass


def _parse_table_structure_from_rects(rects):
    ''' Parse table structure from rects in table border/shading type.
    '''
    # --------------------------------------------------
    # group horizontal/vertical borders
    # --------------------------------------------------
    borders = list(filter(lambda rect: is_cell_border(rect), rects))
    h_borders, v_borders = {}, {}
    for rect in borders:
        the_rect = fitz.Rect(rect['bbox'])
        # group horizontal borders in each row
        if the_rect.width > the_rect.height:
            y = round((the_rect.y0 + the_rect.y1) / 2.0, 1)
            if y in h_borders:
                h_borders[y].append(rect)
            else:
                h_borders[y] = [rect]
        # group vertical borders in each column
        else:
            x = round((the_rect.x0 + the_rect.x1) / 2.0, 1)
            if x in v_borders:
                v_borders[x].append(rect)
            else:
                v_borders[x] = [rect]

    # sort
    rows = sorted(h_borders)
    cols = sorted(v_borders)

    # check the outer borders: 
    if not _check_outer_borders(h_borders[rows[0]], v_borders[cols[-1]], h_borders[rows[-1]], v_borders[cols[0]]):
        return None
        
    # --------------------------------------------------
    # parse table structure, especially the merged cells
    # -------------------------------------------------- 
    # check merged cells in each row
    merged_cells_rows = []
    for i, row in enumerate(rows[0:-1]):
        ref_y = (row+rows[i+1])/2.0
        ordered_v_borders = [v_borders[k] for k in cols]
        row_structure = _check_merged_cells(ref_y, ordered_v_borders, 'row')
        merged_cells_rows.append(row_structure)

    # check merged cells in each column
    merged_cells_cols = []
    for i, col in enumerate(cols[0:-1]):
        ref_x = (col+cols[i+1])/2.0
        ordered_h_borders = [h_borders[k] for k in rows]
        col_structure = _check_merged_cells(ref_x, ordered_h_borders, 'column')        
        merged_cells_cols.append(col_structure)

    # --------------------------------------------------
    # parse table properties
    # --------------------------------------------------
    cells = []
    shading_rects = list(filter(lambda rect: is_cell_shading(rect), rects))
    # for i, (row, row_structure) in enumerate(zip(rows, table_structure)):
    n_rows = len(merged_cells_rows)
    n_cols = len(merged_cells_cols)
    for i in range(n_rows):
        cells_in_row = []
        # for j, (col, cell_structure) in enumerate(zip(cols, row_structure)):
        for j in range(n_cols):
            # if current cell is merged horizontally or vertically, set None.
            # actually, it will be counted in the top-left cell of the merged range.
            if merged_cells_rows[i][j]==0 or merged_cells_cols[j][i]==0:
                cells_in_row.append(None)
                continue

            # Now, this is the top-left cell of merged range.
            # A separate cell without merging can also be treated as a merged range 
            # with 1 row and 1 colum, i.e. itself.
            #             
            # check merged columns in horizontal direction
            n_col = 1
            for val in merged_cells_rows[i][j+1:]:
                if val==0:
                    n_col += 1
                else:
                    break
            # check merged rows in vertical direction
            n_row = 1
            for val in merged_cells_cols[j][i+1:]:
                if val==0:
                    n_row += 1
                else:
                    break

            # cell border rects
            top = h_borders[rows[i]][0]
            bottom = h_borders[rows[i+1]][0]
            left = v_borders[cols[j]][0]
            right = v_borders[cols[j+1]][0]

            # cell bbox
            bbox = (cols[j], rows[i], cols[j+n_col], rows[i+n_row])

            # shading rect in this cell
            shading_rect = _get_rect_with_bbox(bbox, shading_rects)

            cells_in_row.append({
                'bbox': bbox,
                'bg-color': shading_rect['color'] if shading_rect else None,
                'border-color': (top['color'], right['color'], bottom['color'], left['color']),
                'border-width': (
                    top['bbox'][3]-top['bbox'][1],
                    right['bbox'][2]-right['bbox'][0],
                    bottom['bbox'][3]-bottom['bbox'][1],
                    left['bbox'][2]-left['bbox'][0]
                ),
                'merged-cells': (n_row, n_col),
                'lines': [] # text contents in this cell will be determined later
            })
                
        # one row finished
        cells.append(cells_in_row)

    return {
        'type': 3,
        'bbox': (cols[0], rows[0], cols[-1], rows[-1]),
        'cells': cells
    }


def _get_rect_with_bbox(bbox, rects, threshold=0.95):
    '''get rect within given bbox'''
    target_rect = fitz.Rect(bbox)
    for rect in rects:
        this_rect = fitz.Rect(rect['bbox'])
        intersection = target_rect & this_rect
        if intersection.getArea() / this_rect.getArea() >= threshold:
            res = rect
            break
    else:
        res = None
    return res


def _check_outer_borders(top_rects, right_rects, bottom_rects, left_rects):
    ''' Check outer borders: whether end points are concurrent.
        top: top lines in rectangle shape
    '''
    # start/end line segments of borders
    top_start, top_end = top_rects[0]['bbox'], top_rects[-1]['bbox']
    right_start, right_end = right_rects[0]['bbox'], right_rects[-1]['bbox']
    bottom_start, bottom_end = bottom_rects[0]['bbox'], bottom_rects[-1]['bbox']
    left_start, left_end = left_rects[0]['bbox'], left_rects[-1]['bbox']

    # width of each line
    w_top, w_bottom = top_start[3]-top_start[1], bottom_start[3]-bottom_start[1]
    w_left, w_right = left_start[2]-left_start[0], right_start[2]-right_start[0]

    # the max allowable distance for the corner points
    # sqrt(w_1^2+w_2^2) <= sqrt(2)*w_max
    square_tolerance = 2 * max(w_top, w_bottom, w_left, w_right)**2

    # check corner points:
    # top_left
    if not utils.check_concurrent_points(top_start[0:2], left_start[0:2], square_tolerance):
        return False

    # top_right
    if not utils.check_concurrent_points(top_end[2:], right_start[0:2], square_tolerance):
        return False
    
    # bottom_left
    if not utils.check_concurrent_points(bottom_start[0:2], left_end[2:], square_tolerance):
        return False

    # bottom_right
    if not utils.check_concurrent_points(bottom_end[2:], right_end[2:], square_tolerance):
        return False
    
    return True


def _check_merged_cells(ref, borders, direction='row'):
    ''' Check merged cells in a row/column. 
        Taking cells in a row (direction=0) for example, give a horizontal line (y=ref) passing through this row, 
        check the intersection with vertical borders. The n-th cell is merged if no intersection with
        the n-th border.

        ---
        ref: y (or x) coordinate of horizontal (or vertical) passing-through line
        borders: a list of vertical (or horizontal) rects list in a column (or row)
        direction: 
            'row' - check merged cells in row; 
            'column' - check merged cells in a column
    '''

    res = []
    for rects in borders[0:-1]:
        # multi-lines exist in a row/column
        for rect in rects:

            # reference coordinates depending on checking direction
            if direction=='row':
                _, ref0, _, ref1 = rect['bbox']
            else:
                ref0, _, ref1, _ = rect['bbox']

            # 1) intersection found
            if ref0 < ref < ref1:
                res.append(1)
                break
            
            # 2) reference line locates below current rect:
            # still have a chance to find intersection with next rect, but,
            # no chance if this is the last rect, see the else-clause
            elif ref > ref1:
                continue

            # 3) current rect locates below the reference line:
            # no intersection is possible any more
            elif ref < ref0:
                res.append(0)
                break
        
        # see notes 2), no change any more
        else:
            res.append(0)

    return res

