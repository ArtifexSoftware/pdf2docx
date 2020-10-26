# -*- coding: utf-8 -*-

'''
Objects representing PDF path (both stroke and filling) parsed from both pdf raw streams and annotations.

@created: 2020-09-22
@author: train8808@gmail.com
---

Data structure based on results of `page.getDrawings()`:
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

from ..common.utils import RGB_value


class L:
    '''Line path with source ("l", p1, p2)'''
    def __init__(self, item):
        self.p1, self.p2 = item[1:]    

    @property
    def is_iso_oriented(self):
        x0, y0 = self.p1
        x1, y1 = self.p2
        return abs(x1-x0)<=1e-3 or abs(y1-y0)<=1e-3

    def to_strokes(self, width:float, color:list):
        strokes = []
        strokes.append({
                'start': tuple(self.p1),
                'end'  : tuple(self.p2),
                'width': width,
                'color': RGB_value(color)
            })
        return strokes

class R:
    '''Rect path with source ("re", rect)'''
    def __init__(self, item):
        self.rect = item[1]

    @property
    def is_iso_oriented(self): return True

    def to_strokes(self, width:float, color:list):
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
                    'color': RGB_value(color)
                })
        return strokes
    

class C:
    '''Bezier curve path with source ("c", p1, p2, p3, p4)'''
    def __init__(self, item):
        self.p1, self.p2, self.p3, self.p4 = item[1:]
    
    @property
    def is_iso_oriented(self): return False

    def to_strokes(self, width:float, color:list):
        '''Curve path doesn't contribute to table parsing.'''
        return None   


class Path:
    '''Path extracted from PDF, either/both a stroke or/and a filling.'''

    def __init__(self, raw:dict=None):
        '''Init path in un-rotated page CS.'''
        # all path properties
        self.raw = raw if raw else {}

        # path area
        self.bbox = self.raw['rect']

        # command list
        self.items = [] # type: list[L or R or C]
        for item in self.raw['items']:
            if item[0] == 'l':
                self.items.append(L(item))
            elif item[0] == 're':
                self.items.append(R(item))
            elif item[0] == 'c':
                self.items.append(C(item))


    @property
    def is_stroke(self): self.raw.get('color', None) is not None

    @property
    def is_fill(self): self.raw.get('fill', None) is not None

    @property
    def is_iso_oriented(self):
        for item in self.items:
            if not item.is_iso_oriented: return False
        return True


    def to_shapes(self):
        ''' Convert path to shapes: stroke or fill.'''
        stroke_color = self.raw.get('color', None)
        fill_color = self.raw.get('fill', None)
        width = self.raw.get('width', 0.0)

        iso_shapes = []

        # convert to strokes
        if not stroke_color is None:
            iso_shapes.extend(self.to_strokes(width, stroke_color))

        # convert to rectangular fill
        if not fill_color is None:
            iso_shapes.append(self.to_fill(fill_color))

        return iso_shapes


    def to_strokes(self, width:float, color:list):
        '''Convert path segments to strokes.'''
        strokes = []        
        for segment in self.items:
            strokes.extend(segment.to_strokes(width, color))        
        return strokes


    def to_fill(self, color:list):
        '''Convert fill path to rectangular bbox, though the real filling area is not a rectangle.'''
        return {
            'bbox': list(self.bbox), 
            'color': RGB_value(color)
        }


    def plot(self, canvas):
        ''' Plot path https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings
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