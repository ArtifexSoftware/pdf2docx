# -*- coding: utf-8 -*-

'''
Objects representing PDF path (both stroke and filling) parsed from both pdf raw streams and annotations.

@created: 2020-09-22
@author: train8808@gmail.com
---

Paths are created based on DICT data extracted from `pdf2docx.common.pdf` module:
- Stroke path:
    {
        'stroke': True,
        'curve' : is_curve, # whether curve path segments exists
        'points': t_path,
        'color' : color,
        'width' : w
    }
- Fill path:
    {
        'stroke': False,
        'curve' : is_curve, # whether curve path segments exists
        'points': t_path,
        'color' : color
    }
'''

import fitz
from ..common import pdf
from ..common.Collection import BaseCollection
from ..common.rect_intersection import solve_rects_intersection
from ..common.utils import RGB_component, graph_BFS


class PathsExtractor(BaseCollection):
    '''A collection of paths extracted from PDF.'''

    def parse(self, page:fitz.Page):
        '''Extract paths from PDF page.'''

        # paths from pdf source
        raw_paths = pdf.paths_from_stream(page)

        # paths from pdf annotation
        _ = pdf.paths_from_annotations(page)
        raw_paths.extend(_)

        self._instances = [] # type: list[Path]
        for raw_path in raw_paths:
            path = Path(raw_path)
            self._instances.append(path)

        return self

    @property
    def bbox(self):
        bbox = fitz.Rect()
        for instance in self._instances:
            bbox = bbox | instance.bbox # NOTE: | support fitz.Rect and rect-like object, e.g. tuple
        return bbox

    
    def group(self):
        ''' Collect connected path into same group.

            NOTE:
            - It's equal to a GRAPH traversing problem, which the critical point in building the adjacent
            list, especially a large number of vertex (paths).
            - Checking intersections between paths is actually a Rectangle-Intersection problem, studied
            already in many literatures.
        '''
        # build the graph -> adjacent list:
        # the i-th item is a set of indexes, which connected to the i-th instance
        num = len(self._instances)
        index_groups = [set() for _ in range(num)] # type: list[set]

        # solve rectangle intersection problem
        i_rect_x = []
        i = 0
        for rect in self._instances:
            i_rect_x.append((i, rect, rect.x0))
            i_rect_x.append((i+1, rect, rect.x1))
            i += 2
        i_rect_x.sort(key=lambda item: item[-1])
        solve_rects_intersection(i_rect_x, 2*num, index_groups)

        # traverse the graph
        counted_indexes = set() # type: set[int]
        groups = []
        for i in range(num):
            # skip if counted
            if i in counted_indexes: continue

            # a connected component of graph
            indexes = set(graph_BFS(index_groups, i))
            group = PathsExtractor([self._instances[x] for x in indexes])
            groups.append(group)

            # update counted indexes
            counted_indexes = counted_indexes | indexes

        return groups
    

    def filter_pixmaps(self, page:fitz.Page):
        ''' Convert vector graphics built by paths to pixmap.
            
            NOTE: the target is to extract horizontal/vertical paths for table parsing, while others
            are converted to bitmaps.
        '''
        # group connected paths -> each group is a potential pixmap
        groups = self.group()

        # Generally, a table region is composed of orthogonal paths, i.e. either horizontal or vertical paths.
        # Suppose it can't be a table if the count of non-orthogonal paths is larger than NUM=5.
        orth_instances, pixmaps = [], []
        NUM = 5 
        for group in groups:
            cnt = 0
            for path in group:
                if not path.is_orthogonal: cnt += 1
                if cnt >= NUM: 
                    # convert to pixmap
                    pixmaps.append(group.to_image(page))
                    break
            
            # keep potential table border paths
            else:
                orth_instances.extend(group.to_paths())

        return pixmaps, orth_instances

    
    def to_image(self, page:fitz.Page):
        '''Convert to image block dict if this is a vector graphic paths.'''
        bbox = self.bbox
        image = page.getPixmap(clip=bbox)
        return {
            'type': 1,
            'bbox': tuple(bbox),
            'ext': 'png',
            'width': bbox.width,
            'height': bbox.height,
            'image': image.getImageData(output="png")
        }
    

    def to_paths(self):
        '''Convert contained paths to orthogonal strokes and rectangular fills.'''
        paths = []
        for path in self._instances:
            if path.stroke:
                paths.extend(path.to_orthogonal_strokes())
            else:
                paths.append(path.to_rectangular_fill())

        return paths


    def plot(self, doc:fitz.Document, title:str, width:float, height:float):
        # insert a new page
        page = pdf.new_page_with_margin(doc, width, height, None, title)
        for path in self._instances: path.plot(page)



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

        self.bbox = self.fun_bbox()
        self.x0, self.y0, self.x1, self.y1 = self.bbox
    

    def fun_bbox(self):
        '''Boundary box in PyMuPDF page CS (without rotation).'''
        # if self._bbox is None:
        X = [p[0] for p in self.points]
        Y = [p[1] for p in self.points]
        x0, x1 = min(X), max(X)
        y0, y1 = min(Y), max(Y)

        h = self.width / 2.0
        # NOTE: use tuple here has a much higher efficiency than fizt.Rect()
        bbox = (x0-h, y0-h, x1+h, y1+h) if self.stroke else (x0, y0, x1, y1)
        
        return bbox


    @property
    def is_orthogonal(self):
        '''Whether contains horizontal/vertical path segments only.'''
        for i in range(len(self.points)-1):
            # start point
            x0, y0 = self.points[i]
            # end point
            x1, y1 = self.points[i+1]

            if x0!=x1 and y0!=y1: return False
        
        return True


    def to_orthogonal_strokes(self):
        ''' Convert stroke path to line segments. 

            NOTE: Consider horizontal or vertical lines only since such lines contribute to 
            parsing table borders, text underlines.
        '''
        strokes = []
        for i in range(len(self.points)-1):
            # start point
            x0, y0 = self.points[i]
            # end point
            x1, y1 = self.points[i+1]

            if x0!=x1 and y0!=y1: continue

            strokes.append({
                'start': (x0, y0),
                'end'  : (x1, y1),
                'width': self.width,
                'color': self.color
            })
        
        return strokes


    def to_rectangular_fill(self):
        '''Convert fill path to rectangular bbox, thought the real filling area is not a rectangle.'''
        return {
            'bbox': list(self.bbox), 
            'color': self.color
        }


    def plot(self, page):
        color = [c/255.0 for c in RGB_component(self.color)]
        fill_color = None if self.stroke else color
        page.drawPolyline(self.points, color=color, fill=fill_color, width=self.width, overlay=True)