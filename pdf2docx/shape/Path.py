# -*- coding: utf-8 -*-

'''
Objects representing PDF path (stroke and filling) extracted from pdf drawings and annotations.

Data structure based on results of ``page.get_drawings()``::

    {
        'color': (x,x,x) or None,  # stroke color
        'fill' : (x,x,x) or None,  # fill color
        'width': float,            # line width
        'closePath': bool,         # whether to connect last and first point
        'rect' : rect,             # page area covered by this path
        'items': [                 # list of draw commands: lines, rectangle or curves.
            ("l", p1, p2),         # a line from p1 to p2
            ("c", p1, p2, p3, p4), # cubic Bézier curve from p1 to p4, p2 and p3 are the control points
            ("re", rect),          # a rect represented with two diagonal points
            ("qu", quad)           # a quad represented with four corner points
        ],
        ...
    }

References: 
    - https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_drawings
    - https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings

.. note::
    The coordinates extracted by ``page.get_drawings()`` is based on **real** page CS, i.e. with rotation 
    considered. This is different from ``page.get_text('rawdict')``.
'''

import fitz
from ..common.share import rgb_value
from ..common import constants


class Segment:
    '''A segment of path, e.g. a line or a rectangle or a curve.'''
    def __init__(self, item):
        self.points = item[1:]

    def to_strokes(self, width:float, color:list): return []


class L(Segment):
    '''Line path with source ``("l", p1, p2)``.'''

    @property
    def length(self):
        x0, y0 = self.points[0]
        x1, y1 = self.points[1]
        return ((x1-x0)**2+(y1-y0)**2)**0.5


    def to_strokes(self, width:float, color:list):
        """Convert to stroke dict.

        Args:
            width (float): Specify width for the stroke.
            color (list): Specify color for the stroke.

        Returns:
            list: A list of ``Stroke`` dicts. 
        
        .. note::
            A line corresponds to one stroke, but considering the consistence, 
            the return stroke dict is append to a list. So, the length of list 
            is always 1.
        """ 
        strokes = []
        strokes.append({
                'start': self.points[0],
                'end'  : self.points[1],
                'width': width,
                'color': rgb_value(color)
            })
        return strokes


class R(Segment):
    '''Rect path with source ``("re", rect)``.'''
    def __init__(self, item):
        # corner points
        # NOTE: center line of path without stroke width considered
        x0, y0, x1, y1 = item[1]
        self.points = [
            (x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0) # close path
            ]


    def to_strokes(self, width:float, color:list):
        """Convert each edge to stroke dict.

        Args:
            width (float): Specify width for the stroke.
            color (list): Specify color for the stroke.

        Returns:
            list: A list of ``Stroke`` dicts. 
        
        .. note::
            One Rect path is converted to a list of 4 stroke dicts.
        """
        strokes = []
        for i in range(len(self.points)-1):
            strokes.append({
                    'start': self.points[i],
                    'end'  : self.points[i+1],
                    'width': width * 2.0, # seems need adjustment by * 2.0
                    'color': rgb_value(color)
                })
        return strokes


class Q(R):
    '''Quad path with source ``("qu", quad)``.'''
    def __init__(self, item):
        # four corner points
        # NOTE: center line of path without stroke width considered
        ul, ur, ll, lr = item[1]
        self.points = [ul, ur, lr, ll, ul] # close path


class C(Segment):
    '''Bezier curve path with source ``("c", p1, p2, p3, p4)``.'''
    pass


class Segments:
    '''A sub-path composed of one or more segments.'''
    def __init__(self, items:list, close_path=False): 
        self._instances = [] # type: list[Segment]
        for item in items:
            if   item[0] == 'l' : self._instances.append(L(item))
            elif item[0] == 'c' : self._instances.append(C(item))
            elif item[0] == 're': self._instances.append(R(item))
            elif item[0] == 'qu': self._instances.append(Q(item))
        
        # close path
        if close_path:
            item = ('l', self._instances[-1].points[-1], self._instances[0].points[0])
            line = L(item)
            if line.length>1e-3: self._instances.append(line)

    
    def __iter__(self): return (instance for instance in self._instances)


    @property
    def points(self):
        '''Connected points of segments.'''
        points = []
        for segment in self._instances:
            points.extend(segment.points)
        return points


    @property
    def is_iso_oriented(self):
        '''ISO-oriented criterion: the ratio of real area to bbox exceeds 0.9.'''
        bbox_area = self.bbox.get_area()
        return bbox_area==0 or self.area/bbox_area>=constants.FACTOR_MOST


    @property
    def area(self):
        '''Calculate segments area with Green formulas. Note the boundary of Bezier curve 
        is simplified with its control points.
        
        * https://en.wikipedia.org/wiki/Shoelace_formula
        '''        
        points = self.points
        start, end = points[0], points[-1]
        if abs(start[0]-end[0])+abs(start[1]-end[1])>1e-3: 
            return 0.0 # open curve
            
        # closed curve 
        area = 0.0       
        for i in range(len(points)-1):
            x0, y0 = points[i]
            x1, y1 = points[i+1]
            area += x0*y1 - x1*y0

        return abs(area/2.0)


    @property
    def bbox(self):
        '''Calculate segments bbox. '''
        points = self.points
        x0 = min(points, key=lambda point: point[0])[0]
        y0 = min(points, key=lambda point: point[1])[1]
        x1 = max(points, key=lambda point: point[0])[0]
        y1 = max(points, key=lambda point: point[1])[1]
        
        # bbox: `round()` is required to avoid float error
        return fitz.Rect(
            round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))


    def to_strokes(self, width:float, color:list):
        """Convert each segment to a ``Stroke`` dict.

        Args:
            width (float): Specify stroke width.
            color (list): Specify stroke color.

        Returns:
            list: A list of ``Stroke`` dicts.
        """        
        strokes = []
        for segment in self._instances: 
            strokes.extend(segment.to_strokes(width, color))
        return strokes
    

    def to_fill(self, color:list):
        """Convert segment closed area to a ``Fill`` dict.

        Args:
            color (list): Specify fill color.

        Returns:
            dict: ``Fill`` dict.
        """        
        return {
            'bbox' : list(self.bbox), 
            'color': rgb_value(color)
        }


class Path:
    '''Path extracted from PDF, consist of one or more ``Segments``.'''
    def __init__(self, raw:dict):
        '''Init path in real page CS.

        Args:
            raw (dict): Raw dict extracted with `PyMuPDF`, see link
            https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_drawings
        '''
        # all path properties
        self.raw = raw
        self.path_type = raw['type'] # s, f, or fs

        # always close path if fill, otherwise, depends on property 'closePath'
        close_path = True if self.is_fill else raw.get('closePath', False)

        # path segments
        self.items = [] # type: list[Segments]
        self.bbox = fitz.Rect()
        w = raw.get('width', 0.0)
        for segments in self._group_segments(raw['items']):
            S = Segments(segments, close_path)
            self.items.append(S)

            # update bbox: note iso-oriented line segments -> S.bbox.get_area()==0
            rect = S.bbox
            if rect.get_area()==0: rect += (-w, -w, w, w)
            self.bbox |= rect


    @staticmethod
    def _group_segments(items):
        """Group connected segments.

        Args:
            items (dict): Raw dict extracted from ``page.get_drawings()``.

        Returns:
            list: A list of segments list.
        """        
        segments, segments_list = [], []
        cursor = None
        for item in items:
            # line or curve segment
            if item[0] in ('l', 'c'):
                start, end = item[1], item[-1]
                # add to segments if:
                # - first point of segments, or
                # - connected to previous segment
                if not segments or start==cursor:
                    segments.append(item)                    
                
                # otherwise, close current segments and start a new one
                else:
                    segments_list.append(segments)
                    segments = [item] 
                
                # update current point
                cursor = end

            # rectangle / quad as a separate segments group
            elif item[0] in ('re', 'qu'):
                # close current segments
                if segments:
                    segments_list.append(segments)
                    segments = []
                # add this segment
                segments_list.append([item])
        
        # add last segments if exists
        if segments: segments_list.append(segments)

        return segments_list
                

    @property
    def is_stroke(self): return 's' in self.path_type

    @property
    def is_fill(self): return 'f' in self.path_type

    @property
    def is_iso_oriented(self):
        '''It is iso-oriented when all contained segments are iso-oriented.'''
        for segments in self.items:
            if not segments.is_iso_oriented: return False
        return True


    def to_shapes(self):
        """Convert path to ``Shape`` raw dicts.

        Returns:
            list: A list of ``Shape`` dict.
        """
        iso_shapes = []

        # convert to strokes
        if self.is_stroke:
            stroke_color = self.raw.get('color', None)
            width = self.raw.get('width', 0.0)
            iso_shapes.extend(self._to_strokes(width, stroke_color))

        # convert to rectangular fill
        if self.is_fill:
            fill_color = self.raw.get('fill', None)
            iso_shapes.extend(self._to_fills(fill_color))

        return iso_shapes


    def _to_strokes(self, width:float, color:list):
        '''Convert path to ``Stroke`` raw dicts.

        Returns:
            list: A list of ``Stroke`` dict.
        '''
        strokes = []        
        for segments in self.items:
            strokes.extend(segments.to_strokes(width, color))        
        return strokes


    def _to_fills(self, color:list):
        '''Convert path to ``Fill`` raw dicts.

        Returns:
            list: A list of ``Fill`` dict.
        
        .. note::
            The real filling area of this path may be not a rectangle.        
        '''
        fills = []        
        for segments in self.items:
            fills.append(segments.to_fill(color))        
        return fills


    def plot(self, canvas):
        ''' Plot path for debug purpose.

        Args:
            canvas: ``PyMuPDF`` drawing canvas by ``page.new_shape()``.

        Reference:
        
            https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings
        '''
        # draw each entry of the 'items' list
        for item in self.raw.get('items', []):
            if item[0] == "l":  # line
                canvas.draw_line(item[1], item[2])
            elif item[0] == "re":  # rectangle
                canvas.draw_rect(item[1])
            elif item[0] == "qu":  # quad
                canvas.draw_quad(item[1])
            elif item[0] == "c":  # curve
                canvas.draw_bezier(item[1], item[2], item[3], item[4])
            else:
                raise ValueError("unhandled drawing", item)

        # now apply the common properties to finish the path
        canvas.finish(
            fill=self.raw.get("fill", None),  # fill color
            color=self.raw.get("color", None),  # line color
            dashes=self.raw.get("dashes", None),  # line dashing
            even_odd=self.raw.get("even_odd", False),  # control color of overlaps
            closePath=self.raw.get("closePath", False),  # whether to connect last and first point
            lineJoin=self.raw.get("lineJoin", 0),  # how line joins should look like
            lineCap=max(self.raw["lineCap"]) if "lineCap" in self.raw else 0,  # how line ends should look like
            width=self.raw.get("width", 1),  # line width
            stroke_opacity=self.raw.get("stroke_opacity", 1),  # same value for both
            fill_opacity=self.raw.get("fill_opacity", 1)  # opacity parameters
            )