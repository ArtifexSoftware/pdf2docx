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


import fitz
from ..common.BBox import BBox
from .Spans import Spans
from .TextSpan import TextSpan


class Line(BBox):
    '''Object representing a line in text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(Line, self).__init__(raw)
        self.wmode = raw.get('wmode', 0) # writing mode
        self.dir = raw.get('dir', [1, 0]) # writing direction
        self.spans = Spans(raw.get('spans', []))

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
        '''Add spans to current Line and update the bbox accordingly.
            ---
            Args:
              - span_or_list: a TextSpan or TextSpan list
        '''
        if isinstance(span_or_list, (list, tuple)):
            for span in span_or_list:
                self.add_span(span)
        else:
            self.add_span(span_or_list)

    def add_span(self, span:TextSpan):
        '''Add span to current Line and update the bbox accordingly.'''
        if span and isinstance(span, TextSpan):
            self.spans.append(span)
            # update bbox
            self.union(span.bbox)


    def intersect(self, rect:fitz.Rect):
        '''Create new Line object with spans contained in given bbox. '''
        # add line directly if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()

        # further check spans in line
        line = Line()
        for span in self.spans:
            contained_span = span.intersect(rect)
            line.add(contained_span)        

        return line
        