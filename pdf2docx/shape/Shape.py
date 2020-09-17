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

import fitz
from ..common.BBox import BBox
from ..common.base import RectType
from ..common.utils import RGB_component
from ..common.constants import DM
from ..common.constants import MAX_W_BORDER


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
        '''Plot rectangle shapes with PyMuPDF.'''
        color = [c/255.0 for c in RGB_component(self.color)]
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=False)


class Stroke(Shape):
    '''Linear stroke of a path.'''
    def __init__(self, raw:dict={}):
        # convert start/end point to real page CS
        self._start = fitz.Point(raw.get('start', (0.0, 0.0))) * Stroke.ROTATION_MATRIX
        self._end = fitz.Point(raw.get('end', (0.0, 0.0))) * Stroke.ROTATION_MATRIX

        # width, color
        self.width = raw.get('width', 0.0)
        self.color = raw.get('color', 0)
        self._type = RectType.UNDEFINED # no type by default

        # update bbox
        self.update(self._to_rect())
        

    @property
    def horizontal(self): return self._start[1] == self._end[1]

    @property
    def vertical(self): return self._start[0] == self._end[0]

    @property
    def x0(self):
        if self.horizontal: return self.bbox.x0
        if self.vertical: return (self.bbox.x0+self.bbox.x1)/2.0
        raise Exception('Supports horizontal or vertical Strokes only.')

    @property
    def x1(self):
        if self.horizontal: return self.bbox.x1
        if self.vertical: return (self.bbox.x0+self.bbox.x1)/2.0
        raise Exception('Supports horizontal or vertical Strokes only.')

    @property
    def y0(self):
        if self.horizontal: return (self.bbox.y0+self.bbox.y1)/2.0
        if self.vertical: return self.bbox.y0
        raise Exception('Supports horizontal or vertical Strokes only.')

    @property
    def y1(self):
        if self.horizontal: return (self.bbox.y0+self.bbox.y1)/2.0
        if self.vertical: return self.bbox.y1
        raise Exception('Supports horizontal or vertical Strokes only.')


    def update(self, rect):
        '''Update stroke bbox (related to real page CS):
            - rect.area==0: start/end points
            - rect.area!=0: update bbox directly
        '''
        rect = fitz.Rect(rect)

        # an empty area line
        if rect.getArea()==0.0:
            self._start = fitz.Point(rect[0:2])
            self._end = fitz.Point(rect[2:])
            super(Stroke, self).update(self._to_rect())

        # a rect 
        else:
            super(Stroke, self).update(rect)

            # suppose horizontal or vertical stroke
            if rect.width >= rect.height: # horizontal
                y = (rect.y0+rect.y1)/2.0
                self._start = fitz.Point(rect.x0, y)
                self._end   = fitz.Point(rect.x1, y)
            else: #vertical
                x = (rect.x0+rect.x1)/2.0
                self._start = fitz.Point(x, rect.y0)
                self._end   = fitz.Point(x, rect.y1)

        return self    


    def _to_rect(self):
        ''' convert centerline to rectangle shape.'''
        h = self.width / 2.0
        x0, y0 = self._start
        x1, y1 = self._end

        if x0>x1: x0, x1 = x1, x0
        if y0>y1: y0, y1 = y1, y0

        # horizontal/vertical line
        if abs(y0-y1)<=DM or abs(x0-x1)<=DM:
            res = (x0-h, y0-h, x1+h, y1+h)
        else:
            res = (x0, y0, x1, y1)

        return res


    def plot(self, page):
        '''Plot rectangle shapes with PyMuPDF.'''
        color = [c/255.0 for c in RGB_component(self.color)]
        page.drawLine(self._start, self._end, color=color, width=self.width, overlay=False)


class Fill(Shape):
    '''Rectangular (bbox) filling area of a closed path.'''

    def to_stroke(self):
        '''Convert to Stroke instance based on width criterion.

            NOTE: a Fill from shape point of view may be a Stroke from content point of view.
            The criterion here is whether the width is smaller than `MAX_W_BORDER` defined in constants.
        '''
        w = min(self.bbox.width, self.bbox.height)

        # not a stroke if exceed max border width
        if w > MAX_W_BORDER:
            return None
        else:
            return Stroke({'width': w, 'color': self.color}).update(self.bbox)