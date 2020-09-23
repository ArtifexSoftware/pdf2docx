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

from fitz import Point
from ..common.BBox import BBox
from ..common.base import TextDirection
from .Spans import Spans
from ..image.ImageSpan import ImageSpan


class Line(BBox):
    '''Object representing a line in text block.'''
    def __init__(self, raw:dict={}):
        # bbox is calculated from contained spans
        # so remove key 'bbox' here
        if 'bbox' in raw: raw.pop('bbox') 
        super().__init__(raw)

        # writing mode
        self.wmode = raw.get('wmode', 0) 

        # update writing direction to rotated page CS
        if 'dir' in raw:
            self.dir = list(Point(raw['dir'])*Line.pure_rotation_matrix())
        else:
            self.dir = [1.0, 0.0] # left -> right by default

        # Lines contained in text block may be re-grouped, so use an ID to track the parent block.
        # This ID can't be changed once set -> record the original parent extracted from PDF, 
        # so that we can determin whether two lines belong to a same original text block.
        self._pid = None

        # collect spans
        self.spans = Spans(parent=self).from_dicts(raw.get('spans', []))

    
    @property
    def text(self):
        '''Joining span text.'''
        spans_text = [span.text for span in self.spans]        
        return ''.join(spans_text)


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

    
    @property
    def pid(self):
        '''Get parent ID.'''
        return self._pid


    @pid.setter
    def pid(self, pid):
        '''Set parent ID only if not set before.'''
        if self._pid is None:
            self._pid = int(pid)


    def same_parent_with(self, line):
        '''Check if has same parent ID.'''
        if self.pid is None:
            return False
        else:
            return self.pid == line.pid


    def store(self):
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
        self.spans.append(span)


    def intersects(self, rect):
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
        line = Line({'wmode': self.wmode})
        line.dir = self.dir # update line direction relative to final CS
        for span in self.spans:
            contained_span = span.intersects(rect)
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
        idx = 1 if self.is_horizontal_text else 0

        c1 = (self.bbox[idx] + self.bbox[idx+2]) / 2.0
        c2 = (line.bbox[idx] + line.bbox[idx+2]) / 2.0

        # Note y direction under PyMuPDF context
        res = c1<=line.bbox[idx+2] and c2<=self.bbox[idx+2]
        return res


    def make_docx(self, p):
        for span in self.spans:
            span.make_docx(p)
            