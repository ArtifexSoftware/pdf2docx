# -*- coding: utf-8 -*-

'''Text Span object based on PDF raw dict extracted with ``PyMuPDF``.

Data structure for Span refer to 
this `link <https://pymupdf.readthedocs.io/en/latest/textpage.html>`_::

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
                'color': int,
                'uri': str    # for hyperlink
            },
            ...
        ]
    }
'''

import fitz

from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

from .Char import Char
from ..common.Element import Element
from ..common.share import RectType
from ..common import constants
from ..common import share, docx
from ..shape.Shape import Shape


class TextSpan(Element):
    '''Object representing text span.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}
        self.color = raw.get('color', 0)
        self._font = raw.get('font', '')
        self.size = raw.get('size', 12.0)
        self.flags = raw.get('flags', 0)
        self.chars = [ Char(c) for c in raw.get('chars', []) ] # type: list[Char]

        # introduced attributes
        # a list of dict: { 'type': int, 'color': int }
        self.style = raw.get('style', [])
        
        # init text span element
        super().__init__(raw)

        # update bbox if no font is set
        if 'UNNAMED' in self.font.upper(): self.set_font('Arial')        


    @property
    def font(self):
        '''Parse raw font name, e.g. 
        
        * Split with ``+`` and ``-``: BCDGEE+Calibri-Bold, BCDGEE+Calibri -> Calibri.
        * Split with upper case : ArialNarrow -> Arial Narrow, but exception: NSimSUN -> NSimSUN.
        * Replace ``,`` with blank: e.g. Ko Pub Dotum, Light -> KoPubDotum Light.
        
        NSimSUN refers to Chinese font name `新宋体`, so consider a localization mapping.
        '''
        # process on '+' and '-'
        font_name = self._font.split('+')[-1]
        font_name = font_name.split('-')[0]

        # mapping font name
        key = font_name.replace(' ', '').replace('-', '').replace('_', '').upper() # normalize mapping key
        font_name = constants.DICT_FONTS.get(key, font_name)

        # replace ','
        font_name = font_name.replace(',', ' ')

        return font_name


    @property
    def text(self):
        '''Joining chars in text span'''
        chars = [char.c for char in self.chars]        
        return ''.join(chars)

    
    def cal_bbox(self):
        '''Calculate bbox based on contained instances.'''
        bbox = fitz.Rect()
        for char in self.chars: bbox |= char.bbox
        return bbox


    def set_font(self, fontname):
        '''Set new font, and update font size, span/char bbox accordingly.

        It's generally used for span with unnamed fonts. 
        See this `issue <https://github.com/pymupdf/PyMuPDF/issues/642>`_.        

        In corner case, where the PDF file containing unnamed and not embedded fonts, the span bbox
        extracted from ``PyMuPDF`` is not correct. ``PyMuPDF`` provides feature to replace these 
        unnamed fonts with specified fonts, then extract correct bbox from the updated PDF. Since we 
        care less about the original PDF itself but its layout, the idea here is to set a default font 
        for text spans with unnamed fonts, and estimate the updated bbox with method from 
        ``fitz.TextWriter``.

        Args:
            fontname (str): Font name.
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
        self.update_bbox((x0, y0, x1, y1))

        # update contained char bbox
        for char in self.chars:
            x0, _, x1, _ = char.bbox
            char.update_bbox((x0, y0, x1, y1))


    def add(self, char:Char):
        '''Add char and update bbox accordingly.'''
        self.chars.append(char)
        self.union_bbox(char)

    
    def lstrip(self):
        '''Remove blanks at the left side, but keep one blank.'''
        original_text = self.text
        if not original_text.startswith(' '*2): return False

        # keep one blank
        num_blanks = len(original_text) - len(original_text.lstrip())
        self.chars = self.chars[num_blanks-1:]
        self.update_bbox(rect=self.cal_bbox())
        return True
    

    def rstrip(self):
        '''Remove blanks at the right side, but keep one blank.'''
        original_text = self.text
        if not original_text.endswith(' '*2): return False

        # keep one blank
        num_blanks = len(original_text) - len(original_text.rstrip())
        self.chars = self.chars[:1-num_blanks]
        self.update_bbox(rect=self.cal_bbox())
        return True


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


    def plot(self, page, color:tuple): super().plot(page, stroke=color, fill=color, width=0)


    def split(self, rect:Shape, horizontal:bool=True):
        """Split span with the intersection: span-intersection-span.

        Args:
            rect (Shape): Target shape to split this text span.
            horizontal (bool, optional): Text direction. Defaults to True.

        Returns:
            list: Split text spans.
        """        
        # any intersection in this span?
        # NOTE: didn't consider the case that an underline is out of a span
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
            split_span = self.copy().update_bbox(bbox)
            split_span.chars = self.chars[0:pos]
            split_spans.append(split_span)

        # middle intersection part if exists
        if length > 0:
            bbox = (intsec.x0, intsec.y0, intsec.x1, intsec.y1)
            split_span = self.copy().update_bbox(bbox)
            split_span.chars = self.chars[pos:pos_end]            
            split_span._parse_text_format(rect, horizontal)  # update style
            split_spans.append(split_span)

        # right part if exists
        if pos_end < len(self.chars):
            if horizontal:
                bbox = (intsec.x1, self.bbox.y0, self.bbox.x1, self.bbox.y1)
            else:
                bbox = (self.bbox.x0, self.bbox.y0, self.bbox.x1, intsec.y0)
            split_span = self.copy().update_bbox(bbox)
            split_span.chars = self.chars[pos_end:]
            split_spans.append(split_span)

        return split_spans


    def _parse_text_format(self, rect: Shape, horizontal:bool=True):
        """Parse text style based on the position to a rect shape.

        Args:
            rect (Shape): Target rect shape reprenting potential text style.
            horizontal (bool, optional): Horizontal text direction. Defaults to True.

        Returns:
            bool: Parsed text style successfully or not.
        """

        # Skip table border/shading
        if rect.type==RectType.BORDER or rect.type==RectType.SHADING:
            return False
        
        # set hyperlink
        elif rect.type==RectType.HYPERLINK:
            self.style.append({
                'type': rect.type.value,
                'color': rect.color,
                'uri': rect.uri
            })
            return True

        # considering text direction
        idx = 1 if horizontal else 0

        # recognize text format based on rect and the span it applying to
        # region height
        h_rect = rect.bbox[idx+2] - rect.bbox[idx]
        h_span = self.bbox[idx+2] - self.bbox[idx]

        # distance to span bottom border
        d = abs(self.bbox[idx+2] - rect.bbox[idx])

        # highlight: both the rect height and overlap must be large enough
        if h_rect >= 0.5*h_span:
            # In general, highlight color isn't white
            if rect.color != share.rgb_value((1,1,1)) and self.get_main_bbox(rect, constants.FACTOR_MAJOR): 
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
        
        Args:
            rect (fitz.Rect): Target bbox.
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
        span.update_bbox((0.0,0.0,0.0,0.0))

        for char in self.chars:
            if char.get_main_bbox(rect, constants.FACTOR_A_HALF): # contains at least a half part
                span.chars.append(char)
                span.union_bbox(char)

        return span


    def make_docx(self, paragraph):
        '''Add text span to a docx paragraph, and set text style, e.g. font, color, underline, hyperlink, etc.

        .. note::
            Hyperlink and its style is parsed separately from pdf. For instance, regarding a general hyperlink with an
            underline, the text and uri is parsed as hyperlink itself, while the underline is treated as a normal text
            style.
        '''
        # Create hyperlink in particular, otherwise add a run directly
        for style in self.style:
            if style['type']==RectType.HYPERLINK.value and self.text.strip():
                docx_run = docx.add_hyperlink(paragraph, style['uri'], self.text)
                break
        else:
            docx_run = paragraph.add_run(self.text)
        
        # set text style, e.g. font, underline and highlight
        self._set_text_format(docx_run)


    def _set_text_format(self, docx_run):
        '''Set text format for ``python-docx.run`` object.'''
        # set style
        # https://python-docx.readthedocs.io/en/latest/api/text.html#docx.text.run.Font

        # basic font style
        # line['flags'] is an integer, encoding bool of font properties:
        # bit 0: superscripted (2^0)
        # bit 1: italic (2^1)
        # bit 2: serifed (2^2)
        # bit 3: monospaced (2^3)
        # bit 4: bold (2^4)
        docx_run.superscript = bool(self.flags & 2**0)
        docx_run.italic = bool(self.flags & 2**1)
        docx_run.bold = bool(self.flags & 2**4)

        # font name
        font_name = self.font
        docx_run.font.name = font_name
        docx_run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name) # set font for chinese characters
        docx_run.font.color.rgb = RGBColor(*share.rgb_component(self.color))

        # font size
        # NOTE: only x.0 and x.5 is accepted in docx, so set character scaling accordingly
        # if the font size doesn't meet this condition.
        font_size = round(self.size*2)/2.0
        docx_run.font.size = Pt(font_size)

        # adjust by set scaling
        scale = self.size / font_size
        if abs(scale-1.0)>=0.01:
            docx.set_char_scaling(docx_run, scale)
        
        # font style parsed from PDF rectangles: 
        # e.g. highlight, underline, strike-through-line
        for style in self.style:
            
            t = style['type']
            # Built-in method is provided to set highlight in python-docx, but supports only limited colors;
            # so, set character shading instead if out of highlight color scope
            if t==RectType.HIGHLIGHT.value:
                docx.set_char_shading(docx_run, style['color'])

            # underline set with built-in method `font.underline` has a same color with text.
            # so, try to set a different color with xml if necessary
            elif t==RectType.UNDERLINE.value:
                if self.color==style['color']:
                    docx_run.font.underline = True
                else:
                    docx.set_char_underline(docx_run, style['color'])
            
            # same color with text for strike line
            elif t==RectType.STRIKE.value:
                docx_run.font.strike = True

        