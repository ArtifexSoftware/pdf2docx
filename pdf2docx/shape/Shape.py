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
from ..common.constants import DM



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
        self._start = raw.get('start', None)
        self._end = raw.get('end', None)
        width = raw.get('width', 0.0)
        raw['bbox'] = self._to_rect(width)
        super(Stroke, self).__init__(raw)

    @property
    def is_horizontal(self):
        '''override IText method.'''
        return self._start[1] == self._end[1]

    @property
    def is_vertical(self):
        '''override IText method.'''
        return self._start[0] == self._end[0]

    @property
    def width(self):
        return min(self.bbox.width, self.bbox.height)

    @property
    def x0(self):
        return self._x0
    


    def update(self, rect):
        '''Update current bbox to specified `rect`.
            ---
            Args:
              - rect: fitz.rect or raw bbox like (x0, y0, x1, y1)
        '''
        super(Stroke, self).update(rect)

        # suppose horizontal or vertical stroke
        bbox = self.bbox
        if bbox.width >= bbox.height: # horizontal
            y = (bbox.y0+bbox.y1)/2.0
            self._start = (bbox.x0, y)
            self._end   = (bbox.x1, y)
        else: #vertical
            x = (bbox.x0+bbox.x1)/2.0
            self._start = (x, bbox.y0)
            self._end   = (x, bbox.y1)

        return self    


    def _to_rect(self, width):
        ''' convert centerline to rectangle shape.
            centerline is represented with start/end points: (x0, y0), (x1, y1).
        '''
        if not self._start or not self._end:
            return None

        h = width / 2.0
        x0, y0 = self._start
        x1, y1 = self._end

        # horizontal line
        if abs(y0-y1)<=DM:
            res = (x0, y0-h, x1, y1+h)
        # vertical line
        elif abs(x0-x1)<=DM:
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
        page.drawLine(self._start, self._end, color=None, width=self.width, overlay=False)


class Fill(Shape):
    '''Rectanglular (bbox) filling area of a closed path.'''

    ...