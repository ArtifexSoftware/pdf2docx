# -*- coding: utf-8 -*-

'''
A group of Shape instances.

@created: 2020-09-15
@author: train8808@gmail.com
'''

from .Shape import Shape, Stroke, Fill
from ..common.base import RectType
from ..common.Collection import Collection
from ..common import utils
from ..common import pdf



class Shapes(Collection):

    def _update(self, shape:Shape):
        ''' override. Do nothing.'''
        pass

    @property
    def borders(self):
        '''Shapes in border type.'''
        instances = list(filter(
            lambda shape: shape.type==RectType.BORDER, self._instances))
        return Shapes(instances)

    @property
    def strokes(self):
        '''Shapes in border type.'''
        instances = list(filter(
            lambda shape: isinstance(shape, Stroke), self._instances))
        return Shapes(instances)

    @property
    def fillings(self):
        '''Shapes in border type.'''
        instances = list(filter(
            lambda shape: isinstance(shape, Fill), self._instances))
        return Shapes(instances)


    def from_annotations(self, page):
        ''' Get shapes, e.g. Line, Square, Highlight, from annotations(comment shapes) in PDF page.
            ---
            Args:
            - page: fitz.Page, current page
        '''
        strokes, fills = pdf.shapes_from_annotations(page)
        self._initialize(strokes, fills)
        return self


    def from_stream(self, doc, page):
        ''' Get rectangle shapes, e.g. highlight, underline, table borders, from page source contents.
            ---
            Args:
            - doc: fitz.Document representing the pdf file
            - page: fitz.Page, current page
        '''
        strokes, fills = pdf.shapes_from_stream(doc, page)        
        self._initialize(strokes, fills)
        return self


    def _initialize(self, strokes:list, fills:list):
        '''Create Stroke or Fill instances with parsed shapes from PDF.'''
        # strokes
        for raw in strokes: self._instances.append(Stroke(raw))

        # fills: may be stroke, to further process later
        for raw in fills: self._instances.append(Fill(raw))


    def clean(self):
        '''Clean rectangles:
            - delete rectangles fully contained in another one (beside, they have same bg-color)
            - join intersected and horizontally aligned rectangles with same height and bg-color
            - join intersected and vertically aligned rectangles with same width and bg-color
        '''
        # remove shapes out of page
        page_bbox = (0.0, 0.0, self.parent.width, self.parent.height)
        f = lambda shape: shape.bbox.intersects(page_bbox)
        shapes = list(filter(f, self._instances))

        # sort in reading order
        self.sort_in_reading_order()

        # skip rectangles with both of the following two conditions satisfied:
        #  - fully or almost contained in another rectangle
        #  - same filling color with the containing rectangle
        shapes_unique = [] # type: list [Shape]
        for shape in shapes:
            for ref_shape in shapes_unique:
                # Do nothing if these two shapes in different bg-color
                if ref_shape.color!=shape.color: continue     

                # combine two shapes in a same row if any intersection exists
                # ideally the aligning threshold should be 1.0, but use 0.98 here to consider tolerance
                if shape.horizontally_align_with(ref_shape, 0.98): 
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, 0.0)

                # combine two shapes in a same column if any intersection exists
                elif shape.vertically_align_with(ref_shape, 0.98):
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, 0.0)

                # combine two shapes if they have a large intersection
                else:
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, 0.5)

                if main_bbox:
                    ref_shape.update(main_bbox)
                    break            
            else:
                shapes_unique.append(shape)
                
        # convert Fill instance to Stroke if looks like stroke
        shapes = []
        for shape in shapes_unique:
            if isinstance(shape, Stroke):
                shapes.append(shape)
            else:
                stroke = shape.to_stroke()
                shapes.append(stroke if stroke else shape)

        self.reset(shapes)

        return True


    def contained_in_bbox(self, bbox):
        ''' Filter shapes contained in target bbox.
            ---
            Args:
            - bbox: fitz.Rect
        '''
        instances = list(filter(
            lambda shape: shape.bbox & bbox, self._instances)) # use intersection as torrence
        return Shapes(instances)


    def containing_bbox(self, bbox, threshold:float):
        ''' Get the shape containing target bbox.
            ---
            Args:
            - bbox: fitz.Rect, target bbox
            - threshold: regard as contained if the intersection exceeds this threshold
        '''
        s = bbox.getArea()
        if not s: return None

        for instance in self._instances:
            intersection = bbox & instance.bbox
            if intersection.getArea() / s >= threshold:
                res = instance
                break
        else:
            res = None

        return res