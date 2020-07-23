# -*- coding: utf-8 -*-

'''
Object representing rectangles and lines, which is parsed from both raw streams and annotations of pdf.

@created: 2020-07-22
@author: train8808@gmail.com
---

The context meaning of rectangle shape may be:
    - strike through line of text
    - under line of text
    - highlight area of text
    - table border
    - cell shading

Rectangle data structure:
    {
        'type': int,
        'bbox': (x0, y0, x1, y1),
        'color': sRGB_value
    }
'''


from ..common.BBox import BBox
from ..common.base import RectType
from ..common import utils
from ..text.Span import TextSpan


class Rectangle(BBox):
    ''' Rectangle or line shapes parsed from pdf.'''
    def __init__(self, raw: dict) -> None:
        super(Rectangle, self).__init__(raw)
        self._type = RectType.UNDEFINED # no type by default
        self.color = raw.get('color', 0)

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, rect_type: RectType):
        self._type = rect_type

    def store(self) -> dict:
        res = super().store()
        res.update({
            'type': self._type.value,
            'color': self.color
        })
        return res

    def plot(self, page, color:tuple):
        '''Plot rectangle shapes with PyMuPDF.
            ---
            Args:
              - page: fitz.Page object
        '''        
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=False)


    def to_text_style(self, span: TextSpan) -> dict:
        ''' Determin text style based on the position to a span bbox.
        '''

        # consider text format type only
        if self._type==RectType.BORDER or self._type==RectType.SHADING:
            return None

        # recognize text format based on rect and the span it applying to
        # region height
        h_rect = self.bbox.y1 - self.bbox.y0
        h_span = span.bbox.y1 - span.bbox.y0

        # distance to span bottom border
        d = span.bbox.y1 - self.bbox.y0

        # the height of rect is large enough?
        # yes, it's highlight
        if h_rect > 0.75*h_span:
            # In general, highlight color isn't white
            if self.color != utils.RGB_value((1,1,1)): 
                self._type = RectType.HIGHLIGHT
            else:
                self._type = RectType.UNDEFINED

        # near to bottom of span? yes, underline
        elif d < 0.25*h_span:
            self._type = RectType.UNDERLINE

        # near to center of span? yes, strike-through-line
        elif 0.35*h_span < d < 0.75*h_span:
            self._type = RectType.STRIKE

        # unknown style
        else:
            self._type = RectType.UNDEFINED

        # check rect type again
        if self._type==RectType.UNDEFINED:
            style = None
        else:
            style =  {
                'type': self._type,
                'color': self.color
            }
        
        return style    

