# -*- coding: utf-8 -*-

'''
Table Cell object.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from docx.shared import Pt
from ..text.TextBlock import TextBlock
from ..common.BBox import BBox
from ..common.utils import RGB_component
from ..common import docx
from ..layout import Blocks # avoid import conflict


class Cell(BBox):
    ''' Cell object.'''
    def __init__(self, raw:dict={}):
        if raw is None: raw = {}
        super().__init__(raw)
        self.bg_color     = raw.get('bg_color', None) # type: int
        self.border_color = raw.get('border_color', (0,0,0,0)) # type: tuple [int]
        self.border_width = raw.get('border_width', (0,0,0,0)) # type: tuple [float]
        self.merged_cells = raw.get('merged_cells', (1,1)) # type: tuple [int]

        # collect blocks
        self.blocks = Blocks.Blocks(parent=self).from_dicts(raw.get('blocks', []))


    @property
    def text(self):
        '''Text contained in this cell.'''
        return '\n'.join([block.text for block in self.blocks]) if bool(self) else None

    
    def compare(self, cell, threshold:float=0.9):
        '''whether has same structure with given Cell.
            ---
            Args:
              - cell: Cell instance to compare
              - threshold: two bboxes are considered same if the overlap area exceeds threshold.
        '''
        # bbox
        res, msg = super().compare(cell, threshold)
        if not res: return res, msg

        # cell style        
        if self.bg_color != cell.bg_color:
            return False, f'Inconsistent background color @ Cell {self.bbox}:\n{self.bg_color} v.s. {cell.bg_color} (expected)'

        if tuple(self.border_color) != tuple(cell.border_color):
            return False, f'Inconsistent border color @ Cell {self.bbox}:\n{self.border_color} v.s. {cell.border_color} (expected)'

        if tuple(self.border_width) != tuple(cell.border_width):
            return False, f'Inconsistent border width @ Cell {self.bbox}:\n{self.border_width} v.s. {cell.border_width} (expected)'

        if tuple(self.merged_cells) != tuple(cell.merged_cells):
            return False, f'Inconsistent count of merged cells @ Cell {self.bbox}:\n{self.merged_cells} v.s. {cell.merged_cells} (expected)'

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
            - block: text block or table block

            Note: If it's a text block and partly contained in a cell, it must deep into line -> span -> char.
        '''
        # add block directly if fully contained in cell
        if self.bbox.contains(block.bbox):
            self.blocks.append(block)
            return
        
        # add nothing if no intersection
        if not self.bbox & block.bbox: return

        # otherwise, further check lines in text block
        if not block.is_text_block():  return
        
        # NOTE: add each line as a single text block to avoid overlap between table block and combined lines
        split_block = TextBlock()
        for line in block.lines:
            L = line.intersects(self.bbox)
            split_block.add(L)
        self.blocks.append(split_block)


    def make_docx(self, table, indexes):
        '''Set cell style and assign contents.
            ---
            Args:
              - table: docx table instance
              - indexes: (i, j), row and column indexes
        '''        
        # set cell style, e.g. border, shading, cell width
        self._set_style(table, indexes)
        
        # ignore merged cells
        if not bool(self):  return

        # merge cells
        n_row, n_col = self.merged_cells
        i, j = indexes
        docx_cell = table.cell(i, j)
        if n_row*n_col!=1:
            _cell = table.cell(i+n_row-1, j+n_col-1)
            docx_cell.merge(_cell)
        
        # ---------------------
        # cell width (cell height is set by row height)
        # ---------------------
        # experience: width of merged cells may change if not setting width for merged cells
        x0, y0, x1, y1 = self.bbox
        docx_cell.width = Pt(x1-x0)

        # insert contents
        # NOTE: there exists an empty paragraph already in each cell, which should be deleted first to
        # avoid unexpected layout. `docx_cell._element.clear_content()` works here.
        # But, docx requires at least one paragraph in each cell, otherwise resulting in a repair error. 
        if self.blocks:
            docx_cell._element.clear_content()
            self.blocks.make_page(docx_cell)


    def _set_style(self, table, indexes):
        ''' Set python-docx cell style, e.g. border, shading, width, row height, 
            based on cell block parsed from PDF.
            ---
            Args:
              - table: python-docx table object
              - indexes: (i, j) index of current cell in table
        '''
        i, j = indexes
        docx_cell = table.cell(i, j)
        n_row, n_col = self.merged_cells

        # ---------------------
        # border style
        # ---------------------
        # NOTE: border width is specified in eighths of a point, with a minimum value of 
        # two (1/4 of a point) and a maximum value of 96 (twelve points)
        if self.border_width and sum(self.border_width)>0.0:
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
                    docx.set_cell_border(table.cell(m, n), **kwargs)
        

        # ---------------------
        # cell bg-color
        # ---------------------
        if self.bg_color!=None:
            docx.set_cell_shading(docx_cell, self.bg_color)
        
        # ---------------------
        # clear cell margin
        # ---------------------
        # NOTE: the start position of a table is based on text in cell, rather than left border of table. 
        # They're almost aligned if left-margin of cell is zero.
        docx.set_cell_margins(docx_cell, start=0, end=0)

        # set vertical direction if contained text blocks are in vertical direction
        if self.blocks.is_vertical_text:
            docx.set_vertical_cell_direction(docx_cell)