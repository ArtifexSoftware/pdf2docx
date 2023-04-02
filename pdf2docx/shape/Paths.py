# -*- coding: utf-8 -*-

'''
Objects representing PDF path (stroke and filling) extracted by ``page.get_drawings()``.

This method is new since ``PyMuPDF`` 1.18.0, with both pdf raw path and annotations like Line, 
Square and Highlight considered.

* https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_drawings
* https://pymupdf.readthedocs.io/en/latest/faq.html#extracting-drawings
'''

import fitz
from ..image.ImagesExtractor import ImagesExtractor
from ..common.share import lazyproperty
from ..common.Collection import  Collection
from .Path import Path


class Paths(Collection):
    '''A collection of paths.'''

    def restore(self, raws:list):
        '''Initialize paths from raw data get by ``page.get_drawings()``.'''
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


    @property
    def is_iso_oriented(self):
        '''It is iso-oriented when all contained segments are iso-oriented.'''
        for instance in self._instances:
            if not instance.is_iso_oriented: return False
        return True


    def plot(self, page):
        '''Plot paths for debug purpose.

        Args:
            page (fitz.Page): ``PyMuPDF`` page.
        '''
        if not self._instances: return
        # make a drawing canvas and plot path
        canvas = page.new_shape()
        for path in self._instances: path.plot(canvas)
        canvas.commit() # commit the drawing shapes to page
    

    def to_shapes(self):
        '''Convert contained paths to ISO strokes or rectangular fills.

        Returns:
            list: A list of ``Shape`` raw dicts.
        '''
        shapes = []
        for path in self._instances:
            # consider iso-oriented path only
            if not path.is_iso_oriented: continue
            shapes.extend(path.to_shapes())
        return shapes


    def to_shapes_and_images(self, min_svg_gap_dx:float=15, min_svg_gap_dy:float=15, 
                                min_w:float=2, min_h:float=2, clip_image_res_ratio:float=3.0):
        '''Convert paths to iso-oriented shapes or images. The semantic type of path is either table/text style or 
        vector graphic. This method is to:
        * detect svg regions -> exist at least one non-iso-oriented path
        * convert svg to bitmap by clipping page
        * convert the rest paths to iso-oriented shapes for further table/text style parsing

        Args:
            min_svg_gap_dx (float): Merge svg if the horizontal gap is less than this value.
            min_svg_gap_dy (float): Merge svg if the vertical gap is less than this value.
            min_w (float): Ignore contours if the bbox width is less than this value.
            min_h (float): Ignore contours if the bbox height is less than this value.
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            tuple: (list of shape raw dict, list of image raw dict).
        '''
        # convert all paths to shapes if no non-iso-orientated path exists
        iso_shapes = []
        if self.is_iso_oriented:
            iso_shapes.extend(self.to_shapes())
            return iso_shapes, []

        # detect svg with python opencv
        images = []
        ie = ImagesExtractor(self.parent.page_engine)
        groups = ie.detect_svg_contours(min_svg_gap_dx, min_svg_gap_dy, min_w, min_h)

        # `bbox` is the external bbox of current region, while `inner_bboxes` are the inner contours
        # of level-2 hierarchy, i.e. contours under table cell.
        # * it a table (or text style) if paths contained in `bbox` but excluded from `inner_bboxes` 
        #   are all iso-oriented -> export iso-shapes, clip page image based on `inner_bboxes`;
        # * otherwise, it's a vector graphic -> clip page image (without any text) based on `bbox`
        def contained_in_inner_contours(path:Path, contours:list):
            for bbox in contours:
                if fitz.Rect(bbox).contains(path.bbox): return True
            return False

        # group every path to one of the detected bbox
        group_paths = [Paths() for _ in groups] # type: list[Paths]
        for path in self._instances:
            for (bbox, inner_bboxes), paths in zip(groups, group_paths):            
                if path.bbox.intersects(bbox):
                    if not contained_in_inner_contours(path, inner_bboxes): paths.append(path)
                    break
        
        # check each group
        for (bbox, inner_bboxes), paths in zip(groups, group_paths): 
            # all iso-oriented paths -> it's a table, but might contain svg in cell as well
            if paths.is_iso_oriented:
                iso_shapes.extend(paths.to_shapes())
                for svg_bbox in inner_bboxes:
                    images.append(ie.clip_page_to_dict(fitz.Rect(svg_bbox), clip_image_res_ratio))
            
            # otherwise, it's a svg
            else:
                images.append(ie.clip_page_to_dict(fitz.Rect(bbox), clip_image_res_ratio))

        return iso_shapes, images

