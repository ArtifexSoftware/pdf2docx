# -*- coding: utf-8 -*-

'''Objects representing PDF stroke and filling extracted from Path.

* Stroke: consider only the horizontal or vertical path segments
* Fill  : bbox of closed path filling area

Hyperlink in ``PyMuPDF`` is represented as uri and its rectangular area (hot-area), while the
applied text isn't extracted explicitly. To reuse the process that identifying applied text of
text style shape (e.g. underline and highlight), hyperlink is also abstracted to be a ``Shape``.

.. note::
    The evident difference of hyperlink shape to text style shape is: 
    the :py:class:`~pdf2docx.common.share.RectType` of hyperlink shape is determined in advance,
    while text style shape needs to be identified by the position to associated text blocks.

Above all, the semantic meaning of shape instance may be:

* strike through line of text
* under line of text
* highlight area of text
* table border
* cell shading
* hyperlink

Data structure::

    {
        'type': int,
        'bbox': (x0, y0, x1, y1),
        'color': srgb_value,

        # for Stroke
        'start': (x0, y0),
        'end': (x1, y1),
        'width': float,

        # for Hyperlink
        'uri': str
    }
'''

import fitz
from ..common.Element import Element
from ..common.share import RectType
from ..common import constants


class Shape(Element):
    ''' Shape object.'''
    def __init__(self, raw:dict=None):        
        raw = raw or {}
        self.color = raw.get('color', 0)
        super().__init__(raw) # bbox

        # set rect type
        raw_type = raw.get('type', RectType.UNDEFINED.value) # UNDEFINED by default
        for t in RectType:
            if t.value==raw_type:
                rect_type = t
                break
        else:
            rect_type = RectType.UNDEFINED
        self.type = rect_type
    
    @property
    def is_determined(self): return self.type != RectType.UNDEFINED

    def store(self):
        res = super().store()
        res.update({
            'type': self.type.value,
            'color': self.color
        })
        return res


    def semantic_type(self, blocks:list):
        """Determin semantic type based on the position to text blocks.

        Args:
            blocks (list): A list of ``TextBlock`` instance.

        Returns:
            RectType: Shape type.
        """
        # NOTE: blocks must be sorted in reading order
        rect_type = RectType.UNDEFINED
        for block in blocks:
            # not intersect yet
            if block.bbox.y1 < self.bbox.y0: continue

            # check it when intersected
            rect_type = self._check_semantic_type(block)
            if rect_type != RectType.UNDEFINED: break

            # no intersection any more
            if block.bbox.y0 > self.bbox.y1: break
        
        return rect_type


    def _check_semantic_type(self, block):
        ''' Check semantic type based on the position to a text block.
            Return RectType.UNDEFINED if can't be determined this this text block.
            Prerequisite: intersection exists between this shape and block.
        '''
        return RectType.UNDEFINED
            

    def plot(self, page, color):
        '''Plot rectangle shapes with ``PyMuPDF``.'''
        page.drawRect(self.bbox, color=color, fill=color, width=0, overlay=True)


class Stroke(Shape):
    ''' Horizontal or vertical stroke of a path. 
        The semantic meaning may be table border, or text style line like underline and strike-through.
    '''
    def __init__(self, raw:dict=None):
        raw = raw or {}
        # convert start/end point to real page CS
        self._start = fitz.Point(raw.get('start', (0.0, 0.0))) * Stroke.ROTATION_MATRIX
        self._end = fitz.Point(raw.get('end', (0.0, 0.0))) * Stroke.ROTATION_MATRIX

        if self._start.x > self._end.x or self._start.y > self._end.y:
            self._start, self._end = self._end, self._start

        # width, color
        super().__init__(raw) # type, color
        self.width = raw.get('width', 0.0)

        # update bbox
        super().update_bbox(self._to_rect())


    @property
    def horizontal(self): return abs(self._start[1]-self._end[1])<1e-3

    @property
    def vertical(self): return abs(self._start[0]-self._end[0])<1e-3

    @property
    def x0(self): return self._start.x

    @property
    def x1(self): return self._end.x

    @property
    def y0(self): return self._start.y

    @property
    def y1(self): return self._end.y


    def update_bbox(self, rect):
        """Update stroke bbox (related to real page CS).

        * Update start/end points if ``rect.area==0``.
        * Ppdate bbox directly if ``rect.area!=0``.

        Args:
            rect (fitz.Rect, tuple): ``(x0, y0, x1, y1)`` like data.

        Returns:
            Stroke: self
        """
        rect = fitz.Rect(rect)

        # an empty area line
        if rect.getArea()==0.0:
            self._start = fitz.Point(rect[0:2])
            self._end = fitz.Point(rect[2:])
            super().update_bbox(self._to_rect())

        # a rect 
        else:
            super().update_bbox(rect)

            # horizontal stroke
            if rect.width >= rect.height:
                y = (rect.y0+rect.y1)/2.0
                self._start = fitz.Point(rect.x0, y)
                self._end   = fitz.Point(rect.x1, y)

            # vertical stroke
            else: 
                x = (rect.x0+rect.x1)/2.0
                self._start = fitz.Point(x, rect.y0)
                self._end   = fitz.Point(x, rect.y1)

        return self


    def _check_semantic_type(self, block):
        '''Override. Check semantic type of a Stroke: table border v.s. text style line, e.g. underline and strike-through.

        Generally, text style line is contained in a certain block, while table border is never contained.
        But in real cases, where tight layout or incorrectly organized text blocks exist,  

        * a text style line may have no intersection with the applied text block
        * a table border may be very close to a text block, which seems contained in that block
        
        Conservatively, try to determin semantic type like underline and strike-through on condition that:

        * it's contained in a text block, AND
        * also contained in a certain line of that text block.

        .. note::
            A stroke that not determined by this block, can be either table border or text style line.
            So the returned RectType.UNDEFINED means not able to determin its type.
        '''
        # check block first
        if not block.contains(self): return RectType.UNDEFINED

        # check block line for further confirmation
        for line in block.lines:            
            if line.contains(self): return RectType.UNDERLINE_OR_STRIKE
        
        return RectType.UNDEFINED


    def store(self):
        res = super().store()
        res.update({
            'start': tuple(self._start),
            'end': tuple(self._end),
            'width': self.width
        })
        return res


    def _to_rect(self):
        '''Convert centerline to rectangle shape.'''
        h = self.width / 2.0
        x0, y0 = self._start
        x1, y1 = self._end        
        return (x0-h, y0-h, x1+h, y1+h)


class Fill(Shape):
    ''' Rectangular (bbox) filling area of a closed path. 
        The semantic meaning may be table shading, or text style like highlight.
    '''

    def to_stroke(self, max_border_width:float):
        """Convert to Stroke instance based on width criterion.

        Args:
            max_border_width (float): Stroke width must less than this value.

        Returns:
            Stroke: Stroke instance.
        
        .. note::
            A Fill from shape point of view may be a Stroke from content point of view.
            The criterion here is whether the width is smaller than defined ``max_border_width``.
        """
        w = min(self.bbox.width, self.bbox.height)

        # not a stroke if exceed max border width
        if w > max_border_width:
            return None
        else:
            return Stroke({'width': w, 'color': self.color}).update_bbox(self.bbox)
    

    def _check_semantic_type(self, block):
        """Override. Check semantic type based on the position to a text block.

        Args:
            block (TextBlock): A text block.

        Returns:
            RectType: Semantic type of this shape.
        
        .. note::
            Generally, table shading always contains at least one block line, while text highlight doesn't
            contain any lines. But in real cases, with margin exists, table shading may not 100% contain a
            block line, e.g. a factor like 98% or so.
        """
        # check block first
        if self.contains(block, threshold=constants.FACTOR_MAJOR): return RectType.SHADING
        
        # not contain but intersects -> check block line for another chance
        for line in block.lines:
            if self.contains(line, threshold=constants.FACTOR_MAJOR): 
                return RectType.SHADING
        
        return RectType.UNDEFINED # can't be determined by this block


class Hyperlink(Shape):
    '''Rectangular area, i.e. ``hot area`` for a hyperlink. 
    
    Hyperlink in ``PyMuPDF`` is represented as uri and its hot area, while the applied text isn't extracted 
    explicitly. To reuse the process that identifying applied text of text style shape (e.g. underline and 
    highlight), hyperlink is also abstracted to be a ``Shape``.
    '''

    def __init__(self, raw:dict={}):
        '''Initialize from raw dict. Note the type must be determined in advance.'''
        if raw is None: raw = {}
        super().__init__(raw)

        # set uri
        self.uri = raw.get('uri', '')
        

    def store(self):
        res = super().store()
        res.update({
            'uri': self.uri
        })
        return res


    def semantic_type(self, blocks:list=None):
        """Semantic type of Hyperlink shape is determined, i.e. ``RectType.HYPERLINK``."""
        return RectType.HYPERLINK