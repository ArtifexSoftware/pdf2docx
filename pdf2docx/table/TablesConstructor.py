# -*- coding: utf-8 -*-

'''
Parsing table blocks:
- lattice table: explicit borders represented by rectangles
- stream table : borderless table recognized from layout of text blocks.

@created: 2020-08-16
@author: train8808@gmail.com
'''

from ..common.BBox import BBox
from ..common.base import RectType
from ..common import utils
from ..layout.Blocks import Blocks
from ..shape.Rectangle import Rectangle
from ..shape.Rectangles import Rectangles
from .TableStructure import TableStructure
from ..text.Lines import Lines


class TablesConstructor(TableStructure):

    def __init__(self, blocks:Blocks, rects:Rectangles):
        '''Object parsing TableBlock.'''
        self._blocks = blocks
        self._rects = rects


    def lattice_tables(self):
        '''Parse table with explicit borders/shadings represented by rectangle shapes.'''
        # group rects: each group may be a potential table
        fun = lambda a,b: a.bbox & b.bbox
        groups = self._rects.group(fun)

        # parse table with each group
        tables = Blocks()
        for group in groups:
            # parse table structure based on rects in border type
            table = self.parse_structure(group, detect_border=True)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add table to page level
            table.set_lattice_table_block()
            self._blocks.append(table)

        # assign text contents to each table
        self._blocks.assign_table_contents()

        return self._blocks.lattice_table_blocks


    def combined_tables(self):
        ''' Parse table with outer borders extracted from shading rects, 
            and inner borders parsed from layout of text blocks.

            Combined with lattice and stream table parsing methods, this table 
            is to simulate the shading shape in docx. 
        '''
        shading_rects = self._shading_rects(width_threshold=6.0)

        # table based on each shading rect
        tables = Blocks()
        for rect in shading_rects:
            # outer borders
            x0, y0, x1, y1 = rect.bbox_raw
            outer_borders = [
                (x0, y0, x1, y0),
                (x1, y0, x1, y1),
                (x0, y1, x1, y1),
                (x0, y0, x0, y1)
            ]

            # lines contained in shading rect
            table_lines = Lines()
            for block in self._blocks:
                if rect.bbox.contains(block.bbox):
                    table_lines.extend(block.lines)
            
            # parse borders based on contents in cell
            table_rects = self._stream_borders(table_lines, detect_border=False, outer_borders=outer_borders)
            if not table_rects: continue

            # get potential cell shading
            table_bbox = table_rects.bbox
            table_rects.extend(filter(
                lambda rect: table_bbox.intersects(rect.bbox), self._rects))

            # parse table: don't have to detect borders since it's determined already
            table_rects.sort_in_reading_order() # required
            table = self.parse_structure(table_rects, detect_border=False)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add parsed table to page level blocks
            table.set_stream_table_block()
            self._blocks.append(table)

        # assign text contents to each table
        self._blocks.assign_table_contents()

        return self._blocks.stream_table_blocks


    def stream_tables(self, X0:float=-1, X1:float=-1):
        ''' Parse borderless table based on the layout of text/image blocks.
            ---
            Args:
            - X0, X1: left and right boundaries of allowed table region

            Since no cell borders exist in this case, there may be various probabilities of table structures. 
            Among which, we use the simplest one, i.e. 1-row and n-column, to make the docx look like pdf.

            Ensure no horizontally aligned blocks in each column, so that these blocks can be converted to
            paragraphs consequently in docx.
        '''    
        if len(self._blocks)<=1: return []      

        # potential bboxes
        tables_lines = self._blocks.collect_stream_lines()

        # parse tables
        tables = Blocks()
        for table_lines in tables_lines:
            # parse borders based on contents in cell
            table_rects = self._stream_borders(table_lines, detect_border=True, boundary=(X0, X1))
            if not table_rects: continue

            # get potential cell shading
            table_bbox = table_rects.bbox
            table_rects.extend(filter(
                lambda rect: table_bbox.intersects(rect.bbox), self._rects))

            # parse table: don't have to detect borders since it's determined already
            table_rects.sort_in_reading_order() # required
            table = self.parse_structure(table_rects, detect_border=False)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add parsed table to page level blocks
            # in addition, ignore table if contains only one cell since it's unnecessary for stream table
            if table.num_rows>1 or table.num_cols>1:
                table.set_stream_table_block()
                self._blocks.append(table)

        # assign text contents to each table
        self._blocks.assign_table_contents()

        return self._blocks.stream_table_blocks


    @staticmethod
    def _remove_floating_tables(tables:Blocks):
        '''Delete table has intersection with previously parsed tables.'''
        unique_tables = []
        fun = lambda a,b: a.bbox & b.bbox
        for group in tables.group(fun):
            # single table
            if len(group)==1:
                table = group[0]
            
            # intersected tables: keep the table with the most cells only 
            # since no floating elements are supported with python-docx
            else:
                sorted_group = sorted(group, 
                            key=lambda table: table.num_rows*table.num_cols)
                table = sorted_group[-1]
            
            unique_tables.append(table)
        
        return unique_tables


    def _shading_rects(self, width_threshold:float=6.0):
        ''' Detect shading rects.
            ---
            Args:
            - width_threshold: float, suppose shading rect width is larger than this value

            NOTE: Shading borders are checked after parsing lattice tables.            
            
            Note to distinguish shading shape and highlight: 
            - there exists at least one text block contained in shading rect,
            - or no any intersetions with other text blocks (empty block is deleted already);
            - otherwise, highlight rect
        '''
        # lattice tables
        lattice_tables = self._blocks.lattice_table_blocks

        # check rects
        shading_rects = [] # type: list[Rectangle]
        for rect in self._rects:

            # focus on rect not parsed yet
            if rect.type != RectType.UNDEFINED: continue

            # not in lattice table region
            for table in lattice_tables:
                if table.bbox.contains(rect.bbox):
                    skip = True
                    break
            else:
                skip = False
            if skip: continue

            # potential shading rects: min-width > 6 Pt
            x0, y0, x1, y1 = rect.bbox_raw
            if min(x1-x0, y1-y0) <= width_threshold:
                continue

            # now shading rect or highlight rect:
            # shading rect contains at least one text block
            shading = False
            expand_bbox = rect.bbox + utils.DR / 0.2 # expand 2.5 Pt
            for block in self._blocks:
                if expand_bbox.contains(block.bbox):
                    shading = True
                    break

                # do not containing but intersecting with text block -> can't be shading rect
                elif expand_bbox.intersects(block.bbox):
                    break
                
                # no chance any more
                elif block.bbox.y0 > rect.bbox.y1: 
                    break
            
            if shading:
                shading_rects.append(rect)            

        return shading_rects


    def _stream_borders(self, lines:Lines, detect_border:bool=True, **kwargs):
        ''' Parsing borders based on lines contained in table cells.
            ---
            Args:
            - lines: Lines, contained in table cells
            - detect_border: detect outer borders automatically if True, otherwise use given borders
            - kwargs:
              - outer_borders: list of outer borders when `detect_border` is False
              - boundary: tuple of (X0, X1), default left and right outer borders when `detect_border` is True
        '''
        # detect outer borders automatically
        if detect_border:
            X0, X1 = kwargs.get('boundary', (None, None))
            if X0 is None: return None

            # boundary box (considering margin) of all line box
            margin = 1
            x0 = X0 - margin
            y0 = min([rect.bbox.y0 for rect in lines]) - margin
            x1 = X1 + margin
            y1 = max([rect.bbox.y1 for rect in lines]) + margin

            # centerline of outer borders
            borders = [
                (x0, y0, x1, y0), # top
                (x1, y0, x1, y1), # right
                (x0, y1, x1, y1), # bottom
                (x0, y0, x0, y1)  # left
            ]

        # use specified outer borders
        else:
            borders = kwargs.get('outer_borders', None)
            if not borders: return None

            # bbox of lines region
            x0 = min([border[0] for border in borders])
            y0 = min([border[1] for border in borders])
            x1 = max([border[2] for border in borders])
            y1 = max([border[3] for border in borders])

        # centerline of inner borders
        border_bbox = (x0, y0, x1, y1)
        inner_borders = self._borders_from_lines(lines, border_bbox)
        borders.extend(inner_borders)
        
        # all centerlines to rectangle shapes
        res = Rectangles()
        color = utils.RGB_value((1,1,1))

        for border in borders: 
            # set an non-zero width for border check; won't draw border in docx for stream table
            bbox = utils.expand_centerline(border[0:2], border[2:], width=0.2) 
            if not bbox: continue

            # create Rectangle object and set border style
            rect = Rectangle({
                'bbox': bbox,
                'color': color
            })
            rect.type = RectType.BORDER
            res.append(rect)

        return res


    def _borders_from_lines(self, lines:Lines, border_bbox:tuple):
        ''' Calculate the surrounding borders of given lines.
            ---
            Args:
            - lines: lines in table cells
            - border_bbox: boundary box of table region

            These borders construct table cells. Considering the re-building of cell content in docx, 
            - only one bbox is allowed in a line;
            - but multi-lines are allowed in a cell.

            Two purposes of stream table: 
            - rebuild layout, e.g. text layout with two columns
            - parsing real borderless table

            It's controdictory that the former needn't to deep into row level, just 1 x N table convenient for layout recreation;
            instead, the later should, M x N table for each cell precisely.
            So, the principle determining borders for stream tables here:
            - two columns: layout if the rows count in each column is different; otherwise, it's a real table
            - otherwise: real table -> deep into rows
        '''
        # trying: deep into cells        
        cols_lines = lines.group_by_columns()
        group_lines = [col_lines.group_by_rows() for col_lines in cols_lines]

        # real table or just text layout?
        col_num = len(cols_lines)
        real_table = True # table by default
        if col_num==2:
            # It's regarded as layout if row count is different, or the count is 1
            left, right = len(group_lines[0]), len(group_lines[1])
            if left!=right or left==1:
                real_table = False

        # detect borders based on table/layout mode
        borders = set()  # type: set[tuple[float]]        
        X0, Y0, X1, Y1 = border_bbox 
        
        # collect lines column by column
        for i in range(col_num): 

            # add column border
            x0 = X0 if i==0 else (cols_lines[i-1].bbox.x1 + cols_lines[i].bbox.x0) / 2.0
            x1 = X1 if i==col_num-1 else (cols_lines[i].bbox.x1 + cols_lines[i+1].bbox.x0) / 2.0

            if i<col_num-1:
                borders.add((x1, Y0, x1, Y1)) # right border of current column

            
            # NOTE: unnecessary to split row if the count of row is 1
            rows_lines = group_lines[i]
            row_num = len(rows_lines)
            if row_num==1: continue
        
            # collect bboxes row by row 
            for j in range(row_num): 

                # add row border
                y0 = Y0 if j==0 else (rows_lines[j-1].bbox.y1 + rows_lines[j].bbox.y0) / 2.0
                y1 = Y1 if j==row_num-1 else (rows_lines[j].bbox.y1 + rows_lines[j+1].bbox.y0) / 2.0
                
                # needn't go to row level if layout mode
                if not real_table:
                    continue

                # otherwise, add row borders
                if j==0:
                    borders.add((x0, y1, x1, y1)) # bottom border for first row
                elif j==row_num-1:
                    borders.add((x0, y0, x1, y0)) # top border for last row
                else:
                    # both top and bottom borders added, even though duplicates exist since
                    # top border of current row may be considered already when process bottom border of previous row.
                    # So, variable `borders` is a set here
                    borders.add((x0, y0, x1, y0))
                    borders.add((x0, y1, x1, y1))

                # recursion to check borders further
                borders_ = self._borders_from_lines(rows_lines[j], (x0, y0, x1, y1))
                borders = borders | borders_

        return borders