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
        line = Line()
        for span in self.spans:
            contained_span = span.intersect(rect)
            line.add(contained_span)

        return line
        