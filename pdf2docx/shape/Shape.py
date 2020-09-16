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
        self._start = raw.get('start', None)
        self._end = raw.get('end', None)

        # Note: rotation matrix is applied to Stroke.bbox by initializing BBox,
        # while self._start and self._end are still in original PyMuPDF CS. This affects the debug plot.
        width = raw.get('width', 0.0)
        bbox = self._to_rect(width)
        if bbox: raw['bbox'] = bbox
        super(Stroke, self).__init__(raw)

    @property
    def horizontal(self):
        '''override IText method.'''
        return self._start[1] == self._end[1]

    @property
    def vertical(self):
        '''override IText method.'''
        return self._start[0] == self._end[0]

    @property
    def width(self):
        return min(self.bbox.width, self.bbox.height)

    # Note: Get the coordinates from rotated bbox, rather than self._start and self._end
    @property
    def x0(self):
        if self.horizontal: return self.bbox.x0
        if self.vertical: return (self.bbox.x0+self.bbox.x1)/2.0
        raise Exception('Not supported for horizontal or vertical Strokes.')

    @property
    def x1(self):
        if self.horizontal: return self.bbox.x1
        if self.vertical: return (self.bbox.x0+self.bbox.x1)/2.0
        raise Exception('Not supported for horizontal or vertical Strokes.')

    @property
    def y0(self):
        if self.horizontal: return (self.bbox.y0+self.bbox.y1)/2.0
        if self.vertical: return self.bbox.y0
        raise Exception('Not supported for horizontal or vertical Strokes.')

    @property
    def y1(self):
        if self.horizontal: return (self.bbox.y0+self.bbox.y1)/2.0
        if self.vertical: return self.bbox.y1
        raise Exception('Not supported for horizontal or vertical Strokes.')

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

        # horizontal/vertical line
        if abs(y0-y1)<=DM or abs(x0-x1)<=DM:
            res = (x0-h, y0-h, x1+h, y1+h)
        else:
            res = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

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