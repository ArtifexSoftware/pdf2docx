# -*- coding: utf-8 -*-

'''
Text block objects based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---
https://pymupdf.readthedocs.io/en/latest/textpage.html

    {
        'type': 1,
        'bbox': (x0,y0,x1,y1),
        'ext': 'png',
        'width': w,
        'height': h,
        'image': b'',
        'colorspace': n,
        'xref': xref, 'yref': yref, 'bpc': bpc
    }

Note: the raw image block will be merged into text block: Text > Line > Span.

'''


from .Line import Line
from .ImageSpan import ImageSpan
from .TextBlock import TextBlock
from ..common import utils
from ..common.base import Spacing
from ..common.Block import Block


class ImageBlock(Block, Spacing):
    '''Text block.'''
    def __init__(self, raw: dict) -> None:
        super(ImageBlock, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.image = raw.get('image', b'')

        # set type
        self.set_image_block()


    def store(self) -> dict:
        res = super().store()
        res.update({
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': '<image>' # drop real content to reduce size
        })
        return res


    def plot(self, page):
        '''Plot image bbox with diagonal lines.
            ---
            Args: 
              - page: fitz.Page object
        '''
        x0, y0, x1, y1 = self.bbox_raw
        color = utils.RGB_component_from_name('blue')

        page.drawLine((x0, y0), (x1, y1), color=color, width=1)
        page.drawLine((x0, y1), (x1, y0), color=color, width=1)
        page.drawRect(self.bbox, color=color, fill=None, overlay=False)


    def to_text_block(self) -> TextBlock:
        '''convert image block to text block: a span'''
        # image span
        span = ImageSpan()
        span.from_image_block(self)

        # add span to line
        image_line = Line()
        image_line.add(span)
        
        # insert line to block
        block = TextBlock()
        block.add(image_line)

        # set text block
        block.set_text_block()

        return block    