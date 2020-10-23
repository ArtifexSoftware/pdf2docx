# -*- coding: utf-8 -*-

'''
Definition of Image block objects. 

Note the raw image block will be merged into text block: Text > Line > Span.

@created: 2020-07-22
@author: train8808@gmail.com
'''

from io import BytesIO
from ..text.Line import Line
from ..text.TextBlock import TextBlock
from .Image import Image
from .ImageSpan import ImageSpan
from ..common.Block import Block
from ..common.docx import add_float_image

class ImageBlock(Image, Block): # to get Image.plot() in first priority
    '''Image block.'''
    def __init__(self, raw:dict=None):
        super().__init__(raw)

        # set type
        self.set_inline_image_block()


    def to_text_block(self):
        '''convert image block to text block: a span'''
        # image span
        span = ImageSpan().from_image(self)

        # add span to line
        image_line = Line()
        image_line.add(span)
        
        # insert line to block
        block = TextBlock()
        block.add(image_line)

        # set text block
        block.set_text_block()

        return block


    def store(self):
        res = super().store()
        res.update(
            super().store_image()
        )
        return res


class FloatImageBlock(Image, Block): # to get Image.plot() in first priority
    '''Floating Image block.'''
    def __init__(self, raw:dict=None):
        super().__init__(raw)

        # set type
        self.set_float_image_block()
    

    def store(self):
        res = super().store()
        res.update(
            super().store_image()
        )
        return res

    
    def plot(self, page):
        '''Plot image bbox with diagonal lines.
            ---
            Args: 
            - page: fitz.Page object
        '''
        super().plot(page, color=(1,0,0))


    def make_docx(self, p):
        ''' Create floating image behind text.
            ---
            Args:
              - p: docx paragraph instance
        '''
        x0, y0, x1, y1 = self.bbox
        add_float_image(p, BytesIO(self.image), width=x1-x0, pos_x=x0, pos_y=y0)
        return p