# -*- coding: utf-8 -*-

'''
Base class for text/image/table blocks.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from .base import BlockType
from .BBox import BBox


class Block(BBox):
    '''Text block.'''
    def __init__(self, raw: dict) -> None:
        super(Block, self).__init__(raw)
        self._type = BlockType.UNDEFINED

    def is_text_block(self):
        return self._type==BlockType.TEXT

    def is_image_block(self):
        return self._type==BlockType.IMAGE

    def is_explicit_table_block(self):
        return self._type==BlockType.EXPLICIT_TABLE

    def is_implicit_table_block(self):
        return self._type==BlockType.IMPLICIT_TABLE

    def is_table_block(self):
        return self.is_explicit_table_block() or self.is_implicit_table_block()

    def set_text_block(self):
        self._type = BlockType.TEXT

    def set_image_block(self):
        self._type = BlockType.IMAGE

    def set_explicit_table_block(self):
        self._type = BlockType.EXPLICIT_TABLE

    def set_implicit_table_block(self):
        self._type = BlockType.IMPLICIT_TABLE

    def store(self) -> dict:
        res = super().store()
        res.update({
            'type': self._type.value
        })
        return res

    def contains_discrete_lines(self, distance:float=25, threshold:int=3):
        ''' Check whether lines in block are discrete, False by default. 
            Rewrite it if necessary, e.g. in TextBlock'''
        return False

    def plot(self, page):
        '''Plot block bbox in PDF page.
           ---
            Args: 
              - page: fitz.Page object
        '''
        raise NotImplementedError