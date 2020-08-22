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

from ..table.Row import Row
from ..table.Cell import Cell
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

            # add table to page level
            table.set_lattice_table_block()
            self._blocks.append(table)

        # assign text contents to each table
        self._blocks.assign_table_contents()

        return self._blocks.lattice_table_blocks

    
    def stream_tables(self, X0:float, X1:float):
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
        for table_lines in tables_lines:
            # parse borders based on contents in cell
            table_rects = self._stream_borders(table_lines, X0, X1)

            # get potential cell shading
            table_bbox = table_rects.bbox
            table_rects.extend(filter(
                lambda rect: table_bbox.intersects(rect.bbox), self._rects))

            # parse table: don't have to detect borders since it's determined already
            table_rects.sort_in_reading_order() # required
            table = self.parse_structure(table_rects, detect_border=False)

            # add parsed table to page level blocks
            # in addition, ignore table if contains only one cell since it's unnecessary for stream table
            if table and (table.num_rows>1 or table.num_cols>1):
                table.set_stream_table_block()
                self._blocks.append(table)

        # assign text contents to each table
        self._blocks.assign_table_contents()

        return self._blocks.stream_table_blocks


    def _stream_borders(self, lines:Lines, X0:float, X1:float):
        ''' Parsing borders based on lines contained in table cells.
            ---
            Args:
            - lines: Lines, contained in table cells
            - X0, X1: default left and right outer borders
        '''
        # boundary box (considering margin) of all line box
        margin = 1
        x0 = X0 - margin
        y0 = min([rect.bbox.y0 for rect in lines]) - margin
        x1 = X1 + margin
        y1 = max([rect.bbox.y1 for rect in lines]) + margin
        border_bbox = (x0, y0, x1, y1)

        # centerline of outer borders
        borders = [
            (x0, y0, x1, y0), # top
            (x1, y0, x1, y1), # right
            (x0, y1, x1, y1), # bottom
            (x0, y0, x0, y1)  # left
        ]

        # centerline of inner borders
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