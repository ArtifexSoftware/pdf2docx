# -*- coding: utf-8 -*-

'''
Text Span object based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---

Refer to: https://pymupdf.readthedocs.io/en/latest/textpage.html

data structure for Span
    {
        # raw dict
        ---------------------------
        'bbox': (x0,y0,x1,y1),
        'color': sRGB
        'font': fontname,
        'size': fontzise,
        'flags': fontflags,
        'chars': [ chars ],

        # added dict
        ----------------------------
        'text': text,
        'style': [
            {
                'type': int,
                'color': int
            },
            ...
        ]
    }
'''


import fitz
import copy
from .Char import Char
from ..common.BBox import BBox
from ..common.base import RectType
from ..common import utils
from ..shape.Rectangle import Rectangle


class TextSpan(BBox):
    '''Object representing text span.'''
    def __init__(self, raw: dict) -> None:
        super(TextSpan, self).__init__(raw)
        self.color = raw.get('color', 0)
        self.font = raw.get('font', None)
        self.size = raw.get('size', 12.0)
        self.flags = raw.get('flags', 0)
        self.chars = [ Char(c) for c in raw.get('chars', []) ]

        # introduced attributes
        self._text = None
        self.style = [] # a list of dict: { 'type': int, 'color': int }


    @property
    def text(self):
        '''Joining chars in text span'''
        if self._text is None:
            chars = [char.c for char in self.chars]
            self._text = ''.join(chars)
        
        return self._text


    def add(self, char:Char):
        '''Add char and update bbox accordingly.'''
        self.chars.append(char)
        self.union(char.bbox)


    def store(self) -> dict:
        res = super().store()
        res.update({
            'color': self.color,
            'font': self.font,
            'size': self.size,
            'flags': self.flags,
            'chars': [
                char.store() for char in self.chars
            ]
        })
        return res


    def plot(self, page, color:tuple):
        '''Fill bbox with given color.
           ---
            Args: 
              - page: fitz.Page object
        '''
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=False)


    def split(self, rect:Rectangle) -> list:
        '''Split span with the intersection: span-intersection-span.'''
        # any intersection in this span?
        intsec = rect.bbox & self.bbox

        # no, then add this span as it is
        if not intsec: return [self]

        # yes, then split spans:
        # - add new style to the intersection part
        # - keep the original style for the rest
        split_spans = [] # type: list[TextSpan]

        # expand the intersection area, e.g. for strike through line,
        # the intersection is a `line`, i.e. a rectangle with very small height,
        # so expand the height direction to span height
        intsec.y0 = self.bbox.y0
        intsec.y1 = self.bbox.y1

        # calculate chars in the format rectangle
        # combine an index with enumerate(), so the second element is the char
        f = lambda items: items[1].contained_in_rect(rect)
        index_chars = list(filter(f, enumerate(self.chars)))

        # then we get target chars in a sequence
        pos = index_chars[0][0] if index_chars else -1 # start index -1 if nothing found
        length = len(index_chars)
        pos_end = max(pos+length, 0) # max() is used in case: pos=-1, length=0

        # split span with the intersection: span-intersection-span
        # 
        # left part if exists
        if pos > 0:
            split_span = self.copy()
            split_span.update((self.bbox.x0, self.bbox.y0, intsec.x0, self.bbox.y1))
            split_span.chars = self.chars[0:pos]
            split_spans.append(split_span)

        # middle intersection part if exists
        if length > 0:
            split_span = self.copy()
            split_span.update((intsec.x0, intsec.y0, intsec.x1, intsec.y1))
            split_span.chars = self.chars[pos:pos_end]            
            split_span.parse_text_style(rect)  # update style
            split_spans.append(split_span)                

        # right part if exists
        if pos_end < len(self.chars):
            split_span = self.copy()
            split_span.update((intsec.x1, self.bbox.y0, self.bbox.x1, self.bbox.y1))
            split_span.chars = self.chars[pos_end:]
            split_spans.append(split_span)

        return split_spans


    def parse_text_style(self, rect: Rectangle) -> bool:
        '''Parse text style based on the position to a span bbox.'''

        # consider text format type only
        if rect.type==RectType.BORDER or rect.type==RectType.SHADING:
            return False

        # recognize text format based on rect and the span it applying to
        # region height
        h_rect = rect.bbox.y1 - rect.bbox.y0
        h_span = self.bbox.y1 - self.bbox.y0

        # distance to span bottom border
        d = self.bbox.y1 - rect.bbox.y0

        # the height of rect is large enough?
        # yes, it's highlight
        if h_rect > 0.75*h_span:
            # In general, highlight color isn't white
            if rect.color != utils.RGB_value((1,1,1)): 
                rect.type = RectType.HIGHLIGHT
            else:
                rect.type = RectType.UNDEFINED

        # near to bottom of span? yes, underline
        elif d < 0.25*h_span:
            rect.type = RectType.UNDERLINE

        # near to center of span? yes, strike-through-line
        elif 0.35*h_span < d < 0.75*h_span:
            rect.type = RectType.STRIKE

        # unknown style
        else:
            rect.type = RectType.UNDEFINED

        # check rect type again
        if rect.type==RectType.UNDEFINED: return False

        style =  {
            'type': rect.type.value,
            'color': rect.color
        }
        self.style.append(style)

        return True


    def intersect(self, rect:fitz.Rect):
        '''Create new Span object with chars contained in given bbox. '''
        # add span directly if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()

        # no intersection
        if not rect.intersects(self.bbox):
            return TextSpan()

        # furcher check chars in span
        span_chars = [] # type: list[Char]
        span_bbox = fitz.Rect()
        for char in self.chars:
            if utils.get_main_bbox(char.bbox, rect, 0.2):
                span_chars.append(char)
                span_bbox = span_bbox | self.bbox
        
        if not span_chars: return TextSpan()
            
        # update span
        span = self.copy()
        span.chars = span_chars
        span.update(span_bbox)

        return span