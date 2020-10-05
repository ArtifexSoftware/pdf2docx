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
from ..common.utils import RGB_component, get_main_bbox
from ..image.Image import ImagesExtractor

class PathsExtractor:
    '''Extract paths from PDF.'''

    def __init__(self): self.paths = Paths()
    

    def extract_paths(self, page:fitz.Page):
        ''' Convert extracted paths to DICT attributes:
            - bitmap converted from vector graphics
            - iso-oriented paths
            
            NOTE: the target is to extract horizontal/vertical paths for table parsing, while others
            are converted to bitmaps.
        '''
        # get raw paths
        self._parse_page(page)

        # group connected paths -> each group is a potential vector graphic
        paths_list = self.paths.group_by_connectivity()

        # ignore anything covered by vector graphic, so group paths further
        fun = lambda a,b: get_main_bbox(a.bbox, b.bbox, 0.99)
        paths_group_list = BaseCollection(paths_list).group(fun)

        iso_paths, pixmaps = [], []
        for paths_group in paths_group_list:
            largest = max(paths_group, key=lambda paths: paths.bbox.getArea())
            image = largest.to_image(page) if largest.contains_curve else None

            # ignore anything behind vector graphic
            if image:
                pixmaps.append(image)
                continue

            # otherwise, add each paths
            for paths in paths_group:
                # can't be a table if curve path exists
                if paths.contains_curve:
                    image = paths.to_image(page)
                    if image: pixmaps.append(image)
                # keep potential table border paths
                else:
                    iso_paths.extend(paths.to_iso_paths())

        return pixmaps, iso_paths

    
    def _parse_page(self, page:fitz.Page):
        '''Extract paths from PDF page.'''
        # paths from pdf source
        raw_paths = pdf.paths_from_stream(page)

        # paths from pdf annotation
        _ = pdf.paths_from_annotations(page)
        raw_paths.extend(_)

        # init Paths
        instances = [Path(raw_path) for raw_path in raw_paths]
        self.paths.reset(instances)
    
    
class Paths(BaseCollection):
    '''A collection of paths.'''
    
    @property
    def bbox(self):
        if not hasattr(self, '_bbox'):
            bbox = fitz.Rect()
            for instance in self._instances: bbox = bbox | instance.bbox
            self._bbox = bbox
        return self._bbox
    
    @property
    def contains_curve(self, num=5):
        '''Whether any curve paths exist. The criterion is the count of non-iso-oriented paths.'''
        cnt = 0
        for path in self._instances:
            if not path.is_iso_oriented: cnt += 1
            if cnt >= num: return True        
        return False
    
    def append(self, path): self._instances.append(path)

    def reset(self, paths:list=[]): self._instances = paths

    def plot(self, doc:fitz.Document, title:str, width:float, height:float):
        if not self._instances: return
        # insert a new page
        page = pdf.new_page_with_margin(doc, width, height, None, title)
        for path in self._instances: path.plot(page)    

    
    def to_image(self, page:fitz.Page, zoom:float=3.0, ratio:float=0.95):
        '''Convert to image block dict.
            ---
            Args:
            - page: current pdf page
            - zoom: zoom in factor to improve resolution in x- abd y- direction
            - ratio: don't convert to image if the size of image exceeds this value,
            since we don't prefer converting the whole page to an image.
        '''
        bbox = self.bbox

        # NOTE: the image size shouldn't exceed a limitation.
        if bbox.getArea()/page.rect.getArea()>=ratio: return None
        
        return ImagesExtractor.clip_page(page, bbox, zoom)
    

    def to_iso_paths(self):
        '''Convert contained paths to iso strokes and rectangular fills.'''
        paths = []
        for path in self._instances:
            if path.stroke:
                paths.extend(path.to_iso_strokes())
            else:
                paths.append(path.to_rectangular_fill())

        return paths


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
    

    def fun_bbox(self):
        '''Boundary box in PyMuPDF page CS (without rotation).'''
        # if self._bbox is None:
        X = [p[0] for p in self.points]
        Y = [p[1] for p in self.points]
        x0, x1 = min(X), max(X)
        y0, y1 = min(Y), max(Y)

        h = self.width / 2.0
        # NOTE: use tuple here has a much higher efficiency than fizt.Rect()
        bbox = fitz.Rect(x0-h, y0-h, x1+h, y1+h) if self.stroke else fitz.Rect(x0, y0, x1, y1)
        
        return bbox


    @property
    def is_iso_oriented(self):
        '''Whether contains horizontal/vertical path segments only.'''
        for i in range(len(self.points)-1):
            # start point
            x0, y0 = self.points[i]
            # end point
            x1, y1 = self.points[i+1]

            if x0!=x1 and y0!=y1: return False
        
        return True


    def to_iso_strokes(self):
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