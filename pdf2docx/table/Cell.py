# -*- coding: utf-8 -*-

'''
Table Cell object.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from docx.shared import Pt
from docx.enum.table import WD_ROW_HEIGHT
from ..text.TextBlock import TextBlock
from ..common.BBox import BBox
from ..common.utils import RGB_component
from ..common.docx import set_cell_border, set_cell_shading
from ..layout import Blocks # avoid conflict


class Cell(BBox):
    ''' Cell object.'''
    def __init__(self, raw:dict={}):
        if raw is None: raw = {}
        super(Cell, self).__init__(raw)
        self.bg_color = raw.get('bg_color', None) # type: int
        self.border_color = raw.get('border_color', None) # type: tuple [int]
        self.border_width = raw.get('border_width', None) # type: tuple [float]
        self.merged_cells = raw.get('merged_cells', (1,1)) # type: tuple [int]

        # collect blocks
        # NOTE: The cell bbox is determined first, and then find blocks contained in this bbox.
        # so, don't update cell bbox when appending blocks, i.e. set parent=None.
        self.blocks = Blocks.Blocks().from_dicts(raw.get('blocks', []))


    @property
    def text(self) -> str:
        '''Text contained in this cell.'''
        return '\n'.join([block.text for block in self.blocks]) if bool(self) else None

    
    def compare(self, cell, threshold:float=0.9):
        '''whether has same structure with given Cell.
            ---
            Args:
              - cell: Cell instance to compare
              - threshold: two bboxes are considered same if the overlap area exceeds threshold.
        '''
        res, msg = super().compare(cell, threshold)
        if not res:
            return res, msg
        
        if self.bg_color != cell.bg_color:
            return False, f'Inconsistent background color @ Cell {self.bbox_raw}:\n{self.bg_color} v.s. {cell.bg_color}'

        if tuple(self.border_color) != tuple(cell.border_color):
            return False, f'Inconsistent border color @ Cell {self.bbox_raw}:\n{self.border_color} v.s. {cell.border_color}'

        if tuple(self.border_width) != tuple(cell.border_width):
            return False, f'Inconsistent border width @ Cell {self.bbox_raw}:\n{self.border_width} v.s. {cell.border_width}'

        if tuple(self.merged_cells) != tuple(cell.merged_cells):
            return False, f'Inconsistent count of merged cells @ Cell {self.bbox_raw}:\n{self.merged_cells} v.s. {cell.merged_cells}'

        return True, ''


    def store(self):
        if bool(self):
            res = super().store()
            res.update({
                'bg_color': self.bg_color,
                'border_color': self.border_color,
                'border_width': self.border_width,
                'merged_cells': self.merged_cells,
                'blocks': self.blocks.store()
            })
            return res
        else:
            return None


    def plot(self, page, content:bool=True, style:bool=True, color:tuple=None):
        '''Plot cell.
            ---
            Args:
              - page: fitz.Page object
              - content: plot text blocks if True
              - style: plot cell style if True, e.g. border width, shading; otherwise draw table border only
              - color: table border color when style=False              
        '''        
        # plot cell style
        if style:
            # border color and width
            bc = [x/255.0 for x in RGB_component(self.border_color[0])]
            w = self.border_width[0]

            # shading color
            if self.bg_color != None:
                sc = [x/255.0 for x in RGB_component(self.bg_color)] 
            else:
                sc = None
            page.drawRect(self.bbox, color=bc, fill=sc, width=w, overlay=False)
        
        # or just cell borders for illustration
        else:
            page.drawRect(self.bbox, color=color, fill=None, width=1, overlay=False)

        # plot blocks contained in cell
        if content:
            for block in self.blocks:
                block.plot(page)


    def add(self, block):
        ''' Add block to this cell. 
            ---
            Arg:
              - block: Block type

            Note: If the block is partly contained in a cell, it must deep into line -> span -> char.
        '''
        if not block.is_text_block():
            return

        # add block directly if fully contained in cell
        if self.bbox.contains(block.bbox):
            self.blocks.append(block)
            return
        
        # add nothing if no intersection
        if not self.bbox.intersects(block.bbox):
            return

        # otherwise, further check lines in block
        split_block = TextBlock()
        for line in block.lines:
            L = line.intersect(self.bbox)
            split_block.add(L)

        self.blocks.append(split_block)


    def set_style(self, table, indexes, border_style=True):
        ''' Set python-docx cell style, e.g. border, shading, width, row height, 
            based on cell block parsed from PDF.
            ---
            Args:
              - table: python-docx table object
              - indexes: (i, j) index of current cell in table
              - border_style: set border style or not
        '''
        i, j = indexes
        cell = table.cell(i, j)
        n_row, n_col = self.merged_cells

        # ---------------------
        # border style
        # ---------------------
        # NOTE: border width is specified in eighths of a point, with a minimum value of 
        # two (1/4 of a point) and a maximum value of 96 (twelve points)
        if border_style:
            keys = ('top', 'end', 'bottom', 'start')
            kwargs = {}
            for k, w, c in zip(keys, self.border_width, self.border_color):
                hex_c = f'#{hex(c)[2:].zfill(6)}'
                kwargs[k] = {
                    'sz': 8*w, 'val': 'single', 'color': hex_c.upper()
                }
            # merged cells are assumed to have same borders with the main cell        
            for m in range(i, i+n_row):
                for n in range(j, j+n_col):
                    set_cell_border(table.cell(m, n), **kwargs)

        # ---------------------
        # merge cells
        # ---------------------        
        if n_row*n_col!=1:
            _cell = table.cell(i+n_row-1, j+n_col-1)
            cell.merge(_cell)

        # ---------------------
        # cell width/height
        # ---------------------
        x0, y0, x1, y1 = self.bbox_raw
        
        # set cell height by setting row height
        # NOTE: consider separate rows (without cell merging) only since merged rows are determined accordingly.
        if n_row==1:
            row = table.rows[i]
            # to control the layout precisely, set `exact` value, rather than `at least` value
            # the associated steps in MS word: Table Properties -> Row -> Row height -> exactly
            row.height_rule = WD_ROW_HEIGHT.EXACTLY
            # NOTE: cell height is counted from center-line of top border to center line of bottom border,
            # i.e. the height of cell bbox
            row.height = Pt(y1-y0) # Note cell does not have height property.    
        
        # set cell width
        # experience: width of merged cells may change if not setting width for merged cells
        cell.width = Pt(x1-x0)

        # ---------------------
        # cell bg-color
        # ---------------------
        if self.bg_color!=None:
            set_cell_shading(cell, self.bg_color)