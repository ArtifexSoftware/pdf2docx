# -*- coding: utf-8 -*-

'''
Objects representing PDF path (stroke and filling) extracted by ``page.getDrawings()``.

This method is new since ``PyMuPDF`` 1.18.0, with both pdf raw path and annotations like Line, 
Square and Highlight considered.

* https://pymupdf.readthedocs.io/en/latest/page.html#Page.getDrawings
* https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings
'''


import fitz
from ..common.share import lazyproperty
from ..common.Collection import BaseCollection, Collection
from ..common.share import flatten
from ..image.Image import ImagesExtractor
from .Path import Path


class Paths(Collection):
    '''A collection of paths.'''

    def restore(self, raws:list):
        '''Initialize paths from raw data get by ``page.getDrawings()``.'''
        rect = (0, 0, self.parent.width, self.parent.height)
        for raw in raws:
            path = Path(raw)
            # ignore path out of page
            if not path.bbox.intersects(rect): continue
            self.append(path)
        
        return self
    
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
        """Whether any curve paths exist with threshold considered. 

        **Criterion**: the area ratio of all non-iso-oriented paths >= ``ratio``

        Args:
            ratio (float): Threshold for non-iso-oriented paths.

        Returns:
            bool: Whether any curve paths exist.
        """
        area = self.bbox.getArea()
        return self.curve_area/area >= ratio if area else False


    def append(self, path): self._instances.append(path)


    def extend(self, paths):
        for path in paths: self.append(path)


    def group(self):
        '''Group paths by connectivity on two level:

        * connected paths -> basic unit for figure or sub-area of a figure
        * connected paths groups -> figure(s) in a clipping area

        Examples::

                +----------+
                |    A     |  A+B, C  -> connected paths
                +------+---+
                       |   |
            +--------+ | B |  (A+B)+C -> connected paths group
            |   C    | |   |
            +--------+ +---+
        '''
        num = 0 # count of final connected groups
        paths_groups = self.group_by_connectivity(dx=0.0, dy=0.0)

        # check connectivity until no intersections exist in any two groups
        while num!=len(paths_groups)>0:
            num = len(paths_groups)
            res = BaseCollection(paths_groups).group_by_connectivity(dx=0.0, dy=0.0)
            paths_groups = []
            for paths_group in res:
                collection = BaseCollection(list(flatten(paths_group, Paths))) # ensure basic unit: Paths
                paths_groups.append(collection)

        return paths_groups


    def plot(self, page):
        """Plot paths for debug purpose.

        Args:
            page (fitz.Page): ``PyMuPDF`` page.
        """
        if not self._instances: return
        # make a drawing canvas and plot path
        canvas = page.newShape()
        for path in self._instances: path.plot(canvas)
        canvas.commit() # commit the drawing shapes to page


    def to_image(self, page:fitz.Page, zoom:float):
        """Convert to image block dict by clipping page.

        Args:
            page (fitz.Page): Current pdf page.
            zoom (float): Zoom in factor to improve resolution in both x- and y- direction.

        Returns:
            dict: Raw dict of image.
        """ 
        # ignore images outside page
        if not self.bbox.intersects(page.rect): return None
        return ImagesExtractor.clip_page(page, self.bbox, zoom)
    

    def to_iso_paths(self):
        """Convert contained paths to ISO strokes and rectangular fills.

        Returns:
            list: A list of ``Shape`` raw dicts.

        .. note::
            Non-ISO path is ignored.
        """
        paths = []
        for path in self._instances:
            # consider iso-oriented path only
            if not path.is_iso_oriented: continue
            paths.extend(path.to_shapes())
        return paths


    def to_images_and_shapes(self, page:fitz.Page, 
            curve_path_ratio:float=0.2,    # 
            clip_image_res_ratio:float=3.0 # 
            ):
        """Convert paths to raw dicts.

        * Only ISO-oriented paths are considered.
        * Clip a page bitmap when some paths 'look like' a vector graphic, i.e. curved paths exceed the threshold.

        Args:
            page (fitz.Page): pdf page.
            curve_path_ratio (float, optional): Clip page bitmap if curve paths exceed this ratio. Defaults to 0.2.
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            tuple: (a list of images raw dicts, a list of Shape raw dicts)
        
        .. note::
            The target is to extract horizontal/vertical paths for table parsing, while others
            are converted to bitmaps.
        """
        # group connected paths -> each group is a potential vector graphic        
        paths_groups = self.group()

        # convert vector graphics to bitmap
        iso_paths, pixmaps = [], []
        for collection in paths_groups:
            # a collection of paths groups:
            # clip page bitmap if it seems a vector graphic
            combined_paths = Paths()
            for paths in collection: combined_paths.extend(list(paths))            
            if combined_paths.contains_curve(curve_path_ratio):
                image = combined_paths.to_image(page, clip_image_res_ratio)
                if image: pixmaps.append(image)
                continue
            
            # otherwise, check each paths in group
            for paths in collection:                    
                # can't be a table if curve path exists
                if paths.contains_curve(curve_path_ratio):
                    image = paths.to_image(page, clip_image_res_ratio)
                    if image: pixmaps.append(image)
                # keep potential table border paths
                else:
                    iso_paths.extend(paths.to_iso_paths())

        return pixmaps, iso_paths

