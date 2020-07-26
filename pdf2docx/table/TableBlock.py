# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.

@created: 2020-07-22
@author: train8808@gmail.com
---

{
    'type': int
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border_color': (sRGB,,,), # top, right, bottom, left
            'bg_color': sRGB,
            'border_width': (,,,),
            'merged_cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'blocks': [
                text blocks
            ]
        }, # end of cell

        None,  # merged cell

        ...,   # more cells
    ], # end of row

    ...] # more rows    
}

'''

from .Cell import Cell
from . import functions
from ..common.Block import Block
from ..common.base import RectType
from ..common import utils



class TableBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(TableBlock, self).__init__(raw)

        self.cells = [] # type: list[list[Cell]]
        for row in raw.get('cells', []):            
            row_obj = [Cell(cell) for cell in row] # type: list [Cell]
            self.cells.append(row_obj)

        # explicit table by default
        self.set_explicit_table_block()

    @property
    def text(self) -> list:
        '''Get text contained in each cell.'''
        return [ [cell.text for cell in row] for row in self.cells ]


    def store(self) -> dict:
        res = super().store()
        res.update({
            'cells': [ [cell.store() for cell in row] for row in self.cells]
        })
        return res


    def plot(self, page, content=True, style=False):
        '''Plot table block, i.e. cell/line/span.
            ---
            Args:
              - page: fitz.Page object
              - style: plot cell style if True, e.g. border width, shading
              - content: plot text blocks if True
        '''
        for row in self.cells:
            for cell in row:
                # ignore merged cells
                if not cell: continue            
                
                # plot different border colors for explicit / implicit tables when style=False, 
                # i.e. table illustration, rather than real style of explicit table
                bc = (1,0,0) if self.is_explicit_table_block() else (0.6,0.7,0.8)
                cell.plot(page, content=content, style=style, color=bc)

    
    def parse_structure(self, rects:list) -> bool:
        ''' Parse table structure from rects in table border/shading type.
            Args:
              - rects: list[Rectangle], source rects representing table borders, shadings
        '''
        # --------------------------------------------------
        # group horizontal/vertical borders
        # --------------------------------------------------
        h_borders, v_borders = functions.collect_explicit_borders(rects)
        if not h_borders or not v_borders:
            return False

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
            row_structure = functions.check_merged_cells(ref_y, ordered_v_borders, 'row')
            merged_cells_rows.append(row_structure)

        # check merged cells in each column
        merged_cells_cols = []  # type: list[list[int]]
        for i, col in enumerate(cols[0:-1]):
            ref_x = (col+cols[i+1])/2.0
            ordered_h_borders = [h_borders[k] for k in rows]
            col_structure = functions.check_merged_cells(ref_x, ordered_h_borders, 'column')        
            merged_cells_cols.append(col_structure)

        # --------------------------------------------------
        # parse table properties
        # --------------------------------------------------
        cells = []  # type: list[list[Cell]]
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
                shading_rect = functions.get_rect_with_bbox(inner_bbox, rects, threshold=0.9)
                if shading_rect:
                    shading_rect.type = RectType.SHADING # set shaing type
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
            if i==0 and cells_in_row[0]==None:
                return False

            cells.append(cells_in_row)

        # update table
        self.update((cols[0], rows[0], cols[-1], rows[-1]))
        self.cells = cells

        return True


    def parse_text_format(self, rects) -> bool:
        '''Parse text format for blocks contained in each cell.
            ---
            Args:
              - rects: Rectangles, format styles are represented by these rectangles.
        '''
        for row in self.cells:
            for cell in row:
                if not cell: continue
                cell.blocks.parse_text_format(rects)
        
        return True # always return True if table is parsed


    def parse_vertical_spacing(self):
        ''' Calculate vertical space for blocks contained in table cells.'''
        for row in self.cells:
            for cell in row:
                if not cell: continue
                y0 = cell.bbox.y0
                w_top = cell.border_width[0]
                cell.blocks.parse_vertical_spacing(y0+w_top/2.0)


    def make_docx(self, table, page_margin:tuple):
        '''Create docx table.
            ---
            Args:
              - table: docx table instance
              - page_margin: page margin (left, right, top, bottom)
        '''
        # set indent
        left, *_ = page_margin
        pos = self.bbox.x0-left
        utils.indent_table(table, pos)

        # cell format and contents
        border_style = self.is_explicit_table_block() # set border style for explicit table only
        for i in range(len(table.rows)):
            for j in range(len(table.columns)):           

                # ignore merged cells
                block_cell = self.cells[i][j] # type: Cell
                if not block_cell: continue
                
                # set cell style
                # no borders for implicit table
                block_cell.set_style(table, (i,j), border_style)

                # clear cell margin
                # NOTE: the start position of a table is based on text in cell, rather than left border of table. 
                # They're almost aligned if left-margin of cell is zero.
                cell = table.cell(i, j)
                utils.set_cell_margins(cell, start=0, end=0)

                # insert text            
                first = True
                x0, _, x1, _ = block_cell.bbox_raw
                for block in block_cell.blocks:
                    if first:
                        p = cell.paragraphs[0]
                        first = False
                    else:
                        p = cell.add_paragraph()
                    block.make_docx(p, x0)
