# -*- coding: utf-8 -*-

'''
Objects representing PDF path (stroke and filling) extracted from pdf drawings and annotations.

Data structure based on results of ``page.getDrawings()``::

    {
        'color': (x,x,x) or None,  # stroke color
        'fill' : (x,x,x) or None,  # fill color
        'width': float,            # line width
        'closePath': bool,         # whether to connect last and first point
        'rect' : rect,             # page area covered by this path
        'items': [                 # list of draw commands: lines, rectangle or curves.
            ("l", p1, p2),         # a line from p1 to p2
            ("c", p1, p2, p3, p4), # cubic Bézier curve from p1 to p4, p2 and p3 are the control points
            ("re", rect),          # a rect
        ],
        ...
    }
'''

import fitz
from ..common.share import rgb_value


class Segment:
    '''A segment of path, e.g. a line or a rectangle or a curve.'''
    def __init__(self, item):
        self.points = item[1:]

    @property
    def is_iso_oriented(self): return False

    def to_strokes(self, width:float, color:list): return []   


class L(Segment):
    '''Line path with source ``("l", p1, p2)``.'''
    @property
    def is_iso_oriented(self):
        '''Whether horizontal or vertical line.'''
        x0, y0 = self.points[0]
        x1, y1 = self.points[1]
        return abs(x1-x0)<=1e-3 or abs(y1-y0)<=1e-3

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
                'start': tuple(self.points[0]),
                'end'  : tuple(self.points[1]),
                'width': width,
                'color': rgb_value(color)
            })
        return strokes


class R(Segment):
    '''Rect path with source ``("re", rect)``.'''
    def __init__(self, item):
        self.rect = item[1]

    @property
    def is_iso_oriented(self): return True

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
        # corner points
        # NOTE: center line of path without stroke width considered
        x0, y0, x1, y1 = self.rect
        points = [
            (x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)
            ]
        # connect each line
        strokes = []
        for i in range(len(points)-1):
            strokes.append({
                    'start': points[i],
                    'end'  : points[i+1],
                    'width': width * 2.0, # seems need adjustment by * 2.0
                    'color': rgb_value(color)
                })
        return strokes


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
        
        # close path
        if close_path and len(items)>=2:
            item = ('l', items[-1][-1], items[0][1])
            self._instances.append(L(item))

        # calculate bbox
        self.bbox = self.cal_bbox()

    
    def __iter__(self): return (instance for instance in self._instances)


    @property
    def is_iso_oriented_line(self): return bool(self.bbox) and not bool(self.bbox.getArea())


    def cal_bbox(self):
        '''Bbox of Segments. 
        
        .. note::
            For iso-oriented segments, ``bbox.getArea()==0``.
        '''
        # rectangle area
        if len(self._instances)==1 and isinstance(self._instances[0], R):
            return self._instances[0].rect
        
        # calculate bbox of lines and curves area
        points = []
        for segment in self._instances: points.extend(segment.points)
        x0 = min(points, key=lambda point: point[0])[0]
        y0 = min(points, key=lambda point: point[1])[1]
        x1 = max(points, key=lambda point: point[0])[0]
        y1 = max(points, key=lambda point: point[1])[1]
        return fitz.Rect(x0, y0, x1, y1)


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
        '''Init path in un-rotated page CS.'''
        # all path properties
        self.raw = raw

        # path segments
        self.items = [] # type: list[Segments]
        self.bbox = fitz.Rect()
        close_path, w = raw['closePath'], raw['width']
        for segments in self._group_segments(raw['items']):
            S = Segments(segments, close_path)
            self.items.append(S)

            # update bbox: note iso-oriented line segments, e.g. S.bbox.getArea()==0
            rect = S.bbox
            if S.is_iso_oriented_line: rect += (-w, -w, w, w)
            self.bbox |= rect


    @staticmethod
    def _group_segments(items):
        """Group connected segments.

        Args:
            items (dict): Raw dict extracted from ``page.getDrawings()``.

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

            # rectangle as a separate segments group
            elif item[0] == 're':
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
    def is_stroke(self): self.raw.get('color', None) is not None

    @property
    def is_fill(self): self.raw.get('fill', None) is not None

    @property
    def is_iso_oriented(self):
        '''It is iso-oriented on condition that:

        * All Lines are iso-oriented, and
        * the count of iso-oriented Lines is larger than Curves
        '''
        line_cnt, curve_cnt = 0, 0
        for segments in self.items:
            for segment in segments:
                if isinstance(segment, C): curve_cnt += 1
                elif isinstance(segment, R): line_cnt += 1
                elif segment.is_iso_oriented: line_cnt += 1
                else: return False
        return line_cnt >= curve_cnt


    def to_shapes(self):
        """Convert path to ``Shape`` raw dicts.

        Returns:
            list: A list of ``Shape`` dict.
        """        
        stroke_color = self.raw.get('color', None)
        fill_color = self.raw.get('fill', None)
        width = self.raw.get('width', 0.0)

        iso_shapes = []

        # convert to strokes
        if not stroke_color is None:
            iso_shapes.extend(self.to_strokes(width, stroke_color))

        # convert to rectangular fill
        if not fill_color is None:
            iso_shapes.extend(self.to_fills(fill_color))

        return iso_shapes


    def to_strokes(self, width:float, color:list):
        '''Convert path to ``Stroke`` raw dicts.

        Returns:
            list: A list of ``Stroke`` dict.
        '''
        strokes = []        
        for segments in self.items:
            strokes.extend(segments.to_strokes(width, color))        
        return strokes


    def to_fills(self, color:list):
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
            canvas: ``PyMuPDF`` drawing canvas by ``page.newShape()``.

        Reference:
        
            https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings
        '''
        # draw each entry of the 'items' list
        for item in self.raw.get('items', []):
            if item[0] == "l":  # line
                canvas.drawLine(item[1], item[2])
            elif item[0] == "re":  # rectangle
                canvas.drawRect(item[1])
            elif item[0] == "c":  # curve
                canvas.drawBezier(item[1], item[2], item[3], item[4])

        # now apply the common properties to finish the path
        canvas.finish(
            fill=self.raw.get("fill", None),  # fill color
            color=self.raw.get("color", None),  # line color
            dashes=self.raw.get("dashes", None),  # line dashing
            even_odd=self.raw.get("even_odd", False),  # control color of overlaps
            closePath=self.raw.get("closePath", True),  # whether to connect last and first point
            lineJoin=self.raw.get("lineJoin", 0),  # how line joins should look like
            lineCap=max(self.raw["lineCap"]) if "lineCap" in self.raw else 0,  # how line ends should look like
            width=self.raw.get("width", 1),  # line width
            stroke_opacity=self.raw.get("opacity", 1),  # same value for both
            fill_opacity=self.raw.get("opacity", 1)  # opacity parameters
            )