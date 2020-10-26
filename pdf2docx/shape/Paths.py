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
from ..common.Collection import BaseCollection
from ..common.utils import new_page
from ..common.BBox import BBox
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

        # ------------------------------------------------------------
        # ignore vector graphics
        # ------------------------------------------------------------
        if constants.IGNORE_VEC_GRAPH:
            iso_paths = self.paths.to_iso_paths()
            return [], iso_paths

        # ------------------------------------------------------------
        # convert vector graphics to bitmap
        # ------------------------------------------------------------ 
        # group connected paths -> each group is a potential vector graphic
        paths_list = self.paths.group_by_connectivity(dx=0.0, dy=0.0)

        # ignore anything covered by vector graphic, so group paths further
        fun = lambda a,b: BBox().update_bbox(a.bbox).get_main_bbox(b, constants.FACTOR_SAME)
        paths_group_list = BaseCollection(paths_list).group(fun)

        iso_paths, pixmaps = [], []
        for paths_group in paths_group_list:
            largest = max(paths_group, key=lambda paths: paths.bbox.getArea()) # type: Paths
            if largest.contains_curve(constants.FACTOR_A_FEW):
                image = largest.to_image(page, constants.FACTOR_RES, constants.FACTOR_ALMOST)
            else:
                image = None

            # ignore anything under vector graphic
            if image:
                pixmaps.append(image)
                continue

            # otherwise, add each paths
            for paths in paths_group:
                # can't be a table if curve path exists
                if paths.contains_curve(constants.FACTOR_A_FEW):
                    image = paths.to_image(page, constants.FACTOR_RES, constants.FACTOR_ALMOST)
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
            if path.bbox and not path.bbox.intersects(page.rect): continue
            self.paths.append(path)

    
class Paths(BaseCollection):
    '''A collection of paths.'''    
    @lazyproperty
    def bbox(self):
        bbox = fitz.Rect()
        for instance in self._instances: bbox |= instance.bbox
        return bbox
    
    def contains_curve(self, ratio:float):
        ''' Whether any curve paths exist. 
            The criterion: the area ratio of all non-iso-oriented paths >= `ratio`
        '''
        if not self.bbox.getArea(): return False

        bbox = fitz.Rect()
        for path in self._instances:            
            if not path.is_iso_oriented: bbox |= path.bbox
        return bbox.getArea()/self.bbox.getArea() >= ratio


    def append(self, path): self._instances.append(path)


    def reset(self, paths:list): self._instances = paths


    def plot(self, doc:fitz.Document, title:str, width:float, height:float):
        if not self._instances: return
        # insert a new page
        page = new_page(doc, width, height, title)
        
        # make a drawing canvas and plot path
        canvas = page.newShape()
        for path in self._instances: path.plot(canvas)
        canvas.commit() # commit the drawing shapes to page


    def to_image(self, page:fitz.Page, zoom:float, ratio:float):
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

        # NOTE: the image size shouldn't exceed a limitation.
        # if self.bbox.getArea()/page.rect.getArea()>=ratio: return None

        return ImagesExtractor.clip_page(page, self.bbox, zoom)
    

    def to_iso_paths(self):
        '''Convert contained paths to iso strokes and rectangular fills.'''
        paths = []
        for path in self._instances:
            # consider iso-oriented path only
            if not path.is_iso_oriented: continue
            paths.extend(path.to_shapes())
        return paths


