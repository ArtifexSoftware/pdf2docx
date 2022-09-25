# -*- coding: utf-8 -*-

'''
Text Line objects based on PDF raw dict extracted with ``PyMuPDF``.

Data structure of line in text block referring to this
`link <https://pymupdf.readthedocs.io/en/latest/textpage.html>`_::

    {
        'bbox': (x0,y0,x1,y1),
        'wmode': m,
        'dir': [x,y],
        'spans': [ spans ]
    }
'''

from fitz import Point
try:
    # Python <= 3.9
    from collections import Iterable
except ImportError:
    # Python > 3.9
    from collections.abc import Iterable
from .TextSpan import TextSpan
from ..common.Element import Element
from ..common.share import TextDirection
from .Spans import Spans
from ..image.ImageSpan import ImageSpan


class Line(Element):
    '''Object representing a line in text block.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}

        # writing mode
        self.wmode = raw.get('wmode', 0) 

        # update writing direction to rotated page CS
        if 'dir' in raw:
            self.dir = list(Point(raw['dir'])*Line.pure_rotation_matrix())
        else:
            self.dir = [1.0, 0.0] # left -> right by default

        # line break
        self.line_break = raw.get('line_break', 0) # don't break line by default
        self.tab_stop = raw.get('tab_stop', 0) # no TAB stop before the line by default
        
        # remove key 'bbox' since it is calculated from contained spans
        if 'bbox' in raw: raw.pop('bbox') 
        super().__init__(raw)

        # collect spans
        self.spans = Spans(parent=self).restore(raw.get('spans', []))        

    
    @property
    def text(self):
        '''Joining span text. Note image is translated to a placeholder ``<image>``.'''
        spans_text = [span.text for span in self.spans]
        return ''.join(spans_text)


    @property
    def raw_text(self):
        '''Joining span text with image ignored.'''
        spans_text = [span.text for span in self.spans if isinstance(span, TextSpan)]
        return ''.join(spans_text)


    @property
    def white_space_only(self):
        '''If this line contains only white space or not. If True, this line is safe to be removed.'''
        for span in self.spans:
            if not isinstance(span, TextSpan): return False
            if span.text.strip(): return False
        return True


    @property
    def image_spans(self):
        '''Get image spans in this Line.'''
        return list(filter(
            lambda span: isinstance(span, ImageSpan), self.spans
        ))


    @property
    def text_direction(self):
        '''Get text direction. Consider ``LEFT_RIGHT`` and ``LEFT_RIGHT`` only.

        Returns:
            TextDirection: Text direction of this line.
        '''
        if self.dir[0] == 1.0:
            return TextDirection.LEFT_RIGHT
        elif self.dir[1] == -1.0:
            return TextDirection.BOTTOM_TOP
        else:
            return TextDirection.IGNORE


    def strip(self):
        '''Remove redundant blanks at the begin/end span.'''
        return self.spans.strip()



    def store(self):
        res = super().store()
        res.update({
            'wmode'     : self.wmode,
            'dir'       : self.dir,
            'line_break': self.line_break,
            'tab_stop'  : self.tab_stop,
            'spans'     : [
                span.store() for span in self.spans
            ]
        })

        return res


    def add(self, span_or_list):
        '''Add span list to current Line.
        
        Args:
            span_or_list (Span, Iterable): TextSpan or TextSpan list to add.
        '''
        if isinstance(span_or_list, Iterable):
            for span in span_or_list:
                self.add_span(span)
        else:
            self.add_span(span_or_list)


    def add_span(self, span:Element):
        '''Add span to current Line.'''
        self.spans.append(span)


    def intersects(self, rect):
        '''Create new Line object with spans contained in given bbox.
        
        Args:
            rect (fitz.Rect): Target bbox.
        
        Returns:
            Line: The created Line instance.
        '''
        # add line directly if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()
        
        # new line with same text attributes
        line = Line({'wmode': self.wmode})
        line.dir = self.dir # update line direction relative to final CS

        # further check spans in line        
        for span in self.spans:
            contained_span = span.intersects(rect)
            line.add(contained_span)

        return line


    def make_docx(self, p):
        '''Create docx line, i.e. a run in ``python-docx``.'''
        # tab stop before this line to ensure horizontal position
        # Note it might need more than one tabs if multi-tabs are set for current paragraph
        if self.tab_stop: 
            for _ in range(self.tab_stop): p.add_run().add_tab()

        # create span -> run in paragraph
        for span in self.spans: span.make_docx(p)            

        # line break
        if self.line_break: p.add_run('\n')
            
