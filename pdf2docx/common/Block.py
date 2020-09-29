# -*- coding: utf-8 -*-

'''
Base class for text/image/table blocks.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from .base import BlockType, TextAlignment
from .BBox import BBox
from .constants import DM


class Block(BBox):
    '''Text block.'''
    def __init__(self, raw:dict={}):
        super().__init__(raw)
        self._type = BlockType.UNDEFINED

        # horizontal spacing
        self.alignment = self.get_alignment(raw.get('alignment', 0))
        self.left_space = raw.get('left_space', 0.0)
        self.right_space = raw.get('right_space', 0.0)

        # RELATIVE position of tab stops
        self.tab_stops = raw.get('tab_stops', []) 

        # vertical spacing
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

    def get_alignment(self, mode:int):
        for t in TextAlignment:
            if t.value==mode:
                return t
        return TextAlignment.LEFT

    def parse_horizontal_spacing(self, bbox):
        '''set left alignment by default.'''
        # NOTE: in PyMuPDF CS, horizontal text direction is same with positive x-axis,
        # while vertical text is on the contrarory, so use f = -1 here
        idx, f = (0, 1.0) if self.is_horizontal_text else (3, -1.0)
        self.alignment = TextAlignment.LEFT
        self.left_space = (self.bbox[idx] - bbox[idx]) * f


    def compare(self, block, threshold:float=0.9):
        '''whether has same bbox and vertical spacing with given block.
            ---
            Args:
              - block: instance to compare
              - threshold: two bboxes are considered same if the overlap area exceeds threshold.

            NOTE: the vertical spacing has most important impacts on the layout of converted docx.
        '''
        # bbox
        res, msg = super().compare(block, threshold)
        if not res: return res, msg

        # check spacing
        for key, value in self.__dict__.items():
            if not 'space' in key: continue
            target_value = getattr(block, key)
            if abs(value-target_value)>DM/4.0:
                return False, f'Inconsistent {" ".join(key.split("_"))} @ {self.bbox}:\n{value} v.s. {target_value} (expected)'

        return True, ''
        

    def store(self):
        '''Store attributes in json format.'''
        res = super().store()
        res.update({
            'type'        : self._type.value,
            'alignment'   : self.alignment.value,
            'left_space'  : self.left_space,
            'right_space' : self.right_space,
            'before_space': self.before_space,
            'after_space' : self.after_space,
            'line_space'  : self.line_space,
            'tab_stops'   : self.tab_stops
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