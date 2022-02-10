# -*- coding: utf-8 -*-

'''Objects representing PDF stroke and filling extracted from Path.

* Stroke: consider only the horizontal or vertical path segments
* Fill  : bbox of closed path filling area

Hyperlink in ``PyMuPDF`` is represented as uri and its rectangular area (hot-area), while the
applied text isn't extracted explicitly. To reuse the process that identifying applied text of
text style shape (e.g. underline and highlight), hyperlink is also abstracted to be a ``Shape``.

.. note::
    The evident difference of hyperlink shape to text style shape is: the ``type`` of hyperlink 
    shape is determined in advance, while text style shape needs to be identified by the position 
    to associated text blocks.

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

.. note::
    These coordinates are relative to real page CS since they're extracted from ``page.get_drawings()``,
    which is based on real page CS. So, needn't to multiply Element.ROTATION_MATRIX when initializing
    from source dict.
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
        
        # NOTE: coordinates are based on real page CS already
        super().update_bbox(raw.get('bbox', (0,)*4))
        self._parent = None

        # shape semantic type
        # It's able to set shape type in ``RectType``, but a shape might belong to multi-types before
        # it's finalized. So, set int type here.
        self._type = raw.get('type', -1)            # final type
        self._potential_type = self.default_type    # potential types, a combination of raw RectType-s


    @property
    def type(self): return self._type

    @type.setter
    def type(self, rect_type:RectType): self._type = rect_type.value

    @property
    def is_determined(self): 
        '''If the shape type is determined to a basic item of RectType.'''
        return self._type != -1

    def equal_to_type(self, rect_type:RectType): 
        '''If shape type is equal to the specified one or not.'''
        return self._type==rect_type.value

    def has_potential_type(self, rect_type:RectType):
        '''If shape type has a chance to be the specified one or not.'''
        return self._potential_type & rect_type.value

    @property
    def default_type(self): 
        '''Default semantic type for a shape.'''
        return sum(t.value for t in RectType)


    def store(self):
        res = super().store()
        res.update({
            'type': self._type,
            'color': self.color
        })
        return res


    def parse_semantic_type(self, blocks:list):
        '''Determin semantic type based on the position to text blocks. Note the results might be 
        a combination of raw types, e.g. the semantic type of a stroke can be either text strike,
        underline or table border.

        Args:
            blocks (list): A list of ``Line`` instance, sorted in reading order in advance.
        '''
        for line in blocks:
            # not intersect yet
            if line.bbox.y1 < self.bbox.y0: continue
            
            # no intersection any more
            if line.bbox.y0 > self.bbox.y1: break

            # check it when intersected
            rect_type = self._semantic_type(line)
            self._potential_type = rect_type

            if rect_type!=self.default_type: break


    def _semantic_type(self, line):
        ''' Check semantic type based on the position to a text line.
            Return all possibilities if can't be determined with this text line.
            Prerequisite: intersection exists between this shape and line.
        '''
        return self.default_type


    def plot(self, page, color):
        '''Plot rectangle shapes with ``PyMuPDF``.'''
        page.draw_rect(self.bbox, color=color, fill=color, width=0, overlay=True)


class Stroke(Shape):
    ''' Horizontal or vertical stroke of a path. 
        The semantic meaning may be table border, or text style line like underline and strike-through.
    '''
    def __init__(self, raw:dict=None):
        raw = raw or {}
        # NOTE: real page CS
        self._start = fitz.Point(raw.get('start', (0.0, 0.0)))
        self._end = fitz.Point(raw.get('end', (0.0, 0.0)))

        if self._start.x > self._end.x or self._start.y > self._end.y:
            self._start, self._end = self._end, self._start

        # width, color
        super().__init__(raw) # type, color
        self.width = raw.get('width', 0.0) # Note this "width" is actually the height of stroke

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
        '''Update stroke bbox (related to real page CS).

        * Update start/end points if ``rect.area==0``.
        * Ppdate bbox directly if ``rect.area!=0``.

        Args:
            rect (fitz.Rect, tuple): ``(x0, y0, x1, y1)`` like data.

        Returns:
            Stroke: self
        '''
        rect = fitz.Rect(rect)

        # an empty area line
        if rect.get_area()==0.0:
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

    @property
    def default_type(self):
        '''Default sementic type for a Stroke shape: table border, underline or strike-through.'''
        return RectType.BORDER.value | RectType.UNDERLINE.value | RectType.STRIKE.value

    def _semantic_type(self, line):
        '''Override. Check semantic type of a Stroke: table border v.s. text style line, e.g. underline 
        and strike-through. It's potentially a text style line when:

        * the stroke and the text line has same orientation; and
        * the stroke never exceeds the text line along the main direction
        '''
        # check intersection
        expanded_shape = self.get_expand_bbox(2.0)
        if not line.bbox.intersects(expanded_shape): 
            return self.default_type        

        # check orientation
        h_shape = self.horizontal
        h_line = line.is_horizontal_text
        if h_shape != h_line: 
            return self.default_type

        # check main dimension
        line_x0, line_x1 = (line.bbox.x0, line.bbox.x1) if h_line else (line.bbox.y0, line.bbox.y1)
        shape_x0, shape_x1 = (self.bbox.x0, self.bbox.x1) if h_shape else (self.bbox.y0, self.bbox.y1)
        if shape_x0>=line_x0-1 and shape_x1<=line_x1+1: # 1 pt tolerance at both sides
            return RectType.STRIKE.value | RectType.UNDERLINE.value
        else:
            return RectType.BORDER.value        


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
        '''Convert to Stroke instance based on width criterion.

        Args:
            max_border_width (float): Stroke width must less than this value.

        Returns:
            Stroke: Stroke instance.
        
        .. note::
            A Fill from shape point of view may be a Stroke from content point of view.
            The criterion here is whether the width is smaller than defined ``max_border_width``.
        '''
        w = min(self.bbox.width, self.bbox.height)

        # not a stroke if exceed max border width
        if w > max_border_width:
            return None
        else:
            return Stroke({'width': w, 'color': self.color}).update_bbox(self.bbox)
    

    @property
    def default_type(self):
        '''Default sementic type for a Fill shape: table shading or text highlight.'''
        return RectType.SHADING.value | RectType.HIGHLIGHT.value
    
    def _semantic_type(self, line):
        '''Override. Check semantic type based on the position to a text line. Along the main dimesion,
        text highlight never exceeds text line.

        Args:
            line (Line): A text line.

        Returns:
            RectType: Semantic type of this shape.
        
        .. note::
            Generally, table shading always contains at least one line, while text highlight never
            contains any lines. But in real cases, with margin exists, table shading may not 100% 
            contain a line.
        '''
        # check main dimension
        h_shape = self.bbox.width>self.bbox.height
        w_shape = self.bbox.width if h_shape else self.bbox.height

        # check orientation
        h_line = line.is_horizontal_text
        if h_shape != h_line: 
            return self.default_type

        if not self.get_main_bbox(line, threshold=constants.FACTOR_MAJOR): 
            return self.default_type
        
        w_line = line.bbox.width if h_line else line.bbox.height            
        if w_shape <= w_line + 2*constants.MINOR_DIST: # 1 pt tolerance at both sides
            return RectType.HIGHLIGHT.value
        else:
            return RectType.SHADING.value        


class Hyperlink(Shape):
    '''Rectangular area, i.e. ``hot area`` for a hyperlink. 
    
    Hyperlink in ``PyMuPDF`` is represented as uri and its hot area, while the applied text isn't extracted 
    explicitly. To reuse the process that identifying applied text of text style shape (e.g. underline and 
    highlight), hyperlink is also abstracted to be a ``Shape``.
    '''

    def __init__(self, raw:dict=None):
        '''Initialize from raw dict. Note the type must be determined in advance.'''
        super().__init__(raw)

        # set uri
        self.uri = raw.get('uri', '')
        

    def store(self):
        res = super().store()
        res.update({
            'uri': self.uri
        })
        return res


    @property
    def default_type(self):
        '''Default sementic type for a Hyperlink: always hyperlink.'''
        return RectType.HYPERLINK.value

    def parse_semantic_type(self, blocks:list=None):
        '''Semantic type of Hyperlink shape is determined, i.e. ``RectType.HYPERLINK``.'''
        self._potential_type = self.default_type