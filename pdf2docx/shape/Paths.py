# -*- coding: utf-8 -*-

'''
Objects representing PDF path (both stroke and filling) extracted by `page.getDrawings()`.
This method is new since PyMuPDF 1.18.0, with both pdf raw path and annotations  like Line, 
Square and Highlight considered.

- https://pymupdf.readthedocs.io/en/latest/page.html#Page.getDrawings
- https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings

@created: 2020-09-22
@author: train8808@gmail.com
'''


import fitz
from ..common.base import lazyproperty
from ..common import constants
from ..common.Collection import Collection
from ..common.utils import new_page
from ..image.Image import ImagesExtractor
from .Path import Path


class PathsExtractor:
    '''Extract paths from PDF.'''

    def __init__(self): self.paths = Paths()
    

    def extract_paths(self, page:fitz.Page):
        ''' Convert extracted paths to DICT attributes:
            - bitmap converted from vector graphics if necessary
            - iso-oriented paths
            
            NOTE: the target is to extract horizontal/vertical paths for table parsing, while others
            are converted to bitmaps.
        '''
        # get raw paths
        self.parse_page(page)

        # ignore vector graphics
        if constants.IGNORE_VEC_GRAPH: return [], self.paths.to_iso_paths()
        
        # group connected paths -> each group is a potential vector graphic
        from collections.abc import Iterable
        def flatten(items):
            """Yield items from any nested iterable; see REF."""
            for x in items:
                if isinstance(x, Iterable) and not isinstance(x, Paths):
                    yield from flatten(x)
                else:
                    yield x
        paths_list = self.paths.group_by_connectivity(dx=0.0, dy=0.0)
        num = 0
        while num!=len(paths_list)>0:
            num = len(paths_list)
            res = Collection(paths_list).group_by_connectivity(dx=0.0, dy=0.0)
            paths_list = []
            for paths_group in res:
                collection = Collection(list(flatten(paths_group)))                
                paths_list.append(collection)

        # convert vector graphics to bitmap
        iso_paths, pixmaps = [], []
        for collection in paths_list:
            combined_paths = Paths()
            for paths in collection: combined_paths.extend(list(paths))
            # print(combined_paths.curve_area/combined_paths.bbox.getArea())
            if combined_paths.contains_curve(0.2):
                image = combined_paths.to_image(page, constants.FACTOR_RES)
                if image: pixmaps.append(image)
            else:
                for paths in collection:                    
                    # can't be a table if curve path exists
                    if paths.contains_curve(0.2):
                        image = paths.to_image(page, constants.FACTOR_RES)
                        if image: pixmaps.append(image)
                    # keep potential table border paths
                    else:
                        iso_paths.extend(paths.to_iso_paths())

        return pixmaps, iso_paths

    
    def parse_page(self, page:fitz.Page):
        '''Extract paths from PDF page.'''
        # extract paths from pdf source: PyMuPDF >= 1.18.0
        # Currently no clip path considered, so may exist paths out of page, which is to be processed
        # after converting to real page CS (non-rotation page now). 
        raw_paths = page.getDrawings()

        # init Paths
        self.paths.reset([])
        for raw_path in raw_paths:
            path = Path(raw_path)
            # ignore path out of page
            if not path.bbox.intersects(page.rect): continue
            self.paths.append(path)

    
class Paths(Collection):
    '''A collection of paths.'''    
    @lazyproperty
    def bbox(self):
        bbox = fitz.Rect()
        for instance in self._instances: bbox |= instance.bbox
        return bbox


    @lazyproperty
    def curve_area(self):
        '''Sum of curve path area.'''
        curved_areas = [path.bbox.getArea() for path in self._instances if not path.is_iso_oriented]
        return sum(curved_areas) if curved_areas else 0.0


    def contains_curve(self, ratio:float):
        ''' Whether any curve paths exist. 
            The criterion: the area ratio of all non-iso-oriented paths >= `ratio`
        '''
        area = self.bbox.getArea()
        return self.curve_area/area >= ratio if area else False


    def append(self, path): self._instances.append(path)


    def extend(self, paths):
        for path in paths: self.append(path)


    def reset(self, paths:list): self._instances = paths


    def plot(self, doc:fitz.Document, title:str, width:float, height:float):
        if not self._instances: return
        # insert a new page
        page = new_page(doc, width, height, title)
        
        # make a drawing canvas and plot path
        canvas = page.newShape()
        for path in self._instances: path.plot(canvas)
        canvas.commit() # commit the drawing shapes to page


    def to_image(self, page:fitz.Page, zoom:float):
        '''Convert to image block dict.
            ---
            Args:
            - page: current pdf page
            - zoom: zoom in factor to improve resolution in x- abd y- direction
            - ratio: don't convert to image if the size of image exceeds this value,
            since we don't prefer converting the whole page to an image.
        '''
        # ignore images outside page
        if not self.bbox.intersects(page.rect): return None
        return ImagesExtractor.clip_page(page, self.bbox, zoom)
    

    def to_iso_paths(self):
        '''Convert contained paths to iso strokes and rectangular fills.'''
        paths = []
        for path in self._instances:
            # consider iso-oriented path only
            if not path.is_iso_oriented: continue
            paths.extend(path.to_shapes())
        return paths


