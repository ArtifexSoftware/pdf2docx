# -*- coding: utf-8 -*-

'''
A group of Text, Image or Table block.
@created: 2020-07-22
@author: train8808@gmail.com
'''

from .base import BBox, BlockType
from .TextBlock import ImageBlock, TextBlock

class Blocks:
    '''Text block.'''
    def __init__(self, raws: list):
        ''' Construct Text blocks (image blocks included) from a list of raw block dict.'''
        self._blocks = []

        for raw in raws:
            block = None
            # image block
            block_type = raw.get('type', -1)
            if block_type==BlockType.IMAGE:
                block = ImageBlock(raw)
            # text block
            elif block_type == BlockType.TEXT:
                block = TextBlock(raw)
            
            # add to list
            if block: self._blocks.append(block)

    def __getitem__(self, idx):
        try:
            blocks = self._blocks[idx]
        except IndexError:
            msg = f'Block index {idx} out of range'
            raise IndexError(msg)
        else:
            return blocks

    def __iter__(self):
        return (block for block in self._blocks)

    def __len__(self):
        return len(self._blocks)