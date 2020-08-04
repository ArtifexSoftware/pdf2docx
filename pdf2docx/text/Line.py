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

from ..common.BBox import BBox
from ..common.base import TextDirection
from .Spans import Spans
from .ImageSpan import ImageSpan


class Line(BBox):
    '''Object representing a line in text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(Line, self).__init__(raw)
        self.wmode = raw.get('wmode', 0) # writing mode
        self.dir = raw.get('dir', [1, 0]) # writing direction

        # collect spans
        self.spans = Spans(None, self).from_dicts(raw.get('spans', []))

    @property
    def image_spans(self):
        '''Get image spans in this Line.'''
        return list(filter(
            lambda span: isinstance(span, ImageSpan), self.spans
        ))

    @property
    def text_direction(self):
        if self.dir[0] == 1.0:
            return TextDirection.LEFT_RIGHT
        elif self.dir[1] == -1.0:
            return TextDirection.BOTTOM_TOP
        else:
            return TextDirection.IGNORE

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


    def plot(self, page, color:int):
        '''Plot line border in red.
           ---
            Args: 
              - page: fitz.Page object
        '''
        page.drawRect(self.bbox, color=color, fill=None, overlay=False)


    def add(self, span_or_list):
        '''Add span list to current Line.
            ---
            Args:
              - span_or_list: a TextSpan or TextSpan list
        '''
        if isinstance(span_or_list, (list, tuple)):
            for span in span_or_list:
                self.add_span(span)
        else:
            self.add_span(span_or_list)


    def add_span(self, span:BBox):
        '''Add span to current Line.'''
        if isinstance(span, BBox):
            self.spans.append(span)


    def intersect(self, rect):
        '''Create new Line object with spans contained in given bbox.
            ---
            Args:
              - rect: fitz.Rect, target bbox
        '''
        # add line directly if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()

        # further check spans in line
        # new line with same text attributes
        line = Line({
            'wmode': self.wmode,
            'dir': self.dir
        })
        for span in self.spans:
            contained_span = span.intersect(rect)
            line.add(contained_span)

        return line

    def in_same_row(self, line):
        ''' Check whether in same row/line with specified line. Note text direction.

            taking horizontal text as an example:
            - yes: the bottom edge of each box is lower than the centerline of the other one;
            - otherwise, not in same row.

            Note the difference with method `horizontally_align_with`. They may not in same line, though
            aligned horizontally.
        '''
        if not line or self.text_direction != line.text_direction:
            return False

        # normal reading direction by default
        idx = 1 if self.is_horizontal else 0

        c1 = (self.bbox_raw[idx] + self.bbox_raw[idx+2]) / 2.0
        c2 = (line.bbox_raw[idx] + line.bbox_raw[idx+2]) / 2.0

        # Note y direction under PyMuPDF context
        res = c1<=line.bbox_raw[idx+2] and c2<=self.bbox_raw[idx+2]
        return res
            