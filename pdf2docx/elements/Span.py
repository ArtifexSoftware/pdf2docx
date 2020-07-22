# -*- coding: utf-8 -*-

'''
Span and Char objects based on PDF raw dict extracted with PyMuPDF.
@created: 2020-07-22
@author: train8808@gmail.com
---

- raw dict for Char
    {
        'bbox'  : (x0, y0, x1, y1), 
        'c'     : str, 
        'origin': (x,y)
    }

- raw dict for Span
    {
        'bbox': (x0,y0,x1,y1),
        'color': sRGB
        'font': fontname,
        'size': fontzise,
        'flags': fontflags,
        'chars': [ chars ]
    }

https://pymupdf.readthedocs.io/en/latest/textpage.html
'''

from .base import BBox


class Char(BBox):
    '''Object representing a character.'''
    def __init__(self, raw: dict):
        super(Char, self).__init__(raw)
        self.c = raw.get('c', '')
        self.origin = raw.get('origin', None)

    def store(self) -> dict:
        res = super().store()
        res.update({
            'c': self.c,
            'origin': self.origin
        })

        return res



class TextSpan(BBox):
    '''Object representing text span.'''
    def __init__(self, raw: dict):
        super(TextSpan, self).__init__(raw)
        self.color = raw.get('color', 0)
        self.font = raw.get('font', None)
        self.size = raw.get('size', 12.0)
        self.flags = raw.get('flags', 0)
        self.chars = [ Char(c) for c in raw.get('chars', []) ]
    
    def store(self) -> dict:
        res = super().store()
        res.update({
            'color': self.color,
            'font': self.font,
            'size': self.size,
            'flags': self.flags,
            'chars': [
                char.store() for char in self.chars
            ]
        })
        return res


class ImageSpan(BBox):
    '''Text block.'''
    def __init__(self, raw: dict):
        super(ImageSpan, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.image = raw.get('image', b'')

    def store(self) -> dict:
        res = super().store()
        res.update({
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': '<image>' # drop real content to reduce size
        })
        return res
