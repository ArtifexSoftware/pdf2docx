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
from ..common.Collection import  Collection
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


    def contains_curve(self, ratio:float):
        """Whether any curve paths exist with threshold considered. 

        **Criterion**: the ratio of non-iso-oriented paths to total count >= ``ratio``.

        Args:
            ratio (float): Threshold for non-iso-oriented paths.

        Returns:
            bool: Whether any curve paths exist.
        """
        if not self._instances: return False
        curve_paths = list(filter(lambda path: not path.is_iso_oriented, self._instances))
        return len(curve_paths)/len(self._instances) > ratio


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
    

    def _to_iso_paths(self):
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


    def to_shapes(self, curve_path_ratio:float=0.2):
        """Extract ISO-oriented (horizontal/vertical) paths for table parsing.

        Args:
            curve_path_ratio (float, optional): Not iso-oriented paths if exceed this ratio. Defaults to 0.2.

        Returns:
            tuple: (Shape raw dicts, shape bbox list, whether exists vector graphics).
        """
        # group connected paths -> each group is a potential vector graphic        
        paths_group = self.group_by_connectivity(dx=0.1, dy=0.1)

        iso_paths, iso_areas, exist_svg = [], [], False
        for paths in paths_group:
            # keep potential table border paths
            if paths.contains_curve(curve_path_ratio):
                exist_svg = True
            else:
                iso_paths.extend(paths._to_iso_paths())
                iso_areas.extend([path.bbox for path in paths])

        return iso_paths, iso_areas, exist_svg

