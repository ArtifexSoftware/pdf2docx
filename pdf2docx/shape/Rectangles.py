# -*- coding: utf-8 -*-

'''
A group of Rectangle instances focusing on table parsing process.

@created: 2020-07-22
@author: train8808@gmail.com
'''

from .Rectangle import Rectangle
from ..common.base import RectType
from ..common.BBox import BBox
from ..common.Collection import Collection
from ..common import utils
from ..common import pdf
from ..table.TableBlock import TableBlock
from ..table.Cell import Cell

class Rectangles(Collection):

    @property
    def border_rects(self):
        '''Rectangles in border type.'''
        return list(filter(
            lambda rect: rect.type==RectType.BORDER, self._instances))

    def from_annotations(self, page):
        ''' Get shapes, e.g. Line, Square, Highlight, from annotations(comment shapes) in PDF page.
            ---
            Args:
            - page: fitz.Page, current page
        '''
        rects = pdf.rects_from_annotations(page)
        for rect in rects:
            self._instances.append(Rectangle(rect))

        return self


    def from_stream(self, doc, page):
        ''' Get rectangle shapes, e.g. highlight, underline, table borders, from page source contents.
            ---
            Args:
            - doc: fitz.Document representing the pdf file
            - page: fitz.Page, current page
        '''
        rects = pdf.rects_from_stream(doc, page)
        for rect in rects:
            self._instances.append(Rectangle(rect))

        return self


    def clean(self):
        '''Clean rectangles:
            - delete rectangles fully contained in another one (beside, they have same bg-color)
            - join intersected and horizontally aligned rectangles with same height and bg-color
            - join intersected and vertically aligned rectangles with same width and bg-color
        '''
        # sort in reading order
        self.sort_in_reading_order()

        # skip rectangles with both of the following two conditions satisfied:
        #  - fully or almost contained in another rectangle
        #  - same filling color with the containing rectangle
        rects_unique = [] # type: list [Rectangle]
        rect_changed = False
        for rect in self._instances:
            for ref_rect in rects_unique:
                # Do nothing if these two rects in different bg-color
                if ref_rect.color!=rect.color: continue     

                # combine two rects in a same row if any intersection exists
                # ideally the aligning threshold should be 1.0, but use 0.98 here to consider tolerance
                if rect.horizontally_align_with(ref_rect, 0.98): 
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.0)

                # combine two rects in a same column if any intersection exists
                elif rect.vertically_align_with(ref_rect, 0.98):
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.0)

                # combine two rects if they have a large intersection
                else:
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.5)

                if main_bbox:
                    rect_changed = True
                    ref_rect.update(main_bbox)
                    break            
            else:
                rects_unique.append(rect)
                
        # update layout
        if rect_changed:
            self._instances = rects_unique

        return rect_changed


    def parse_table_structure(self, detect_border=True):
        ''' Parse table structure from rects, which may be border, shading or text style.
            ---
            Args:
            - detect_border: to detect table border if True.

            NOTE: for implicit table, table borders are determined from text blocks in advance,
            so, it's safe to set `detect_border=False`.
        '''

        # --------------------------------------------------
        # mark table borders first
        # --------------------------------------------------
        # exit if no borders exist
        if detect_border and not self._set_table_borders(width_threshold=6.0):
            return None
        
        # --------------------------------------------------
        # group horizontal/vertical borders
        # --------------------------------------------------
        h_borders, v_borders = self._collect_explicit_borders()
        if not h_borders or not v_borders:
            # reset borders because it's a invalid table
            self._unset_table_border()
            return None

        # sort
        rows = sorted(h_borders)
        cols = sorted(v_borders)       
            
        # --------------------------------------------------
        # parse table structure, especially the merged cells
        # -------------------------------------------------- 
        # check merged cells in each row
        merged_cells_rows = []  # type: list[list[int]]
        for i, row in enumerate(rows[0:-1]):
            ref_y = (row+rows[i+1])/2.0
            ordered_v_borders = [v_borders[k] for k in cols]
            row_structure = self._check_merged_cells(ref_y, ordered_v_borders, 'row')
            merged_cells_rows.append(row_structure)

        # check merged cells in each column
        merged_cells_cols = []  # type: list[list[int]]
        for i, col in enumerate(cols[0:-1]):
            ref_x = (col+cols[i+1])/2.0
            ordered_h_borders = [h_borders[k] for k in rows]
            col_structure = self._check_merged_cells(ref_x, ordered_h_borders, 'column')        
            merged_cells_cols.append(col_structure)

        # --------------------------------------------------
        # parse table properties
        # --------------------------------------------------
        table = TableBlock()
        n_rows = len(merged_cells_rows)
        n_cols = len(merged_cells_cols)

        for i in range(n_rows):
            cells_in_row = []    # type: list[Cell]
            for j in range(n_cols):
                # if current cell is merged horizontally or vertically, set None.
                # actually, it will be counted in the top-left cell of the merged range.
                if merged_cells_rows[i][j]==0 or merged_cells_cols[j][i]==0:
                    cells_in_row.append(Cell())
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

                w_top = top.bbox.y1-top.bbox.y0
                w_right = right.bbox.x1-right.bbox.x0
                w_bottom = bottom.bbox.y1-bottom.bbox.y0
                w_left = left.bbox.x1-left.bbox.x0

                # cell bbox
                bbox = (cols[j], rows[i], cols[j+n_col], rows[i+n_row])

                # shading rect in this cell
                # modify the cell bbox from border center to inner region
                inner_bbox = (bbox[0]+w_left/2.0, bbox[1]+w_top/2.0, bbox[2]-w_right/2.0, bbox[3]-w_bottom/2.0)
                target_bbox = BBox().update(inner_bbox)
                shading_rect = self._get_rect_with_bbox(target_bbox, threshold=0.9)
                if shading_rect:
                    shading_rect.type = RectType.SHADING # ATTENTION: set shaing type
                    bg_color = shading_rect.color
                else:
                    bg_color = None

                # Cell object
                cell_dict = {
                    'bbox': bbox,
                    'bg_color':  bg_color,
                    'border_color': (top.color, right.color, bottom.color, left.color),
                    'border_width': (w_top, w_right, w_bottom, w_left),
                    'merged_cells': (n_row, n_col),
                }

                cells_in_row.append(Cell(cell_dict))
                    
            # one row finished
            # check table: the first cell in first row MUST NOT be None
            if i==0 and not cells_in_row[0]:
                # reset borders because it's a invalid table
                self._unset_table_border()
                return None

            table.append_row(cells_in_row)

        return table


    def implicit_borders(self, X0:float, X1:float):
        ''' Construct border rects based on contents rects, e.g. contents in table cells.
            ---
            Args:
              - X0, X1: default left and right outer borders
        '''
        # boundary box (considering margin) of all line box
        margin = 1
        x0 = X0 - margin
        y0 = min([rect.bbox.y0 for rect in self._instances]) - margin
        x1 = X1 + margin
        y1 = max([rect.bbox.y1 for rect in self._instances]) + margin    
        border_bbox = (x0, y0, x1, y1)

        # centerline of outer borders
        borders = [
            (x0, y0, x1, y0), # top
            (x1, y0, x1, y1), # right
            (x0, y1, x1, y1), # bottom
            (x0, y0, x0, y1)  # left
        ]

        # centerline of inner borders
        inner_borders = self._borders_from_bboxes(border_bbox)
        borders.extend(inner_borders)
        
        # all centerlines to rectangle shapes
        rects = Rectangles()
        color = utils.RGB_value((1,1,1))
        for border in borders: 
            # set an non-zero width for border check; won't draw border in docx for implicit table
            bbox = utils.expand_centerline(border[0:2], border[2:], width=0.2) 
            if not bbox: continue

            # create Rectangle object and set border style
            rect = Rectangle({
                'bbox': bbox,
                'color': color
            })
            rect.type = RectType.BORDER
            rects.append(rect)

        return rects


    def _set_table_borders(self, width_threshold:float=6.0):
        ''' Detect table borders from rects.
            ---
            Args:
              - width_threshold: float, suppose border width is lower than this threshold value

            Cell borders are detected based on the experiences that:
              - compared to cell shading, the size of cell border never exceeds 6 pt
              - compared to text format, cell border always has intersection with other rects

            NOTE: cell shading is determined after the table structure is parsed from these cell borders.
        '''
        # Get all rects with on condition: size < 6 Pt
        thin_rects = [] # type: list[Rectangle]
        for rect in self._instances:
            x0, y0, x1, y1 = rect.bbox_raw
            if min(x1-x0, y1-y0) <= width_threshold:
                thin_rects.append(rect)

        # These thin rects may be cell borders, or text format, e.g. underline within cell.
        # Compared to text format, cell border always has intersection with other rects
        borders = [] # type: list[Rectangle]
        for rect in thin_rects:
            # check intersections with other rect
            for other_rect in thin_rects:
                if rect==other_rect: continue
                # it's a cell border if intersection found
                # Note: if the intersection is an edge, method `intersects` returns False, while
                # the operator `&` return True. So, `&` is used here.
                if rect.bbox & other_rect.bbox: 
                    borders.append(rect)
                    break

        # at least two inner borders exist for a normal table
        if len(borders)>=2:
            # set table border type
            for rect in borders:
                rect.type = RectType.BORDER
            return True
        else:
            return False


    def _unset_table_border(self):
        '''Unset table border type.'''
        for rect in self._instances:
            if rect.type==RectType.BORDER:
                rect.type = RectType.UNDEFINED


    def _collect_explicit_borders(self):
        ''' Collect explicit borders in horizontal and vertical groups respectively.'''        

        h_borders = {} # type: dict [float, Rectangles]
        v_borders = {} # type: dict [float, Rectangles]
        h_outer = []   # type: list[float]
        v_outer = []   # type: list[float]

        for rect in self.border_rects:
            # group horizontal borders in each row
            if rect.bbox.width > rect.bbox.height:
                # row centerline
                y = round((rect.bbox.y0 + rect.bbox.y1) / 2.0, 1)

                # ignore minor error resulting from different border width
                for y_ in h_borders:
                    if abs(y-y_)<utils.DM:
                        h_borders[y_].append(rect)
                        break
                else:
                    h_borders[y] = Rectangles([rect])
                
                # candidates for vertical outer border
                v_outer.extend([rect.bbox.x0, rect.bbox.x1])

            # group vertical borders in each column
            else:
                # column centerline
                x = round((rect.bbox.x0 + rect.bbox.x1) / 2.0, 1)
                
                # ignore minor error resulting from different border width
                for x_ in v_borders:
                    if abs(x-x_)<utils.DM:
                        v_borders[x_].append(rect)
                        break
                else:
                    v_borders[x] = Rectangles([rect])
                
                # candidates for horizontal outer border
                h_outer.extend([rect.bbox.y0, rect.bbox.y1])

        # at least 2 inner borders exist
        if not h_borders or not v_borders:
            return None, None

        # Note: add dummy borders if no outer borders exist
        # check whether outer borders exists in collected borders
        if h_borders:
            top_rects = h_borders[min(h_borders)]
            bottom_rects = h_borders[max(h_borders)]
            left   = min(v_outer)
            right  = max(v_outer)
        else:
            top_rects = Rectangles()
            bottom_rects = Rectangles()
            left   = None
            right  = None

        if v_borders:
            left_rects = v_borders[min(v_borders)]
            right_rects = v_borders[max(v_borders)]
            top   = min(h_outer)
            bottom  = max(h_outer)
        else:
            left_rects = Rectangles()
            right_rects = Rectangles()
            top   = None
            bottom  = None    

        c = utils.RGB_value((1,1,1))
        if not top_rects._exist_outer_border(top, 'h'):
            h_borders[top] = Rectangles([
                Rectangle({
                    'bbox': (left, top, right, top),
                    'color': c
                })])
        if not bottom_rects._exist_outer_border(bottom, 'h'):
            h_borders[bottom] = Rectangles([
                Rectangle({
                    'bbox': (left, bottom, right, bottom),
                    'color': c
                })])
        if not left_rects._exist_outer_border(left, 'v'):
            v_borders[left] = Rectangles([
                Rectangle({
                    'bbox': (left, top, left, bottom),
                    'color': c
                })])
        if not right_rects._exist_outer_border(right, 'v'):
            v_borders[right] = Rectangles([
                Rectangle({
                    'bbox': (right, top, right, bottom),
                    'color': c
                })])

        return h_borders, v_borders


    def _exist_outer_border(self, target:float, direction:str='h') -> bool:
        ''' Check outer borders: whether target border exists in collected borders.
            ---
            Args:
                - target: float, target position of outer border
                - direction: str, 'h'->horizontal border; 'v'->vertical border
        '''
        # no target outer border needed
        if target==None:
            return True

        # need outer border if no borders exist
        if not bool(self):
            return False
        
        # considering direction
        idx = 1 if direction=='h' else 0
        
        # centerline of source borders
        source = round((self._instances[0].bbox_raw[idx+2] + self._instances[0].bbox_raw[idx]) / 2.0, 1)
        # max width of source borders
        width = max(map(lambda rect: rect.bbox_raw[idx+2]-rect.bbox_raw[idx], self._instances))

        target = round(target, 1)
        width = round(width, 1)

        return abs(target-source) <= width


    @staticmethod
    def _check_merged_cells(ref:float, borders:list, direction:str='row'):
        ''' Check merged cells in a row/column. 
            ---
            Args:
              - ref: y (or x) coordinate of horizontal (or vertical) passing-through line
              - borders: list[Rectangles], a list of vertical (or horizontal) rects list in a column (or row)
              - direction: 'row' - check merged cells in row; 'column' - check merged cells in a column

            Taking cells in a row (direction=0) for example, give a horizontal line (y=ref) passing through this row, 
            check the intersection with vertical borders. The n-th cell is merged if no intersection with the n-th border.
            
        '''
        res = [] # type: list[int]
        for rects in borders[0:-1]:
            # multi-lines exist in a row/column
            for rect in rects:

                # reference coordinates depending on checking direction
                if direction=='row':
                    _, ref0, _, ref1 = rect.bbox_raw
                else:
                    ref0, _, ref1, _ = rect.bbox_raw

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


    def _get_rect_with_bbox(self, target:BBox, threshold:float):
        '''Get rect contained in given bbox.
            ---
            Args:
              - target: target bbox
        '''
        s = target.bbox.getArea()
        if not s: return None

        for rect in self._instances:
            intersection = target.bbox & rect.bbox
            if intersection.getArea() / s >= threshold:
                res = rect
                break
        else:
            res = None
        return res


    def _borders_from_bboxes(self, border_bbox:tuple):
        ''' Calculate the surrounding borders of given bbox-es.
            ---
            Args:
              - border_bbox: border of table region
            
            These borders construct table cells. Considering the re-building of cell content in docx, 
              - only one bbox is allowed in a line, 
              - but multi-lines are allowed in a cell.
        '''
        borders = []  # type: list[tuple[float]]

        # collect bbox-ex column by column
        X0, Y0, X1, Y1 = border_bbox
        cols_rects, cols_rect = self._column_borders_from_bboxes()
        col_num = len(cols_rects)

        for i in range(col_num):
            # add column border
            x0 = X0 if i==0 else (cols_rect[i-1].bbox.x1 + cols_rect[i].bbox.x0) / 2.0
            x1 = X1 if i==col_num-1 else (cols_rect[i].bbox.x1 + cols_rect[i+1].bbox.x0) / 2.0

            if i<col_num-1:
                borders.append((x1, Y0, x1, Y1))

            # collect bboxes row by row        
            rows_rects, rows_rect = cols_rects[i]._row_borders_from_bboxes()

            # NOTE: unnecessary to split row if the count of row is 1
            row_num = len(rows_rects)
            if row_num==1: continue
        
            for j in range(row_num):
                # add row border
                y0 = Y0 if j==0 else (rows_rect[j-1].bbox.y1 + rows_rect[j].bbox.y0) / 2.0
                y1 = Y1 if j==row_num-1 else (rows_rect[j].bbox.y1 + rows_rect[j+1].bbox.y0) / 2.0
                
                # it's Ok if single bbox in a line
                if len(rows_rects[j])<2:
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
                _borders = rows_rects[j]._borders_from_bboxes((x0, y0, x1, y1))
                borders.extend(_borders)        

        return borders


    def _column_borders_from_bboxes(self):
        ''' split bbox-es into column groups and add border for adjacent two columns.'''
        # sort bbox-ex in column first mode: from left to right, from top to bottom
        self.sort_in_line_order()
        
        #  bboxes list in each column
        cols_rects = [] # type: list[Rectangles]
        
        # bbox of each column
        cols_rect = [] # type: list[Rectangle]

        # collect bbox-es column by column
        for rect in self._instances:
            col_rect = cols_rect[-1] if cols_rect else Rectangle()

            # same column group if vertically aligned
            if col_rect.vertically_align_with(rect):
                cols_rects[-1].append(rect)
                cols_rect[-1].union(rect.bbox)
            
            # otherwise, start a new column group
            else:
                cols_rects.append(Rectangles([rect]))
                cols_rect.append(rect)    

        return cols_rects, cols_rect


    def _row_borders_from_bboxes(self):
        ''' split bbox-es into row groups and add border for adjacent two rows.'''
        # sort bbox-ex in row first mode: from top to bottom, from left to right
        self.sort_in_reading_order()

        #  bboxes list in each row
        rows_rects = [] # type: list[Rectangles]
        
        # bbox of each row
        rows_rect = [] # type: list[Rectangle]

        # collect bbox-es row by row
        for rect in self._instances:
            row_rect = rows_rect[-1] if rows_rect else Rectangle()

            # same row group if horizontally aligned
            if row_rect.horizontally_align_with(rect):
                rows_rects[-1].append(rect)
                rows_rect[-1].union(rect.bbox)
            
            # otherwise, start a new row group
            else:
                rows_rects.append(Rectangles([rect]))
                rows_rect.append(rect)

        return rows_rects, rows_rect
