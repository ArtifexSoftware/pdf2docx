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
    'type': 3, # or 4 for implicit table
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border-color': (utils.RGB_value(c),,,), # top, right, bottom, left
            'bg-color': utils.RGB_value(c),
            'border-width': (,,,),
            'merged-cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'blocks': [
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
from .pdf_block import (is_text_block, is_image_block, is_table_block, is_discrete_lines_in_block,
        set_implicit_table_block, set_explicit_table_block, merge_blocks)


def parse_table(layout, **kwargs):
    ''' parse table blocks: 
        - table structure recognized from rectangles
        - cell contents extracted from text blocks
    '''
    # -----------------------------------------------------
    # table structure from rects
    # -----------------------------------------------------
    clean_rects(layout, **kwargs) # clean rects
    parse_table_structure_from_rects(layout, **kwargs)    
    parse_table_content(layout, **kwargs) # cell contents

    # -----------------------------------------------------
    # table structure from layout of text lines
    # This MUST come after explicit tables are already detected.
    # -----------------------------------------------------
    parse_table_structure_from_blocks(layout, **kwargs)    
    parse_table_content(layout, **kwargs) # cell contents


@debug_plot('Cleaned Rectangle Shapes', plot=False, category='shape')
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

    # skip rectangles with both of the following two conditions satisfied:
    #  - fully or almost contained in another rectangle
    #  - same filling color with the containing rectangle
    rects_unique = []
    rect_changed = False
    for rect in rects:
        for ref_rect in rects_unique:
            # Do nothing if these two rects in different bg-color
            if ref_rect['color']!=rect['color']: continue     

            # combine two rects in a same row if any intersection exists
            # ideally the aligning threshold should be 1.0, but use 0.98 here to consider tolerance
            if utils.is_horizontal_aligned(rect['bbox'], ref_rect['bbox'], True, 0.98): 
                main_bbox = utils.get_main_bbox(rect['bbox'], ref_rect['bbox'], 0.0)

            # combine two rects in a same column if any intersection exists
            elif utils.is_vertical_aligned(rect['bbox'], ref_rect['bbox'], True, 0.98):
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


@debug_plot('Explicit Table Structure', plot=True, category='table')
def parse_table_structure_from_rects(layout, **kwargs):
    '''parse table structure from rectangle shapes'''    
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
            _set_table_borders(group['rects'])

            # parse table structure based on rects in border type
            table = _parse_table_structure_from_rects(group['rects'])
            if table: 
                set_explicit_table_block(table)
                tables.append(table)

    # add parsed table structure to blocks list
    if tables:
        layout['blocks'].extend(tables)
        return True
    else:
        return False


@debug_plot('Implicit Table Structure', plot=True, category='implicit_table')
def parse_table_structure_from_blocks(layout, **kwargs):
    ''' Parse table structure based on the layout of text/image blocks.

        Since no cell borders exist in this case, there may be various probabilities of table structures. 
        Among which, we use the simplest one, i.e. 1-row and n-column, to make the docx look like pdf.

        Ensure no horizontally aligned blocks in each column, so that these blocks can be converted to
        paragraphs consequently in docx.
        
        Table may exist if:
            - lines in blocks are not connected sequently
            - multi-blocks are in a same row (horizontally aligned)
    '''    
    if len(layout['blocks'])<=1: return False    

    table_lines = []
    new_line = False
    tables = []
    num = len(layout['blocks'])
    for i in range(num):
        block = layout['blocks'][i]
        next_block = layout['blocks'][i+1] if i<num-1 else {}
        
        # lines in current block are not connected sequently?
        if is_discrete_lines_in_block(block):
            table_lines.extend( _collect_table_lines(block) )
            
            # update table / line status
            new_line = False
            table_end = False

        # then, check the layout with next block: in a same row?
        elif utils.is_horizontal_aligned(block['bbox'], next_block.get('bbox', None)):
            # if it's start of new table row: add the first block
            if new_line: 
                table_lines.extend( _collect_table_lines(block) )
            
            # add next block
            table_lines.extend( _collect_table_lines(next_block) )

            # update table / line status
            new_line = False
            table_end = False

        else:
            # table end 
            # - if it's a text line, i.e. no more than one block in a same line
            # - or the next block is also a table
            if new_line or is_table_block(block):
                table_end = True

            # update line status            
            new_line = True

        # NOTE: close table detecting manually if last block
        if i==num-1:
            table_end = True

        # end of current table
        if table_lines and table_end: 
            # parse borders based on contents in cell
            rects = _border_rects_from_table_lines(table_lines)

            # parse table
            table = _parse_table_structure_from_rects(rects)
            if table: 
                set_implicit_table_block(table)
                tables.append(table)

            # reset table_blocks
            table_lines = []

    # add parsed table structure to blocks list
    if tables:
        layout['blocks'].extend(tables)
        return True
    else:
        return False


@debug_plot('Parsed Table', plot=False, category='layout')
def parse_table_content(layout, **kwargs):
    '''Add block lines to associated cells.'''

    # table blocks
    table_found = False
    tables = list(filter(lambda block: is_table_block(block), layout['blocks']))
    if not tables: return table_found

    # collect blocks in table region
    blocks = []
    blocks_in_tables = [[] for _ in tables]
    for block in layout['blocks']:
        # ignore table block
        if is_table_block(block): continue

        # collect blocks contained in table region
        for table, blocks_in_table in zip(tables, blocks_in_tables):
            fitz_table = fitz.Rect(table['bbox'])
            if fitz_table.contains(block['bbox']):
                blocks_in_table.append(block)
                break
        # normal blocks
        else:
            blocks.append(block)

    # assign blocks to associated cells
    # ATTENTION: no nested table is considered
    for table, blocks_in_table in zip(tables, blocks_in_tables):
        for row in table['cells']:
            for cell in row:
                if not cell: continue
                blocks_in_cell = _assign_blocks_to_cell(cell, blocks_in_table)
                if blocks_in_cell: 
                    cell_blocks = merge_blocks(blocks_in_cell)
                    cell['blocks'].extend(cell_blocks)
                    table_found = True

    # sort in natural reading order and update layout blocks
    blocks.extend(tables)
    blocks.sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
    layout['blocks'] = blocks

    return table_found


def _group_rects(rects):
    ''' split rects into groups, to be further checked if it's a table group.        
    '''
    num = len(rects)

    # group intersected rects: a list of {'Rect': fitz.Rect(), 'rects': []}
    groups = []
    counted_index = []
    for i in range(num):
        # do nothing if current rect has considered already
        if i in counted_index:
            continue

        # start a new group
        rect = rects[i]
        group = {
            'Rect': fitz.Rect(rect['bbox']),
            'rects': [rect]
        }

        # check all rects contained in this group
        for j in range(i+1, num):
            other_rect = rects[j]
            fitz_rect = fitz.Rect(other_rect['bbox'])
            # add to the group containing current rect
            if fitz_rect & (group['Rect']+utils.DR): 
                counted_index.append(j) # mark the counted rect

                # update group
                group['Rect'] = fitz_rect | group['Rect']
                group['rects'].append(other_rect)

        # add to groups list
        # NOTE: merge group if any intersection with existing group
        for _group in groups:
            if group['Rect'] & _group['Rect']:
                _group['Rect'] = group['Rect'] | _group['Rect']
                _group['rects'].extend(group['rects'])
                break
        else:
            groups.append(group)

    return groups


def _set_table_borders(rects, border_threshold=6):
    ''' Detect table borders from rects.
        These rects may be categorized as three types:
            - cell border
            - cell shading
            - text format, e.g. highlight, underline

        Cell borders are detected based on the experiences that:
            - compared to cell shading, the size of cell border never exceeds 6 pt
            - compared to text format, cell border always has intersection with other rects

        Note:
            cell shading is determined after the table structure is parsed from these cell borders.
    '''
    # Get all rects with on condition: size < 6 Pt
    thin_rects = []
    for rect in rects:
        x0, y0, x1, y1 = rect['bbox']
        if min(x1-x0, y1-y0) <= border_threshold:
            thin_rects.append(rect)

    # These thin rects may be cell borders, or text format, e.g. underline within cell.
    # Compared to text format, cell border always has intersection with other rects
    for rect in thin_rects:
        fitz_rect = fitz.Rect(rect['bbox'])
        # check intersections with other rect
        for other_rect in thin_rects:
            if rect==other_rect: continue
            # it's a cell border if intersection found
            # Note: if the intersection is an edge, method `intersects` returns False, while
            # the operator `&` return True. So, `&` is used here.
            if fitz_rect & fitz.Rect(other_rect['bbox']):                
                set_cell_border(rect)
                break


def _parse_table_structure_from_rects(rects):
    ''' Parse table structure from rects in table border/shading type.
    '''
    # --------------------------------------------------
    # group horizontal/vertical borders
    # --------------------------------------------------
    borders = list(filter(lambda rect: is_cell_border(rect), rects))
    if not borders: return None

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
    n_rows = len(merged_cells_rows)
    n_cols = len(merged_cells_cols)
    for i in range(n_rows):
        cells_in_row = []
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

            w_top = top['bbox'][3]-top['bbox'][1]
            w_right = right['bbox'][2]-right['bbox'][0]
            w_bottom = bottom['bbox'][3]-bottom['bbox'][1]
            w_left = left['bbox'][2]-left['bbox'][0]

            # cell bbox
            bbox = (cols[j], rows[i], cols[j+n_col], rows[i+n_row])

            # shading rect in this cell
            # modify the cell bbox from border center to inner region
            inner_bbox = (bbox[0]+w_left/2.0, bbox[1]+w_top/2.0, bbox[2]-w_right/2.0, bbox[3]-w_bottom/2.0)
            shading_rect = _get_rect_with_bbox(inner_bbox, rects, threshold=0.9)
            if shading_rect:
                set_cell_shading(shading_rect)
                bg_color = shading_rect['color']
            else:
                bg_color = None

            cells_in_row.append({
                'bbox': bbox,
                'bg-color':  bg_color,
                'border-color': (top['color'], right['color'], bottom['color'], left['color']),
                'border-width': (w_top, w_right, w_bottom, w_left),
                'merged-cells': (n_row, n_col),
                'blocks': [] # text contents in this cell will be determined later
            })
                
        # one row finished
        cells.append(cells_in_row)    

    return {
        'type': -1, # to determin table type later
        'bbox': (cols[0], rows[0], cols[-1], rows[-1]),
        'cells': cells
    }


def _collect_table_lines(block):
    '''Collect block lines bbox, considered as table content.'''
    res = []

    # lines in text block
    if is_text_block(block):
        res.extend([line['bbox'] for line in block['lines']])
    # image block
    elif is_image_block(block):
        res.append(block['bbox'])

    return res
        

def _border_rects_from_table_lines(bbox_lines):
    '''Construct border rects based on contents in table cells.'''
    rects = []

    # boundary box (considering margin) of all line box
    margin = 2.0
    x0 = min([bbox[0] for bbox in bbox_lines]) - margin
    y0 = min([bbox[1] for bbox in bbox_lines]) - margin
    x1 = max([bbox[2] for bbox in bbox_lines]) + margin
    y1 = max([bbox[3] for bbox in bbox_lines]) + margin    
    border_bbox = (x0, y0, x1, y1)

    # centerline of outer borders
    borders = [
        (x0, y0, x1, y0), # top
        (x1, y0, x1, y1), # right
        (x0, y1, x1, y1), # bottom
        (x0, y0, x0, y1)  # left
    ]

    # centerline of inner borders
    inner_borders = _borders_from_bboxes(bbox_lines, border_bbox)
    
    # all centerlines to rectangle shapes
    borders.extend(inner_borders)
    rects = _centerline_to_rect(borders, width=0.0) # no border for implicit table

    return rects


def _borders_from_bboxes(bboxes, border_bbox):
    ''' Calculate the surrounding borders of given bbox-es.
        These borders construct table cells. Considering the re-building of cell content in docx, 
          - only one bbox is allowed in a line, 
          - but multi-lines are allowed in a cell.
    '''
    borders = []   

    # collect bbox-ex column by column
    X0, Y0, X1, Y1 = border_bbox
    cols_bboxes, cols_rects = _column_borders_from_bboxes(bboxes)
    col_num = len(cols_bboxes)
    for i in range(col_num):
        # add column border
        x0 = X0 if i==0 else (cols_rects[i-1].x1 + cols_rects[i].x0) / 2.0
        x1 = X1 if i==col_num-1 else (cols_rects[i].x1 + cols_rects[i+1].x0) / 2.0

        if i<col_num-1:
            borders.append((x1, Y0, x1, Y1))

        # collect bboxes row by row        
        rows_bboxes, rows_rects = _row_borders_from_bboxes(cols_bboxes[i])

        # NOTE: unnecessary o split row if the count of row is 1
        row_num = len(rows_bboxes)
        if row_num==1: continue
    
        for j in range(row_num):
            # add row border
            y0 = Y0 if j==0 else (rows_rects[j-1].y1 + rows_rects[j].y0) / 2.0
            y1 = Y1 if j==row_num-1 else (rows_rects[j].y1 + rows_rects[j+1].y0) / 2.0
            
            # it's Ok if single bbox in a line
            if len(rows_bboxes[j])<2:
                continue

            # otherwise, add row border and check borders further
            if j==0:
                borders.append((x0, y1, x1, y1))
            elif j==row_num-1:
                borders.append((x0, y0, x1, y0))
            else:
                borders.append((x0, y0, x1, y0))
                borders.append((x0, y1, x1, y1))

            # recursion
            _borders = _borders_from_bboxes(rows_bboxes[j], (x0, y0, x1, y1))
            borders.extend(_borders)        

    return borders


def _column_borders_from_bboxes(bboxes):
    ''' split bbox-es into column groups and add border for adjacent two columns.'''
    # sort bbox-ex in column first mode: from left to right, from top to bottom
    bboxes.sort(key=lambda bbox: (bbox[0], bbox[1], bbox[2]))

    # collect bbox-es column by column
    cols_bboxes = []
    cols_rects = [] # cooresponding boundary rect
    for bbox in bboxes:
        if cols_rects:
            col_bbox = (cols_rects[-1].x0, cols_rects[-1].y0, cols_rects[-1].x1, cols_rects[-1].y1)
        else:
            col_bbox = None

        # same column group if vertically aligned
        if utils.is_vertical_aligned(col_bbox, bbox):
            cols_bboxes[-1].append(bbox)
            cols_rects[-1] = cols_rects[-1] | bbox
        
        # otherwise, start a new column group
        else:
            cols_bboxes.append([bbox])
            cols_rects.append(fitz.Rect(bbox))    

    return cols_bboxes, cols_rects


def _row_borders_from_bboxes(bboxes):
    ''' split bbox-es into row groups and add border for adjacent two rows.'''
    # sort bbox-ex in row first mode: from top to bottom, from left to right
    bboxes.sort(key=lambda bbox: (bbox[1], bbox[0], bbox[3]))

    # collect bbox-es row by row
    rows_bboxes = []
    rows_rects = [] # cooresponding boundary rect
    for bbox in bboxes:
        if rows_rects:
            row_bbox = (rows_rects[-1].x0, rows_rects[-1].y0, rows_rects[-1].x1, rows_rects[-1].y1)
        else:
            row_bbox = None

        # same row group if horizontally aligned
        if utils.is_horizontal_aligned(row_bbox, bbox):
            rows_bboxes[-1].append(bbox)
            rows_rects[-1] = rows_rects[-1] | bbox
        
        # otherwise, start a new row group
        else:
            rows_bboxes.append([bbox])
            rows_rects.append(fitz.Rect(bbox))

    return rows_bboxes, rows_rects


def _centerline_to_rect(borders, width=2.0):
    ''' convert centerline to rectangle shape '''
    rects = []
    h = width / 2.0
    for (x0, y0, x1, y1) in borders:
        # consider horizontal or vertical line only
        if x0==x1 or y0==y1:
            rect = {
                'type': -1,
                'bbox': (x0-h, y0-h, x1+h, y1+h),
                'color': utils.RGB_value((1,1,1))
            }
            set_cell_border(rect)
            rects.append(rect)

    return rects


def _get_rect_with_bbox(bbox, rects, threshold):
    '''get rect within given bbox'''
    target_rect = fitz.Rect(bbox)
    for rect in rects:
        this_rect = fitz.Rect(rect['bbox'])
        intersection = target_rect & this_rect
        if intersection.getArea() / target_rect.getArea() >= threshold:
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


def _assign_blocks_to_cell(cell, blocks):
    ''' Get blocks contained in cell bbox.
        Note: If a block is partly contained in a cell, the contained lines should be extracted
              as a new block and assign to the cell.
    '''
    res = []
    fitz_cell = fitz.Rect(cell['bbox'])
    for block in blocks:
        # add it directly if fully contained in a cell
        if fitz_cell.contains(block['bbox']):
            res.append(block)
        
        # add the contained lines if any intersection
        elif fitz_cell.intersects(block['bbox']):
            lines = []
            bbox = fitz.Rect()
            # check each line
            for line in block.get('lines', []): # no lines if image block
                # contains and intersects does not work since tolerance may exists
                if utils.get_main_bbox(cell['bbox'], line['bbox'], 0.5):
                    lines.append(line)
                    bbox = bbox | fitz.Rect(line['bbox'])
            
            # join contained lines back to block
            if lines:
                res.append({
                    'type': 0,
                    'bbox': (bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                    'lines': lines
                })
            
    return res
