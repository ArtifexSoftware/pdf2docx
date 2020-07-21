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

import copy
import fitz
from . import utils
from .pdf_debug import debug_plot
from .pdf_shape import (set_cell_border, set_cell_shading, is_cell_border, is_cell_shading, centerline_to_rect)
from .pdf_block import (is_text_block, is_image_block, is_table_block, is_discrete_lines_in_block,
        set_implicit_table_block, set_explicit_table_block, merge_blocks)


def parse_explicit_table(layout, **kwargs):
    '''Parse table structure recognized from rectangles.'''
    clean_rects(layout, **kwargs) # clean rects
    parse_table_structure_from_rects(layout, **kwargs)    
    parse_table_content(layout, **kwargs) # cell contents


def parse_implicit_table(layout, **kwargs):
    ''' Parse table structure recognized from text blocks.
        This MUST come after explicit tables are already detected.
    '''
    parse_table_structure_from_blocks(layout, **kwargs)    
    parse_table_content(layout, **kwargs) # cell contents


@debug_plot('Cleaned Rectangle Shapes', plot=True, category='shape')
def clean_rects(layout, **kwargs):
    '''clean rectangles:
        - delete rectangles fully contained in another one (beside, they have same bg-color)
        - join intersected and horizontally aligned rectangles with same height and bg-color
        - join intersected and vertically aligned rectangles with same width and bg-color
    '''
    # sort in reading order
    layout['rects'].sort(key=lambda rect: (rect['bbox'][1],  
                    rect['bbox'][0],
                    rect['bbox'][2]))

    # skip rectangles with both of the following two conditions satisfied:
    #  - fully or almost contained in another rectangle
    #  - same filling color with the containing rectangle
    rects_unique = []
    rect_changed = False
    for rect in layout['rects']:
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
        # skip if not a table group
        if not _set_table_borders(group):
            continue

        # parse table structure based on rects in border type
        table = _parse_table_structure_from_rects(group)
        if table: 
            set_explicit_table_block(table)
            tables.append(table)
        # reset border type if parse table failed
        else:
            for rect in group:
                rect['type'] = -1

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
        
        Table may exist on the following two conditions:
            - (a) lines in blocks are not connected sequently -> determined by current block only
            - (b) multi-blocks are in a same row (horizontally aligned) -> determined by two adjacent blocks
    '''    
    if len(layout['blocks'])<=1: return False
    
    # horizontal range of table
    left, right, *_ = layout['margin']
    X0 = left
    X1 = layout['width'] - right

    table_lines = []
    new_line = True
    tables = []
    num = len(layout['blocks'])
    for i in range(num):
        block = layout['blocks'][i]
        next_block = layout['blocks'][i+1] if i<num-1 else {}

        table_end = False
        
        # there is gap between these two criteria, so consider condition (a) only if if it's the first block in new row
        # (a) lines in current block are connected sequently?
        # yes, counted as table lines
        if new_line and is_discrete_lines_in_block(block): 
            table_lines.extend( _collect_table_lines(block) )
            
            # update line status
            new_line = False
            

        # (b) multi-blocks are in a same row: check layout with next block?
        # yes, add both current and next blocks
        if utils.is_horizontal_aligned(block['bbox'], next_block.get('bbox', None)):
            # if it's start of new table row: add the first block
            if new_line: 
                table_lines.extend( _collect_table_lines(block) )
            
            # add next block
            table_lines.extend( _collect_table_lines(next_block) )

            # update line status
            new_line = False

        # no, consider to start a new row
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
            rects = _border_rects_from_table_lines(table_lines, X0, X1)

            # parse table
            table = _parse_table_structure_from_rects(rects)

            # ignore table if contains only one cell
            if table: 
                rows = table['cells']
                if len(rows)>1 or len(rows[0])>1:
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
            if fitz_table.intersects(block['bbox']):
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

                # check candidate blocks
                blocks_in_cell = []
                fitz_cell = fitz.Rect(cell['bbox'])
                for block in blocks_in_table:
                    cell_block = _assign_block_to_cell(block, fitz_cell)
                    if cell_block:
                        blocks_in_cell.append(cell_block)

                # merge blocks if contained blocks found
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
    groups = []
    counted_index = set()

    for i in range(len(rects)):

        # do nothing if current rect has been considered already
        if i in counted_index:
            continue

        # start a new group
        rect = rects[i]
        group = { i }

        # get intersected rects
        _get_intersected_rects(rect, rects, group)

        # update counted rects
        counted_index = counted_index | group

        # add rect to groups
        group_rects = [rects[x] for x in group]
        groups.append(group_rects)

    return groups


def _get_intersected_rects(rect, rects, group):
    ''' Get intersected rects from `rects` and store in `group`.
        ---
        Args:
            - group: a set() of index of intersected rect
    '''
    # source rect to intersect with
    fitz_source = fitz.Rect(rect['bbox'])

    for i in range(len(rects)):

        # ignore rect already processed
        if i in group: continue

        # if intersected, check rects further
        target = rects[i]
        fitz_target = fitz.Rect(target['bbox'])
        if fitz_source & fitz_target:
            group.add(i)
            _get_intersected_rects(target, rects, group)


def _parse_table_structure_from_rects(rects):
    ''' Parse table structure from rects in table border/shading type.
    '''
    # --------------------------------------------------
    # group horizontal/vertical borders
    # --------------------------------------------------
    h_borders, v_borders = _collect_explicit_borders(rects)
    if not h_borders or not v_borders:
        return None

    # sort
    rows = sorted(h_borders)
    cols = sorted(v_borders)
        
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

            # cell border rects: merged cells considered
            top = h_borders[rows[i]][0]
            bottom = h_borders[rows[i+n_row]][0]
            left = v_borders[cols[j]][0]
            right = v_borders[cols[j+n_col]][0]

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
        # check table: the first cell in first row MUST NOT be None
        if i==0 and cells_in_row[0]==None:
            return None

        cells.append(cells_in_row)    

    return {
        'type': -1, # to determin table type later
        'bbox': (cols[0], rows[0], cols[-1], rows[-1]),
        'cells': cells
    }


def _collect_explicit_borders(rects):
    ''' Collect explicit borders in horizontal and vertical groups respectively.'''
    borders = list(filter(lambda rect: is_cell_border(rect), rects))
    h_borders, v_borders = {}, {}
    h_outer, v_outer = [], []
    for rect in borders:
        the_rect = fitz.Rect(rect['bbox'])
        # group horizontal borders in each row
        if the_rect.width > the_rect.height:
            # row centerline
            y = round((the_rect.y0 + the_rect.y1) / 2.0, 1)
            if y in h_borders:
                h_borders[y].append(rect)
            else:
                h_borders[y] = [rect]
            
            # candidates for vertical outer border
            v_outer.extend([the_rect.x0, the_rect.x1])

        # group vertical borders in each column
        else:
            # column centerline
            x = round((the_rect.x0 + the_rect.x1) / 2.0, 1)
            if x in v_borders:
                v_borders[x].append(rect)
            else:
                v_borders[x] = [rect]
            
            # candidates for horizontal outer border
            h_outer.extend([the_rect.y0, the_rect.y1])

    # at least 2 inner borders exist
    if len(h_borders)+len(v_borders)<2:
        return None, None

    # Note: add dummy borders if no outer borders exist
    # check whether outer borders exists in collected borders
    if h_borders:
        top_rects = h_borders[min(h_borders)]
        bottom_rects = h_borders[max(h_borders)]
        left   = min(v_outer)
        right  = max(v_outer)
    else:
        top_rects = []
        bottom_rects = []
        left   = None
        right  = None

    if v_borders:
        left_rects = v_borders[min(v_borders)]
        right_rects = v_borders[max(v_borders)]
        top   = min(h_outer)
        bottom  = max(h_outer)
    else:
        left_rects = []
        right_rects = []
        top   = None
        bottom  = None    

    if not _exist_outer_border(top, top_rects, 'h'):
        h_borders[top] = [
            {
                'type': -1,
                'bbox': (left, top, right, top),
                'color': utils.RGB_value((1,1,1))
            }
        ]
    if not _exist_outer_border(bottom, bottom_rects, 'h'):
        h_borders[bottom] = [
            {
                'type': -1,
                'bbox': (left, bottom, right, bottom),
                'color': utils.RGB_value((1,1,1))
            }
        ]
    if not _exist_outer_border(left, left_rects, 'v'):
        v_borders[left] = [
            {
                'type': -1,
                'bbox': (left, top, left, bottom),
                'color': utils.RGB_value((1,1,1))
            }
        ]
    if not _exist_outer_border(right, right_rects, 'v'):
        v_borders[right] = [
            {
                'type': -1,
                'bbox': (right, top, right, bottom),
                'color': utils.RGB_value((1,1,1))
            }
        ]

    return h_borders, v_borders


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
    borders = []
    for rect in thin_rects:
        fitz_rect = fitz.Rect(rect['bbox'])
        # check intersections with other rect
        for other_rect in thin_rects:
            if rect==other_rect: continue
            # it's a cell border if intersection found
            # Note: if the intersection is an edge, method `intersects` returns False, while
            # the operator `&` return True. So, `&` is used here.
            if fitz_rect & fitz.Rect(other_rect['bbox']):                
                borders.append(rect)
                break
    
    # at least two inner borders exist for a normal table
    if len(borders)>=2:
        # set table border type
        for rect in borders:
            set_cell_border(rect)
        return True
    else:
        return False


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
        

def _border_rects_from_table_lines(bbox_lines, X0, X1):
    ''' Construct border rects based on contents in table cells.
        Args:
          - X0, X1: default left and right borders of table
    '''
    # boundary box (considering margin) of all line box
    margin = 2.0
    x0 = X0 - margin
    y0 = min([bbox[1] for bbox in bbox_lines]) - margin
    x1 = X1 + margin
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
    borders.extend(inner_borders)
    
    # all centerlines to rectangle shapes
    rects = []
    color = utils.RGB_value((1,1,1))
    for border in borders:        
        rect = centerline_to_rect(border, color, width=0.0) # no border for implicit table
        if not rect: continue
        set_cell_border(rect) # set border style
        rects.append(rect)

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


def _exist_outer_border(target, borders, direction='h'):
    ''' Check outer borders: whether target border exists in collected borders.
        Args:
            target: float, target position of outer border
            borders: list, a list of rects representing borders
            direction: str, 'h'->horizontal border; 'v'->vertical border
    '''
    # no target outer border needed
    if target==None:
        return True

    # need outer border if no borders exist
    if not borders:
        return False
    
    if direction=='h':
        # centerline of source borders
        source = round((borders[0]['bbox'][1] + borders[0]['bbox'][3]) / 2.0, 1)
        # max width of source borders
        width = max(map(lambda rect: rect['bbox'][3]-rect['bbox'][1], borders))
    else:
        source = round((borders[0]['bbox'][0] + borders[0]['bbox'][2]) / 2.0, 1)
        width = max(map(lambda rect: rect['bbox'][2]-rect['bbox'][0], borders))

    target = round(target, 1)
    width = round(width, 1)

    return abs(target-source) <= width


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


def _assign_block_to_cell(block, fitz_bbox):
    ''' Get part of block contained in bbox. 
        Note: If the block is partly contained in a cell, it must deep into line -> span -> char.
    '''
    res = None

    # add block directly if fully contained in cell
    if fitz_bbox.contains(block['bbox']):
        res = block

    # otherwise, further check lines in block
    elif fitz_bbox.intersects(block['bbox']):
        block_bbox = fitz.Rect()
        block_lines = []

        for line in block.get('lines', []): # no lines if image block                
            cell_line = _assign_line_to_bbox(line, fitz_bbox)
            if cell_line:
                block_lines.append(cell_line)
                block_bbox = block_bbox | cell_line['bbox']

        # update block
        if block_lines:
            res = copy.deepcopy(block)
            res['bbox'] = (block_bbox.x0, block_bbox.y0, block_bbox.x1, block_bbox.y1)
            res['lines'] = block_lines

    return res


def _assign_line_to_bbox(line, fitz_bbox):
    ''' Get line spans contained in bbox. '''
    res = None

    # add line directly if fully contained in bbox
    if fitz_bbox.contains(line['bbox']):
        res = line
    
    # further check spans in line
    elif fitz_bbox.intersects(line['bbox']):
        line_bbox = fitz.Rect()
        line_spans = []

        for span in line.get('spans', []):
            cell_span = _assign_span_to_bbox(span, fitz_bbox)
            if cell_span:
                line_spans.append(cell_span)
                line_bbox = line_bbox | cell_span['bbox']
        
        # update line
        if line_spans:
            res = copy.deepcopy(line)
            res['bbox'] = (line_bbox.x0, line_bbox.y0, line_bbox.x1, line_bbox.y1)
            res['spans'] = line_spans

    return res


def _assign_span_to_bbox(span, fitz_bbox):
    ''' Get span chars contained in bbox. '''
    res = None

    # add span directly if fully contained in bbox
    if fitz_bbox.contains(span['bbox']):
        res = span

    # furcher check chars in span
    elif fitz_bbox.intersects(span['bbox']):
        span_chars = []
        span_bbox = fitz.Rect()
        for char in span.get('chars', []):
            if utils.get_main_bbox(char['bbox'], fitz_bbox, 0.2):
                span_chars.append(char)
                span_bbox = span_bbox | char['bbox']

        # update span
        if span_chars:
            res = copy.deepcopy(span)
            res['chars'] = span_chars
            res['bbox'] = (span_bbox.x0, span_bbox.y0, span_bbox.x1, span_bbox.y1)
            res['text'] = ''.join([c['c'] for c in span_chars])

    return res
        