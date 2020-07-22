# -*- coding: utf-8 -*-

'''
Text block objects based on PDF raw dict extracted with PyMuPDF.
@created: 2020-07-22
@author: train8808@gmail.com
---

- text block
    {
        'type': 0,
        'bbox': (x0,y0,x1,y1),
        'lines': [ lines ]
    }

- image block
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

Note: the raw image block is merged into text block: Text > Line > Span.


https://pymupdf.readthedocs.io/en/latest/textpage.html

'''

from .base import BBox, BlockType
from .Line import Line


class TextBlock(BBox):
    '''Text block.'''
    def __init__(self, raw: dict):
        super(TextBlock, self).__init__(raw)
        self.type = BlockType.TEXT
        self.lines = [ Line(line) for line in raw.get('lines', []) ]

    def store(self) -> dict:
        res = super().store()
        res.update({
            'type': self.type.value,
            'lines': [line.store() for line in self.lines]
        })
        return res


class ImageBlock(BBox):
    '''Text block.'''
    def __init__(self, raw: dict):
        super(ImageBlock, self).__init__(raw)
        self.type = BlockType.IMAGE
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.image = raw.get('image', b'')

    def store(self) -> dict:
        res = super().store()
        res.update({
            'type': self.type.value,
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': '<image>' # drop real content to reduce size
        })
        return res
