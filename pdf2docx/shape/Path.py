# -*- coding: utf-8 -*-

'''
Objects representing PDF path (both stroke and filling) parsed from both pdf raw streams and annotations.

@created: 2020-09-22
@author: train8808@gmail.com
---
'''

import fitz
from ..common.utils import RGB_component
from ..common import pdf


class PathsExtractor:
    '''Extract paths from PDF.'''
    def __init__(self, doc:fitz.Document, page:fitz.Page):

        # paths from pdf source
        raw_paths = pdf.paths_from_stream(doc, page)

        # paths from pdf annotation
        # _ = pdf.paths_from_annotations(page)
        # raw_paths.extend(_)

        self._instances = [] # type: list[Path]
        for raw_path in raw_paths:
            path = Path(raw_path)
            self._instances.append(path)


    def __len__(self): return len(self._instances)


    def plot(self, doc:fitz.Document, title:str, width, height):
        # insert a new page
        page = pdf.new_page_with_margin(doc, width, height, None, title)
        for path in self._instances: path.plot(page)
    

    def store(self):
        paths = []
        for path in self._instances:
            if path.stroke:
                paths.extend(path.to_strokes())
            else:
                paths.append(path.to_fill())

        return { 'paths': paths }


class Path:
    '''Path extracted from PDF, either a stroke or filling.'''
    def __init__(self, raw:dict={}):
        '''Init path in un-rotated page CS.'''
        self.points = []
        for x,y in raw.get('points', []): # [(x0,y0), (x1, y1)]
            self.points.append((x,y))

        # stroke (by default) or fill path
        self.stroke = raw.get('stroke', True)

        # stroke/fill color
        self.color = raw.get('color', 0)

        # width if stroke
        self.width = raw.get('width', 0.0)


    def to_strokes(self):
        '''Convert stroke path to line segments.'''
        strokes = []
        for i in range(len(self.points)-1):
            # start point
            x0, y0 = self.points[i]
            # end point
            x1, y1 = self.points[i+1]        

            strokes.append({
                'start': (x0, y0),
                'end'  : (x1, y1),
                'width': self.width,
                'color': self.color
            })
        
        return strokes


    def to_fill(self):
        '''Convert fill path to rectangular bbox.'''
        # find bbox of path region
        X = [p[0] for p in self.points]
        Y = [p[1] for p in self.points]
        x0, x1 = min(X), max(X)
        y0, y1 = min(Y), max(Y)

        # filled bbox, thought the real filling area is not a rectangle
        return {
            'bbox': (x0, y0, x1, y1), 
            'color': self.color
        }


    def plot(self, page):
        color = [c/255.0 for c in RGB_component(self.color)]
        page.drawPolyline(self.points, color=color, fill=not self.stroke, width=self.width, overlay=True)