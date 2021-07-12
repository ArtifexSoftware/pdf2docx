# -*- coding: utf-8 -*-

'''Definition of Image block objects. 

**The raw image block will be merged into TextBlock > Line > Span.**
'''

from io import BytesIO
from ..text.Line import Line
from ..text.TextBlock import TextBlock
from .Image import Image
from .ImageSpan import ImageSpan
from ..common.Block import Block
from ..common.docx import add_float_image


class ImageBlock(Image, Block):
    '''Image block.'''
    def __init__(self, raw:dict=None):
        super().__init__(raw)

        # inline image type by default
        self.set_inline_image_block()


    def to_text_block(self):
        """Convert image block to a span under text block.

        Returns:
            TextBlock: New TextBlock instance containing this image.
        """
        # image span
        span = ImageSpan().from_image(self)

        # add span to line
        image_line = Line()
        image_line.add(span)
        
        # insert line to block
        block = TextBlock()        
        block.add(image_line)

        # NOTE: it's an image block even though in TextBlock type
        block.set_inline_image_block() 

        return block
 

    def store(self):
        '''Store ImageBlock instance in raw dict.'''
        res = Block.store(self)
        res.update(
            Image.store(self)
        )
        return res

    
    def plot(self, page):
        '''Plot image bbox with diagonal lines (for debug purpose).
        
        Args: 
            page (fitz.Page): pdf page to plot.
        '''
        super().plot(page, color=(1,0,0))


    def make_docx(self, p):
        '''Create floating image behind text. 
        
        Args:
            p (Paragraph): ``python-docx`` paragraph instance.
        
        .. note::
            Inline image is created within TextBlock.
        '''
        if self.is_float_image_block:
            x0, y0, x1, y1 = self.bbox
            add_float_image(p, BytesIO(self.image), width=x1-x0, pos_x=x0, pos_y=y0)
        else:
            super().make_docx(p)
        return p