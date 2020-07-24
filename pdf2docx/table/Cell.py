# -*- coding: utf-8 -*-

'''
Table Cell object.

@created: 2020-07-23
@author: train8808@gmail.com
'''


from pdf2docx.pdf2docx.text.TextBlock import TextBlock
from ..common.BBox import BBox
from ..common.base import RectType
from ..common.Block import Block
from ..common import utils
from ..layout.Blocks import Blocks

class Cell(BBox):
    ''' Cell object.'''
    def __init__(self, raw:dict={}) -> None:
        super(Cell, self).__init__(raw)
        self.bg_color = raw.get('bg_color', None) # type: int
        self.border_color = raw.get('border_color', None) # type: tuple [int]
        self.border_width = raw.get('border_width', None) # type: tuple [float]
        self.merged_cells = raw.get('merged_cells', (1,1)) # type: tuple [int]
        self.blocks = Blocks(raw.get('blocks', []))


    def store(self) -> dict:
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


    def plot(self, page, style:bool=True, content:bool=True):
        '''Plot cell.
            ---
            Args:
              - page: fitz.Page object
              - style: plot cell style if True, e.g. border width, shading
              - content: plot text blocks if True
        '''        
        # plot cell style
        if style:
            # border color and width
            bc = [x/255.0 for x in utils.RGB_component(self.border_color[0])]
            w = self.border_width[0]

            # shading color
            if self.bg_color != None:
                sc = [x/255.0 for x in utils.RGB_component(self.bg_color)] 
            else:
                sc = None
            page.drawRect(self.bbox, color=bc, fill=sc, width=w, overlay=False)
        
        # or just cell borders for illustration
        else:
            bc = (1,0,0)
            page.drawRect(self.bbox, color=bc, fill=None, width=1, overlay=False)

        # plot blocks contained in cell
        if content:
            for block in self.blocks:
                block.plot(page)


    def add(self, block:Block):
        ''' Add block to this cell. 
            ---
            Note: If the block is partly contained in a cell, it must deep into line -> span -> char.
        '''
        if not block.is_text_block():
            return

        # add block directly if fully contained in cell
        if self.bbox.contains(block.bbox):
            self.blocks.append(block)
        
        # add nothing if no intersection
        if not self.bbox.intersects(block.bbox):
            return

        # otherwise, further check lines in block
        split_block = TextBlock()
        for line in block.lines:
            L = line.intersect(self.bbox)
            split_block.add(L)

        self.blocks.append(split_block)