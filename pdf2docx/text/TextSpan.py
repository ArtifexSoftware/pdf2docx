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

from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

from .Char import Char
from ..common.BBox import BBox
from ..common.base import RectType
from ..common.constants import DICT_FONTS
from ..common import utils, docx
from ..shape.Shape import Shape


class TextSpan(BBox):
    '''Object representing text span.'''
    def __init__(self, raw:dict={}):
        super().__init__(raw)
        self.color = raw.get('color', 0)
        self._font = raw.get('font', '')
        self.size = raw.get('size', 12.0)
        self.flags = raw.get('flags', 0)
        self.chars = [ Char(c) for c in raw.get('chars', []) ] # type: list[Char]

        # introduced attributes
        # a list of dict: { 'type': int, 'color': int }
        self.style = raw.get('style', [])

        # update bbox if no font is set
        if 'UNNAMED' in self.font.upper(): self.set_font('Arial')


    @property
    def font(self):
        '''Parse raw font name, e.g. 
            - split with '+' and '-': BCDGEE+Calibri-Bold, BCDGEE+Calibri -> Calibri
            - split with upper case : ArialNarrow -> Arial Narrow, but exception: NSimSUN -> NSimSUN
            - replace ',' with blank: e.g. Ko Pub Dotum, Light -> KoPubDotum Light
        
            NSimSUN refers to Chinese font name `新宋体`, so consider a localization mapping.
        '''
        # process on '+' and '-'
        font_name = self._font.split('+')[-1]
        font_name = font_name.split('-')[0]

        # mapping font name
        key = font_name.replace(' ', '').replace('-', '').replace('_', '').upper() # normalize mapping key
        font_name = DICT_FONTS.get(key, font_name)

        # split with upper case letters
        blank = ' '
        # font_name = ''.join(f'{blank}{x}' if x.isupper() else x for x in font_name).strip(blank)

        # replace ','
        font_name = font_name.replace(',', blank)

        return font_name


    @property
    def text(self):
        '''Joining chars in text span'''
        chars = [char.c for char in self.chars]        
        return ''.join(chars)


    def set_font(self, fontname):
        ''' Set new font, and update font size, span/char bbox accordingly.

            It's generally used for span with unnamed fonts.
            https://github.com/pymupdf/PyMuPDF/issues/642

            In corner case, where the PDF file containing unnamed and not embedded fonts, the span bbox
            extracted from PyMuPDF is not correct. PyMuPDF provides feature to replace these unnamed fonts
            with specified fonts, then extract correct bbox from the updated PDF. Since we care less about
            the original PDF itself but its layout, the idea here is to set a default font for text spans 
            with unnamed fonts, and estimate the updated bbox with method from `fitz.TextWriter`.
        '''
        # set new font
        font = fitz.Font(fontname)
        self._font = fontname

        # compute text length under new font with that size
        new_length = font.text_length(self.text, fontsize=self.size)
        if new_length > self.bbox.width:
            self.size *= self.bbox.width / new_length

        # estimate occupied rect when added with TextWriter
        x0, y0, x1, y1 = self.bbox
        tw = fitz.TextWriter((0, 0, x1, y1))
        rect, _ = tw.append(
            self.chars[0].origin, # the bottom left point of the first character
            self.text,
            font=font,
            fontsize=self.size
        )

        # update span bbox
        # - x-direction: use original horizontal range
        # - y-direction: centerline defined by estimated vertical range, and height by font size
        buff = (rect.height-self.size)/2.0
        y0 = rect.y0 + buff
        y1 = rect.y1 - buff
        self.update((x0, y0, x1, y1))

        # update contained char bbox
        for char in self.chars:
            x0, _, x1, _ = char.bbox
            char.update((x0, y0, x1, y1))


    def add(self, char:Char):
        '''Add char and update bbox accordingly.'''
        self.chars.append(char)
        self.union(char)


    def store(self):
        res = super().store()
        res.update({
            'color': self.color,
            'font': self.font,
            'size': self.size,
            'flags': self.flags,
            'chars': [
                char.store() for char in self.chars
            ],
            'text': self.text,
            'style': self.style
        })
        return res


    def plot(self, page, color:tuple):
        '''Fill bbox with given color.
           ---
            Args: 
              - page: fitz.Page object
        '''
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=False)


    def split(self, rect:Shape, horizontal:bool=True):
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
        if horizontal:
            intsec.y0 = self.bbox.y0
            intsec.y1 = self.bbox.y1
        else:
            intsec.x0 = self.bbox.x0
            intsec.x1 = self.bbox.x1

        # calculate chars in the format rectangle
        # combine an index with enumerate(), so the second element is the char
        f = lambda items: items[1].contained_in_rect(rect, horizontal)
        index_chars = list(filter(f, enumerate(self.chars)))

        # then we get target chars in a sequence
        pos = index_chars[0][0] if index_chars else -1 # start index -1 if nothing found
        length = len(index_chars)
        pos_end = max(pos+length, 0) # max() is used in case: pos=-1, length=0

        # split span with the intersection: span-intersection-span
        # 
        # left part if exists
        if pos > 0:
            if horizontal:
                bbox = (self.bbox.x0, self.bbox.y0, intsec.x0, self.bbox.y1)
            else:
                bbox = (self.bbox.x0, intsec.y1, self.bbox.x1, self.bbox.y1)
            split_span = self.copy().update(bbox)
            split_span.chars = self.chars[0:pos]
            split_spans.append(split_span)

        # middle intersection part if exists
        if length > 0:
            bbox = (intsec.x0, intsec.y0, intsec.x1, intsec.y1)
            split_span = self.copy().update(bbox)
            split_span.chars = self.chars[pos:pos_end]            
            split_span.parse_text_style(rect, horizontal)  # update style
            split_spans.append(split_span)

        # right part if exists
        if pos_end < len(self.chars):
            if horizontal:
                bbox = (intsec.x1, self.bbox.y0, self.bbox.x1, self.bbox.y1)
            else:
                bbox = (self.bbox.x0, self.bbox.y0, self.bbox.x1, intsec.y0)
            split_span = self.copy().update(bbox)
            split_span.chars = self.chars[pos_end:]
            split_spans.append(split_span)

        return split_spans


    def parse_text_style(self, rect: Shape, horizontal:bool=True):
        '''Parse text style based on the position to a span bbox.'''

        # consider text format type only
        if rect.type==RectType.BORDER or rect.type==RectType.SHADING:
            return False

        # considering text direction
        idx = 1 if horizontal else 0

        # recognize text format based on rect and the span it applying to
        # region height
        h_rect = rect.bbox[idx+2] - rect.bbox[idx]
        h_span = self.bbox[idx+2] - self.bbox[idx]

        # distance to span bottom border
        d = self.bbox[idx+2] - rect.bbox[idx]

        # highlight: both the rect height and overlap must be large enough
        if h_rect >= 0.5*h_span:
            # In general, highlight color isn't white
            if rect.color != utils.RGB_value((1,1,1)) and utils.get_main_bbox(self.bbox, rect.bbox, 0.75): 
                rect.type = RectType.HIGHLIGHT
    
        # near to bottom of span? yes, underline
        elif d <= 0.25*h_span:
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


    def intersects(self, rect):
        '''Create new TextSpan object with chars contained in given bbox.
            ---
            Args:
              - rect: fitz.Rect, target bbox
        '''
        # add span directly if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()

        # no intersection
        if not rect.intersects(self.bbox):
            return TextSpan()

        # furcher check chars in span
        span = self.copy()
        span.chars.clear()
        span.update((0.0,0.0,0.0,0.0))

        for char in self.chars:
            if utils.get_main_bbox(char.bbox, rect, 0.55): # contains at least a half part
                span.chars.append(char)
                span.union(char)

        return span


    def make_docx(self, paragraph):
        '''Add text span to a docx paragraph.'''
        # set text
        docx_span = paragraph.add_run(self.text)        

        # set style
        # https://python-docx.readthedocs.io/en/latest/api/text.html#docx.text.run.Font

        # basic font style
        # line['flags'] is an integer, encoding bool of font properties:
        # bit 0: superscripted (2^0)
        # bit 1: italic (2^1)
        # bit 2: serifed (2^2)
        # bit 3: monospaced (2^3)
        # bit 4: bold (2^4)
        docx_span.superscript = bool(self.flags & 2**0)
        docx_span.italic = bool(self.flags & 2**1)
        docx_span.bold = bool(self.flags & 2**4)

        # font name
        font_name = self.font
        docx_span.font.name = font_name
        docx_span._element.rPr.rFonts.set(qn('w:eastAsia'), font_name) # set font for chinese characters
        docx_span.font.color.rgb = RGBColor(*utils.RGB_component(self.color))

        # font size
        # NOTE: only x.0 and x.5 is accepted in docx, so set character scaling accordingly
        # if the font size doesn't meet this condition.
        font_size = round(self.size*2)/2.0
        docx_span.font.size = Pt(font_size)

        # adjust by set scaling
        scale = self.size / font_size
        if abs(scale-1.0)>=0.01:
            docx.set_char_scaling(docx_span, scale)
        
        # font style parsed from PDF rectangles: 
        # e.g. highlight, underline, strike-through-line
        for style in self.style:
            
            t = style['type']
            # Built-in method is provided to set highlight in python-docx, but supports only limited colors;
            # so, set character shading instead if out of highlight color scope
            if t==RectType.HIGHLIGHT.value:
                docx.set_char_shading(docx_span, style['color'])

            # underline set with built-in method `font.underline` has a same color with text.
            # so, try to set a different color with xml if necessary
            elif t==RectType.UNDERLINE.value:
                if self.color==style['color']:
                    docx_span.font.underline = True
                else:
                    docx.set_char_underline(docx_span, style['color'])
            
            # same color with text for strike line
            elif t==RectType.STRIKE.value:
                docx_span.font.strike = True

        