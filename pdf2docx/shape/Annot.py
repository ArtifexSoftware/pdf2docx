# -*- coding: utf-8 -*-

'''
Get path from PDF Annotations:
- https://pymupdf.readthedocs.io/en/latest/annot.html
- https://pymupdf.readthedocs.io/en/latest/vars.html#annotation-types

@created: 2020-10-26
@author: train8808@gmail.com
'''

import fitz


class Annot:
    '''A wrapper of fitz.Annot targeting to convert Annotation to paths.'''

    def __init__(self, annot):
        # annot type, e.g. (8, 'Highlight')
        self.type = annot.type[0] 

        # color, e.g. {'stroke': [1.0, 1.0, 0.0], 'fill': []}
        c = annot.colors
        self.color = c['stroke'] if c['stroke'] else None
        self.fill  = c['fill'] if c['fill'] else None

        # width
        w = annot.border.get('width', 1.0)
        self.width = w if w!=-1 else 0.0

        # annotation bbox
        self.rect = annot.rect

        # vertices, useful when annot span cross multi-lines
        self.vertices = annot.vertices


    def to_paths(self):
        ''' Convert annot (only in following types) to paths considering the contributions 
            to text format and table border.
            - PDF_ANNOT_LINE 3
            - PDF_ANNOT_SQUARE 4
            - PDF_ANNOT_HIGHLIGHT 8
            - PDF_ANNOT_UNDERLINE 9
            - PDF_ANNOT_STRIKEOUT 11
        '''
        paths = []

        if self.type == 3: # Line
            paths.append(self.line_to_path())
        
        elif self.type == 4: # Square
            paths.append(self.square_to_path())
        
        elif self.type == 8: # highlight
            paths.extend(self.highlight_to_paths())

        elif self.type == 9: # underline
            paths.extend(self.underline_to_paths())

        elif self.type == 11: # strikethrough
            paths.extend(self.striketout_to_paths())

        return paths
    

    def line_to_path(self):
        '''Convert Line to a path (stroke).
           Annotation Line: a space of 1.5*w around each border
           ```
           +----------------------------+ <- rect
           |         space              |
           |     +--------------+       |
           |     |   border     | 1.5w  |
           |     +--------------+       |
           |         1.5w               |
           +----------------------------+
           ```
        '''
        x0, y0, x1, y1 = self.rect
        w = self.width
        
        if x1-x0 >= y1-y0: # horizontal line
            u0 = x0+1.5*w
            u1 = x1-1.5*w
            v0 = v1 = (y0+y1)/2.0
        else:
            v0 = y0+1.5*w
            v1 = y1-1.5*w
            u0 = u1 = (x0+x1)/2.0
        
        return self.L((u0, v0), (u1, v1))
    

    def square_to_path(self):
        '''Convert Square to a path (stroke and fill).
           Square: a space of 0.5*w around eah border
           ```
           +------------------------------------------+
           |                space                     |
           |      +----------------------------+      |
           |      |         border             |      |
           |      |     +--------------+       |      |
           |            |     fill     |  w    | 0.5w |
           |      |     +--------------+       |      |
           |      |            w               |      |
           |      +----------------------------+      |
           |                  0.5w                    |
           +------------------------------------------+
           ```
        '''
        x0, y0, x1, y1 = self.rect
        w = self.width

        # rectangles with corner points located in the center of border
        u0, v0 = x0+w, y0+w
        u1, v1 = x1-w, y1-w

        return self.Re((u0,v0), (u1,v1))
    

    def highlight_to_paths(self):
        '''Convert highlight to paths. 

           NOTE: A highlight may spread cross multi-rows, so `annot.rect` is a combination of all sub-highlights.
           ```
                    +------------------------+
                    +------------------------+
           +-----------+
           +-----------+
           ```
           NOTE: Though underline and strikethrough are just lines, the affected areas are same as
           highlights, as illustrated above.
           
           https://github.com/pymupdf/PyMuPDF/issues/318
        '''
        # NOTE: this indeed a stroke for PyMuPDF -> no fill color but stroke color !!
        self.color, self.fill = self.fill, self.color

        # use annot.vertices to consider each sub-highlights
        paths = []
        points = self.vertices
        for i in range(int(len(points)/4.0)): # four points in a group
            # top-left, bottom-right points
            x0, y0 = points[4*i]
            x1, y1 = points[4*i+3]
            paths.append(self.Re((x0,y0), (x1,y1)))
        
        return paths


    def underline_to_paths(self):
        '''Convert underline to paths. Refer to highlight.'''
        # NOTE: this indeed a stroke for PyMuPDF -> no fill color but stroke color !!
        self.color, self.fill = self.fill, self.color

        # use annot.vertices to consider each sub-highlights
        paths = []
        points = self.vertices
        for i in range(int(len(points)/4.0)): # four points in a group 
            # two points at bottom edge
            start, end = points[4*i+2], points[4*i+3]
            paths.append(self.L(start, end))
        
        return paths


    def striketout_to_paths(self):
        '''Convert striketout to paths. Refer to highlight.'''
        # NOTE: this indeed a stroke for PyMuPDF -> no fill color but stroke color !!
        self.color, self.fill = self.fill, self.color

        # use annot.vertices to consider each sub-highlights
        paths = []
        points = self.vertices
        for i in range(int(len(points)/4.0)): # four points in a group 
            # average of top and bottom edge
            x0, x1 = points[4*i][0], points[4*i+1][0]
            y_ = (points[4*i][1]+points[4*i+2][1])/2.0
            start = x0, y_
            end = x1, y_
            paths.append(self.L(start, end))
        
        return paths
    

    def L(self, start:tuple, end:tuple):
        '''command item for a line.'''
        return {
            'color': self.color,
            'fill' : self.fill,
            'width': self.width,
            'items': [ ['l', start, end] ],
            'rect': fitz.Rect(*start, *end)
        }
    

    def Re(self, start:tuple, end:tuple):
        '''command item for a line.'''
        rect = fitz.Rect(*start, *end)
        return {
            'color': self.color,
            'fill' : self.fill,
            'width': self.width,
            'items': [ ['re', rect] ],
            'rect': rect
        }