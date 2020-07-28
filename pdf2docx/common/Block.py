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
    def __init__(self, raw:dict={}):
        super(Block, self).__init__(raw)
        self._type = BlockType.UNDEFINED

        # spacing attributes
        self.before_space = 0.0
        self.after_space = 0.0
        self.line_space = 0.0


    @property
    def sub_bboxes(self):
        '''sub-region bbox of this block, e.g. Lines in TextBlock. Return self.bbox by default.'''
        return [self.bbox]

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

    def is_horizontal_block(self):
        '''Whether horizontally oriented block. True by default.'''
        return True

    def store(self):
        '''Store attributes in json format.'''
        res = super().store()
        res.update({
            'type': self._type.value
        })
        # set spacing attributes for text and image block
        if not self.is_table_block():
            res.update({
                'before_space': self.before_space,
                'after_space': self.after_space,
                'line_space': self.line_space
            })
        return res

    def contains_discrete_lines(self, distance:float=25, threshold:int=3):
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