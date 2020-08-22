# -*- coding: utf-8 -*-

'''
A group of Rectangle instances focusing on table parsing process.

@created: 2020-07-22
@author: train8808@gmail.com
'''

from .Rectangle import Rectangle
from ..common.base import RectType
from ..common.Collection import Collection
from ..common import utils
from ..common import pdf


class Rectangles(Collection):

    @property
    def border_rects(self):
        '''Rectangles in border type.'''
        return list(filter(
            lambda rect: rect.type==RectType.BORDER, self._instances))

    def from_annotations(self, page):
        ''' Get shapes, e.g. Line, Square, Highlight, from annotations(comment shapes) in PDF page.
            ---
            Args:
            - page: fitz.Page, current page
        '''
        rects = pdf.rects_from_annotations(page)
        for rect in rects:
            self._instances.append(Rectangle(rect))

        return self


    def from_stream(self, doc, page):
        ''' Get rectangle shapes, e.g. highlight, underline, table borders, from page source contents.
            ---
            Args:
            - doc: fitz.Document representing the pdf file
            - page: fitz.Page, current page
        '''
        rects = pdf.rects_from_stream(doc, page)
        for rect in rects:
            self._instances.append(Rectangle(rect))

        return self


    def clean(self, page_bbox):
        '''Clean rectangles:
            - delete rectangles fully contained in another one (beside, they have same bg-color)
            - join intersected and horizontally aligned rectangles with same height and bg-color
            - join intersected and vertically aligned rectangles with same width and bg-color
        '''
        # remove rects out of page
        f = lambda rect: rect.bbox.intersects(page_bbox)
        self._instances = list(filter(f, self._instances))

        # sort in reading order
        self.sort_in_reading_order()

        # skip rectangles with both of the following two conditions satisfied:
        #  - fully or almost contained in another rectangle
        #  - same filling color with the containing rectangle
        rects_unique = [] # type: list [Rectangle]
        rect_changed = False
        for rect in self._instances:
            for ref_rect in rects_unique:
                # Do nothing if these two rects in different bg-color
                if ref_rect.color!=rect.color: continue     

                # combine two rects in a same row if any intersection exists
                # ideally the aligning threshold should be 1.0, but use 0.98 here to consider tolerance
                if rect.horizontally_align_with(ref_rect, 0.98): 
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.0)

                # combine two rects in a same column if any intersection exists
                elif rect.vertically_align_with(ref_rect, 0.98):
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.0)

                # combine two rects if they have a large intersection
                else:
                    main_bbox = utils.get_main_bbox(rect.bbox, ref_rect.bbox, 0.5)

                if main_bbox:
                    rect_changed = True
                    ref_rect.update(main_bbox)
                    break            
            else:
                rects_unique.append(rect)
                
        # update layout
        if rect_changed:
            self._instances = rects_unique

        return rect_changed


    def get_contained_rect(self, target, threshold:float):
        '''Get rect contained in given bbox.
            ---
            Args:
            - target: BBox, target bbox
            - threshold: regard as contained if the intersection exceeds this threshold
        '''
        s = target.bbox.getArea()
        if not s: return None

        for rect in self._instances:
            intersection = target.bbox & rect.bbox
            if intersection.getArea() / s >= threshold:
                res = rect
                break
        else:
            res = None

        return res