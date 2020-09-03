# -*- coding: utf-8 -*-

'''
Base class for text/image/table blocks.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from .base import BlockType
from .BBox import BBox
from .constants import DM


class Block(BBox):
    '''Text block.'''
    def __init__(self, raw:dict={}):
        super(Block, self).__init__(raw)
        self._type = BlockType.UNDEFINED

        # spacing attributes
        self.before_space = raw.get('before_space', 0.0)
        self.after_space = raw.get('after_space', 0.0)
        self.line_space = raw.get('line_space', 0.0)


    def is_text_block(self):
        return self._type==BlockType.TEXT

    def is_image_block(self):
        return self._type==BlockType.IMAGE

    def is_lattice_table_block(self):
        return self._type==BlockType.LATTICE_TABLE

    def is_stream_table_block(self):
        return self._type==BlockType.STREAM_TABLE

    def is_table_block(self):
        return self.is_lattice_table_block() or self.is_stream_table_block()

    def set_text_block(self):
        self._type = BlockType.TEXT

    def set_image_block(self):
        self._type = BlockType.IMAGE

    def set_lattice_table_block(self):
        self._type = BlockType.LATTICE_TABLE

    def set_stream_table_block(self):
        self._type = BlockType.STREAM_TABLE

    def compare(self, block, threshold:float=0.9):
        '''whether has same bbox and vertical spacing with given block.
            ---
            Args:
              - block: instance to compare
              - threshold: two bboxes are considered same if the overlap area exceeds threshold.

            NOTE: the vertical spacing has most important impacts on the layout of converted docx.
        '''
        res, msg = super().compare(block, threshold)
        if not res:
            return res, msg
        
        if abs(self.before_space-block.before_space)>DM/4.0:
            return False, f'Inconsistent before space @ {self.bbox}:\n{self.before_space} v.s. {block.before_space}'

        if abs(self.after_space-block.after_space)>DM/4.0:
            return False, f'Inconsistent after space @ {self.bbox}:\n{self.after_space} v.s. {block.after_space}'

        if abs(self.line_space-block.line_space)>DM/4.0:
            return False, f'Inconsistent line space @ {self.bbox}:\n{self.line_space} v.s. {block.line_space}'

        return True, ''
        

    def store(self):
        '''Store attributes in json format.'''
        res = super().store()
        res.update({
            'type': self._type.value,
            'before_space': self.before_space,
            'after_space': self.after_space,
            'line_space': self.line_space
            })
        return res

    @staticmethod
    def contains_discrete_lines():
        ''' Check whether lines in block are discrete, False by default. 
            Rewrite it if necessary, e.g. in TextBlock.
        '''
        return False


    def plot(self, *args, **kwargs):
        '''Plot block bbox in PDF page.'''
        raise NotImplementedError


    def parse_text_format(self, *args, **kwargs):
        '''Parse text format.'''
        raise NotImplementedError


    def make_docx(self, *args, **kwargs):
        '''Create associated docx element, e.g. TextBlock/ImageBlock -> paragraph.'''
        raise NotImplementedError