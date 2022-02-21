# -*- coding: utf-8 -*-

'''Parsing table structure based on strokes and fills.
'''

import fitz
from ..common.Element import Element
from ..common.share import RectType
from ..common import constants
from ..shape.Shape import Shape, Stroke
from ..shape.Shapes import Shapes
from .TableBlock import TableBlock
from .Row import Row
from .Cell import Cell


class CellStructure:
    '''Cell structure with properties bbox, borders, shading, etc.'''
    def __init__(self, bbox:list):
        # bbox
        self.bbox = fitz.Rect(bbox) # theoretical lattice bbox
        self.merged_bbox = fitz.Rect(bbox) # cell bbox considering merged cells

        # stroke shapes around this cell: top, right, bottom, left
        self.borders = None # type: list[Shape]
        
        # fill shape representing the bg-color
        self.shading = None # type: Shape

        # the count of merged cells in row and col direction:
        # (1, 1) by default -> the cell itself -> no merged cell
        # (3, 2) -> merge 3*2=6 cells (with itself counted as the top-left cell)
        # (0, 0) -> it is merged by other cell
        self.merged_cells = (1,1)

   
    @property
    def is_merged(self): return self.merged_cells[0]==0 or self.merged_cells[1]==0

    @property
    def is_merging(self): return self.merged_cells[0]>1 or self.merged_cells[1]>1


    def parse_borders(self, h_strokes:dict, v_strokes:dict):
        '''Parse cell borders from strokes.
        
        Args:
            h_strokes (dict): A dict of y-coordinate v.s. horizontal strokes, e.g. 
                ``{y0: [h1,h2,..], y1: [h3,h4,...]}``
            v_strokes (dict): A dict of x-coordinates v.s. vertical strokes, e.g. 
                ``{x0: [v1,v2,..], x1: [v3,v4,...]}``
        '''
        x0, y0, x1, y1 = self.merged_bbox
        top = self._get_border_stroke(h_strokes[y0], 'row')
        bottom = self._get_border_stroke(h_strokes[y1], 'row')
        left = self._get_border_stroke(v_strokes[x0], 'col')
        right = self._get_border_stroke(v_strokes[x1], 'col')
        self.borders = (top, bottom, left, right)

    
    def parse_shading(self, fills:Shapes):
        '''Parse cell shading from fills.
        
        Args:
            fills (Shapes): Fill shapes representing cell shading.
        '''
        # border width
        top, bottom, left, right = self.borders
        w_top = top.width
        w_right = right.width
        w_bottom = bottom.width
        w_left = left.width

        # modify the cell bbox from border center to inner region
        x0, y0, x1, y1 = self.merged_bbox
        inner_bbox = (x0+w_left/2.0, y0+w_top/2.0, x1-w_right/2.0, y1-w_bottom/2.0)
        target = Element().update_bbox(inner_bbox)

        # shading shape of this cell        
        for shape in fills:
            if shape.contains(target, threshold=constants.FACTOR_MOST):
                self.shading = shape
                break
        else:
            self.shading = None


    def _get_border_stroke(self, strokes:Shapes, direction:str='row'):
        ''' Find strokes representing cell borders.
        
        Args:
            strokes (Shapes): Candidate stroke shapes for cell border.
            direction (str): Either ``row`` or ``col``.
        '''
        if not strokes: return Stroke()

        # depends on border direction
        idx = 0 if direction=='row' else 1

        # cell range
        x0, x1 = self.merged_bbox[idx], self.merged_bbox[idx+2]

        # check all candidate strokes
        L = 0.0
        border_strokes = []
        for stroke in strokes:
            bbox = (stroke.x0, stroke.y0, stroke.x1, stroke.y1)
            t0, t1 = bbox[idx], bbox[idx+2]
            if t1 <= x0: continue
            if t0 >= x1: break
            # intersection length
            dl = min(x1, t1) - max(x0, t0)
            # NOTE to ignore small intersection on end point
            if dl < constants.MAJOR_DIST: continue 
            L += dl
            border_strokes.append(stroke)
        
        # use an empty stroke if nothing found, especially for merged cells.
        # no worry since the border style will be set correctly by adjacent separate cells.
        if L/(x1-x0) < constants.FACTOR_MAJOR: return Stroke()

        # the entire border of merged cell must have same property, i.e. width and color
        # otherwise, set empty stroke here and let adjacent cells set the correct style separately
        if len(border_strokes)==1: return border_strokes[0]

        properties = set([stroke.color for stroke in border_strokes])
        return border_strokes[0] if len(properties)==1 else Stroke()


class TableStructure:
    '''Parsing table structure based on strokes/fills.
    
    Steps to parse table structure::

            x0        x1       x2        x3
        y0  +----h1---+---h2---+----h3---+
            |         |        |         |
            v1        v2       v3        v4
            |         |        |         |
        y1  +----h4------------+----h5---+
            |                  |         |
            v5                 v6        v7
            |                  |         |
        y2  +--------h6--------+----h7---+
        

    1. Group horizontal and vertical strokes::
        
        self.h_strokes = {
            y0 : [h1, h2, h3],
            y1 : [h4, h5],
            y2 : [h6, h7]
        }
    
    These ``[x0, x1, x2, x3] x [y0, y1, y2]`` forms table lattices, i.e. 2 rows x 3 cols.

    2. Check merged cells in row/column direction.

    Let horizontal line ``y=(y0+y1)/2`` cross through table, it gets intersection with 
    ``v1``, ``v2`` and ``v3``, indicating no merging exists for cells in the first row.

    When ``y=(y1+y2)/2``, it has no intersection with vertical strokes at ``x=x1``, i.e. 
    merging status is ``[1, 0, 1]``, indicating ``Cell(2,2)`` is merged into ``Cell(2,1)``.

    So, the final merging status in this case::

        [
            [(1,1), (1,1), (1,1)],
            [(1,2), (0,0), (1,1)]
        ]
    '''

    def __init__(self, strokes:Shapes, **settings):
        '''Parse table structure from strokes and fills shapes.
        
        Args:
            strokes (Shapes): Stroke shapes representing table border. 
                For lattice table, they're retrieved from PDF raw contents; 
                for stream table, they're determined from layout of text blocks.

        .. note::
            Strokes must be sorted in reading order in advance, required by checking merged cells.        
        '''
        # cells
        self.cells = [] # type: list[list[CellStructure]]

        # group horizontal/vertical strokes -> table structure dict
        self.h_strokes, self.v_strokes = TableStructure._group_h_v_strokes(strokes, 
                        settings['min_border_clearance'], 
                        settings['max_border_width'])
        if not self.h_strokes or not self.v_strokes: return

        # initialize cells
        self.cells = self._init_cells()
        
    
    @property
    def bbox(self):
        '''Table boundary bbox.

        Returns:
            fitz.Rect: bbox of table.
        '''
        if not self.cells: return fitz.Rect()
        x0, y0 = self.cells[0][0].bbox.tl
        x1, y1 = self.cells[-1][-1].bbox.br
        return fitz.Rect(x0,y0,x1,y1)

    @property
    def num_rows(self): return len(self.cells)

    @property
    def num_cols(self): return len(self.cells[0]) if self.cells else 0

    @property
    def y_rows(self):
        """Top y-coordinate ``y0`` of each row.

        Returns:
            list: y-coordinates of each row.
        """        
        if not self.cells: return []
        Y = [row[0].bbox.y0 for row in self.cells]
        Y.append(self.cells[-1][0].bbox.y1)
        return Y

    @property
    def x_cols(self):
        """Left x-coordinate ``x0`` of each column.

        Returns:
            list: x-coordinates of each column.
        """  
        if not self.cells: return []
        X = [cell.bbox.x0 for cell in self.cells[0]]
        X.append(self.cells[0][-1].bbox.x1)
        return X


    def parse(self, fills:Shapes):
        '''Parse table structure.
        
        Args:
            fills (Shapes): Fill shapes representing cell shading.
        '''
        if not self.cells: return self

        # check merged cells
        self._check_merging_status()

        # check cell borders/shadings
        for row in self.cells:
            for cell in row:
                if cell.is_merged: continue
                cell.parse_borders(self.h_strokes, self.v_strokes)
                cell.parse_shading(fills)
        
        return self

    
    def to_table_block(self):
        '''Convert parsed table structure to ``TableBlock`` instance.

        Returns:
            TableBlock: Parsed table block instance.
        '''
        table = TableBlock()
        for row_structures in self.cells:
            # row object
            row = Row()
            row.height = row_structures[0].bbox.y1-row_structures[0].bbox.y0
            for cell_structure in row_structures:
                # if current cell is merged horizontally or vertically, set None.
                # actually, it will be counted in the top-left cell of the merged range.
                if cell_structure.is_merged:
                    row.append(Cell())
                    continue

                # cell borders properties
                top, bottom, left, right = cell_structure.borders
                w_top = top.width
                w_right = right.width
                w_bottom = bottom.width
                w_left = left.width

                # cell bg-color
                bg_color = cell_structure.shading.color if cell_structure.shading else None

                # Cell object
                # Note that cell bbox is calculated under real page CS, so needn't to consider rotation.
                cell = Cell({
                    'bg_color':  bg_color,
                    'border_color': (top.color, right.color, bottom.color, left.color),
                    'border_width': (w_top, w_right, w_bottom, w_left),
                    'merged_cells': cell_structure.merged_cells,
                }).update_bbox(cell_structure.merged_bbox)

                # add cell to row
                row.append(cell)                    
            
            # add row to table
            table.append(row)

        # finalize table structure
        if table: self._finalize_strokes_fills()

        return table


    def _finalize_strokes_fills(self):
        '''Finalize table structure, so set strokes and fills type as BORDER and SHADING accordingly.'''
        # strokes -> borders
        for k, strokes in self.h_strokes.items():
            for stroke in strokes: stroke.type = RectType.BORDER
        
        for k, strokes in self.v_strokes.items():
            for stroke in strokes: stroke.type = RectType.BORDER
        
        # fills -> shadings
        for row in self.cells:
            for cell in row:
                if cell.shading: cell.shading.type = RectType.SHADING


    @staticmethod
    def _group_h_v_strokes(strokes:Shapes, min_border_clearance:float, max_border_width:float):
        '''Split strokes in horizontal and vertical groups respectively.

        According to strokes below, the grouped h-strokes looks like::

            h_strokes = {
                y0 : [h1, h2, h3],
                y1 : [h4, h5],
                y2 : [h6, h7]
            }

               x0        x1        x2        x3
            y0  +----h1---+---h2---+----h3---+
                |         |        |         |
                v1        v2       v3        v4
                |         |        |         |
            y1  +----h4------------+----h5---+
                |                  |         |
                v5                 v6        v7
                |                  |         |
            y2  +--------h6--------+----h7---+

        '''
        def group_strokes(stroke:Shape, strokes:dict):
            # y-coordinate of h-strokes or x-coordinate of v-strokes
            t = round(stroke.y0, 1) if stroke.horizontal else round(stroke.x0, 1)

            # ignore minor error resulting from different stroke width
            for t_ in strokes:
                if abs(t-t_)>min_border_clearance: continue
                t = (t_+t)/2.0 # average
                strokes[t] = strokes.pop(t_)
                strokes[t].append(stroke)
                break
            else:
                strokes[t] = Shapes([stroke])
        
        h_strokes = {} # type: dict [float, Shapes]
        v_strokes = {} # type: dict [float, Shapes]
        X0, Y0, X1, Y1 = float('inf'), float('inf'), -float('inf'), -float('inf')
        for stroke in strokes:
            # group horizontal/vertical strokes in each row/column
            group_strokes(stroke, h_strokes if stroke.horizontal else v_strokes)

            # update table region
            X0 = min(X0, stroke.x0)
            X1 = max(X1, stroke.x1)
            Y0 = min(Y0, stroke.y0)
            Y1 = max(Y1, stroke.y1)

        # at least 2 inner strokes exist
        if not h_strokes or not v_strokes: return None, None

        # Note: add dummy strokes if no outer strokes exist        
        table_bbox = Element().update_bbox((X0, Y0, X1, Y1)) # table bbox
        TableStructure._check_outer_strokes(table_bbox, h_strokes, 'top', max_border_width)
        TableStructure._check_outer_strokes(table_bbox, h_strokes, 'bottom', max_border_width)
        TableStructure._check_outer_strokes(table_bbox, v_strokes, 'left', max_border_width)
        TableStructure._check_outer_strokes(table_bbox, v_strokes, 'right', max_border_width)

        # ATTENTION: sort in advance to avoid mistake when checking cell merging status
        for _, borders in h_strokes.items(): borders.sort_in_line_order()        
        for _, borders in v_strokes.items(): borders.sort_in_reading_order()

        return h_strokes, v_strokes
    

    def _init_cells(self):
        '''Initialize table lattices.'''
        # sort keys of borders -> table rows/cols coordinates
        y_rows = sorted(self.h_strokes)
        x_cols = sorted(self.v_strokes)

        # each lattice is a cell
        cells = []
        for i in range(len(y_rows)-1):
            y0, y1 = y_rows[i], y_rows[i+1]
            cells.append([]) # append a row
            for j in range(len(x_cols)-1):
                x0, x1 = x_cols[j], x_cols[j+1]
                cell = CellStructure([x0, y0, x1, y1])
                cells[-1].append(cell)
        
        return cells


    def _check_merging_status(self):
        '''Check cell merging status.'''
        x_cols, y_rows = self.x_cols, self.y_rows
        # check cell merging status in each row
        merged_cells_rows = []  # type: list[list[int]]
        ordered_strokes = [self.v_strokes[k] for k in x_cols]
        for row in self.cells:
            ref_y = (row[0].bbox.y0+row[0].bbox.y1)/2.0
            row_structure = TableStructure._check_merged_cells(ref_y, ordered_strokes, 'row')
            merged_cells_rows.append(row_structure)

        # check cell merging status in each column
        merged_cells_cols = []  # type: list[list[int]]
        ordered_strokes = [self.h_strokes[k] for k in y_rows]
        for cell in self.cells[0]:
            ref_x = (cell.bbox.x0+cell.bbox.x1)/2.0
            col_structure = TableStructure._check_merged_cells(ref_x, ordered_strokes, 'column')
            merged_cells_cols.append(col_structure)

        # count merged cells in row and column directions
        for i in range(self.num_rows):
            for j in range(self.num_cols):
                cell = self.cells[i][j]
                n_col = TableStructure._count_merged_cells(merged_cells_rows[i][j:])
                n_row = TableStructure._count_merged_cells(merged_cells_cols[j][i:])                
                cell.merged_cells = (n_row, n_col)        

        # check whether merged region is valid
        for i in range(self.num_rows):
            for j in range(self.num_cols):
                # validate region
                self._validate_merging_region(i, j)

                # update merged bbox
                # A separate cell without merging can also be treated as a merged range 
                # with 1 row and 1 colum, i.e. itself.
                cell = self.cells[i][j]               
                n_row, n_col = cell.merged_cells
                bbox = (x_cols[j], y_rows[i], x_cols[j+n_col], y_rows[i+n_row])
                cell.merged_bbox = fitz.Rect(bbox)

    
    @staticmethod
    def _check_outer_strokes(table_bbox:Element, borders:dict, direction:str, max_border_width:float):
        '''Add missing outer borders based on table bbox and grouped horizontal/vertical borders.
        
        Args:
            * table_bbox (Element): Table region.
            * borders (dict): Grouped horizontal (or vertical) borders at y-coordinates.
            * direction (str): Either ``top`` or ``bottom`` or ``left`` or ``right``.
        '''
        # target / real borders
        bbox = list(table_bbox.bbox)
        if direction=='top':
            idx = 1
            current = min(borders)
            borders[current].sort_in_line_order()
        elif direction=='bottom':
            idx = 3
            current = max(borders)
            borders[current].sort_in_line_order()
        elif direction=='left':
            idx = 0
            current = min(borders)
            borders[current].sort_in_reading_order()
        elif direction=='right':
            idx = 2
            current = max(borders)
            borders[current].sort_in_reading_order()
        else:
            return
        target = bbox[idx]
        
        # add missing border rects
        sample_border = Stroke()        
        bbox[idx] = target
        bbox[(idx+2)%4] = target

        # add whole border if not exist
        if abs(target-current)> max_border_width:
            borders[target] = Shapes([sample_border.copy().update_bbox(bbox)])
        
        # otherwise, check border segments
        else:
            idx_start = (idx+1)%2 # 0, 1
            idx_end = idx_start+2

            occupied = [(border.bbox[idx_start], 
                        border.bbox[idx_end]) for border in borders[current]]
            occupied.append((bbox[idx_end], None)) # end point
            start = bbox[idx_start] # start point
            segments = []
            for (left, right) in occupied:
                end = left
                # not connected -> add missing border segment
                if abs(start-end)>constants.MINOR_DIST:
                    bbox[idx_start] = start
                    bbox[idx_start+2] = end
                    segments.append(sample_border.copy().update_bbox(bbox))
                
                # update ref position
                start = right
            
            borders[current].extend(segments)


    @staticmethod
    def _check_merged_cells(ref:float, borders:list, direction:str='row'):
        '''Check merged cells in a row/column. 
        
        Args:
            * ref (float): y (or x) coordinate of horizontal (or vertical) passing-through line.
            * borders (list[Shapes]): A list of vertical (or horizontal) rects list in a column (or row).
            * direction (str): ``row`` - check merged cells in row; ``column`` - check merged cells in a column.

        Taking cells in a row for example, give a horizontal line ``y=ref`` passing through this row, 
        check the intersection with vertical borders. The ``n-th`` cell is merged if no intersection 
        with the ``n-th`` border.
            
                +-----+-----+-----+
                |     |     |     |
                |     |     |     |
                +-----+-----------+
                |           |     |
            ----1-----0-----1----------> [1,0,1]
                |           |     |
                |           |     |
                +-----------+-----+
        '''
        res = [] # type: list[int]
        for shapes in borders[0:-1]:
            # NOTE: shapes MUST be sorted in reading order!!
            # multi-lines exist in a row/column
            for border in shapes:
                # reference coordinates depending on checking direction
                if direction=='row':
                    ref0, ref1 = border.y0, border.y1
                else:
                    ref0, ref1 = border.x0, border.x1

                # 1) intersection found
                if ref0 < ref < ref1:
                    res.append(1)
                    break
                
                # 2) reference line locates below current border:
                # still have a chance to find intersection with next border, but,
                # no chance if this is the last border, see the else-clause
                elif ref > ref1:
                    continue

                # 3) current border locates below the reference line:
                # no intersection is possible any more
                elif ref < ref0:
                    res.append(0)
                    break
            
            # see notes 2), no change any more
            else:
                res.append(0)

        return res


    @staticmethod
    def _count_merged_cells(merging_status:list):
        '''Count merged cells, 
        e.g. ``[1,0,0,1]`` -> the second and third cells are merged into the first one.
        
        Args:
            merging_status (list): A list of 0-1 representing cell merging status.
        '''
        # it's merged by other cell
        if merging_status[0]==0: return 0
        
        # check a continuous sequence of 0 status
        num = 1
        for val in merging_status[1:]:
            if val==0:
                num += 1
            else: 
                break            
        return num
    

    def _validate_merging_region(self, i:int, j:int):
        '''Check whether the merging region of Cell (i,j) is valid. If not, unset merging status. 

        Args:
            i (int): Row index of the target cell.
            j (int): Column index of the target cell.
        '''
        cell = self.cells[i][j]
        if cell.is_merged: return

        # merged cells count
        n_row, n_col = cell.merged_cells 
        if n_row==1 and n_col==1: return

        # unset merging status if invalid merging region
        if not self._is_valid_region(i, i+n_row, j, j+n_col):
            for m in range(i, i+n_row):
                for n in range(j, j+n_col):
                    target = self.cells[m][n]
                    if target.is_merged: target.merged_cells = (1, 1)
            # reset current cell
            cell.merged_cells = (1, 1)        


    def _is_valid_region(self, row_start:int, row_end:int, col_start:int, col_end:int):
        '''Check whether all cells in given region are marked to merge.

        Args:
            row_start (int): Start row index (included) of the target region.
            row_end (int): End row index (excluded) of the target region.
            col_start (int): Start column index (included) of the target region.
            col_end (int): Start column index (excluded) of the target region.
        '''
        for i in range(row_start, row_end):
            for j in range(col_start, col_end):
                if i==row_start and j==col_start: continue # skip top-left cell
                if not self.cells[i][j].is_merged:
                    return False
        return True

