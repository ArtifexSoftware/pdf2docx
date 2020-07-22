# -*- coding: utf-8 -*-

'''
Object representing rectangles and lines, which is parsed from both raw streams and annotations of pdf.

@created: 2020-07-22
@author: train8808@gmail.com
---

The context meaning of rectangle shape may be:
    - strike through line of text
    - under line of text
    - highlight area of text
    - table border
    - cell shading

Rectangle data structure:
    {
        'type': int,
        'bbox': (x0, y0, x1, y1),
        'color': sRGB_value
    }
'''


from .base import BBox, RectType


class Rectangle(BBox):
    ''' Rectangle or line shapes parsed from pdf.'''
    def __init__(self, raw: dict):
        super(Rectangle, self).__init__(raw)
        self._type = RectType.UNDEFINED # no type by default
        self.color = raw.get('color', 0)

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, rect_type: RectType):
        self._type = rect_type

    def store(self) -> dict:
        res = super().store()
        res.update({
            'type': self._type.value,
            'color': self.color
        })

        return res