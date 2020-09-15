# -*- coding: utf-8 -*-

'''
Objects representing PDF path (both stroke and filling) parsed from both pdf raw streams and annotations.

@created: 2020-09-15
@author: train8808@gmail.com
---

The context meaning of shape instance may be:
    - strike through line of text
    - under line of text
    - highlight area of text
    - table border
    - cell shading

Data structure:
    {
        'type': int,
        'bbox': (x0, y0, x1, y1),
        'color': sRGB_value
    }
'''

from ..common.BBox import BBox
from ..common.base import RectType
from ..common.utils import RGB_component
from ..common.base import RectType



class Shape(BBox):
    ''' Shape object.'''
    def __init__(self, raw:dict={}):
        super(Shape, self).__init__(raw)
        self._type = RectType.UNDEFINED # no type by default
        self.color = raw.get('color', 0)

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, rect_type: RectType):
        self._type = rect_type

    def store(self):
        res = super().store()
        res.update({
            'type': self._type.value,
            'color': self.color
        })
        return res

    def plot(self, page):
        '''Plot rectangle shapes with PyMuPDF.
            ---
            Args:
              - page: fitz.Page object
        '''
        color = [c/255.0 for c in RGB_component(self.color)]
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=False)


class Stroke(Shape):
    '''Liear stroke of a path.'''
    def __init__(self, raw:dict={}):
        # stroke style
        self.start = raw.get('start', (0.0, 0.0))
        self.end = raw.get('end', (0.0, 0.0))
        self.width = raw.get('width', 0.5)

        # calculate bbox
        raw['bbox'] = self.to_rect()
        super(Stroke, self).__init__(raw)


    def to_rect(self):
        ''' convert centerline to rectangle shape.
            centerline is represented with start/end points: (x0, y0), (x1, y1).
        '''
        h = self.width / 2.0
        x0, y0 = self.start
        x1, y1 = self.end

        # horizontal line
        if y0==y1:
            res = (x0, y0-h, x1, y1+h)
        # vertical line
        elif x0==x1:
            res = (x0-h, y0, x1+h, y1)
        else:
            res = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

        return res

    def plot(self, page):
        '''Plot rectangle shapes with PyMuPDF.
            ---
            Args:
              - page: fitz.Page object
        '''
        color = [c/255.0 for c in RGB_component(self.color)]
        page.drawLine(self.start, self.end, color=None, width=self.width, overlay=False)


class Fill(Shape):
    '''Rectanglular (bbox) filling area of a closed path.'''

    ...