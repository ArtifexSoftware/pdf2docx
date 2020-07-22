# -*- coding: utf-8 -*-

'''
Text Line objects based on PDF raw dict extracted with PyMuPDF.
@created: 2020-07-22
@author: train8808@gmail.com
---

Data structure of line in text block:
{
    'bbox': (x0,y0,x1,y1),
    'wmode': m,
    'dir': [x,y],
    'spans': [ spans ]
}

https://pymupdf.readthedocs.io/en/latest/textpage.html
'''

from .base import BBox
from .Span import TextSpan


class Line(BBox):
    '''Object representing a line in text block.'''
    def __init__(self, raw: dict):
        super(Line, self).__init__(raw)
        self.wmode = raw.get('wmode', 0) # writing mode
        self.dir = raw.get('dir', [1, 0]) # writing direction
        self.spans = [
            TextSpan(s) for s in raw.get('spans', []) # text span by default
        ]

    def store(self) -> dict:
        res = super().store()
        res.update({
            'wmode': self.wmode,
            'dir': self.dir,
            'spans': [
                span.store() for span in self.spans
            ]
        })

        return res
        