# -*- coding: utf-8 -*-

'''Row in a table.
'''

from docx.enum.table import WD_ROW_HEIGHT
from docx.shared import Pt
from .Cells import Cells
from ..common.Element import Element


class Row(Element):
    '''Row in a table.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}
        super().__init__(raw)

        # logical row height
        self.height = raw.get('height', 0.0)

        # cells in row
        self._cells = Cells(parent=self).restore(raw.get('cells', []))


    def __getitem__(self, idx):
        try:
            cell = self._cells[idx]
        except IndexError:
            msg = f'Cell index {idx} out of range'
            raise IndexError(msg)
        else:
            return cell

    def __iter__(self):
        return (cell for cell in self._cells)

    def __len__(self):
        return len(self._cells)


    def append(self, cell):
        '''Append cell to row and update bbox accordingly.'''
        self._cells.append(cell)


    def store(self):
        res = super().store()
        res.update({
            'height': self.height,
            'cells': self._cells.store()
        })

        return res


    def make_docx(self, table, idx_row:int):
        '''Create row of docx table.
        
        Args:
            table (Table): ``python-docx`` table instance.
            idx_row (int): Current row index.
        '''  
        # set row height
        docx_row = table.rows[idx_row]

        # to control the layout precisely, set `exact` value, rather than `at least` value
        # the associated steps in MS word: Table Properties -> Row -> Row height -> exactly
        docx_row.height_rule = WD_ROW_HEIGHT.EXACTLY
        
        # NOTE: row height is counted from center-line of top border to center line of bottom border
        docx_row.height = Pt(self.height)

        # set cell style and contents
        for idx_col in range(len(table.columns)):
            self._cells[idx_col].make_docx(table, (idx_row, idx_col))