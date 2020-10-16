# -*- coding: utf-8 -*-

'''
A group of Shape (Stroke or Fill) instances.

@created: 2020-09-15
@author: train8808@gmail.com
'''

from .Shape import Shape, Stroke, Fill
from ..common.base import RectType, lazyproperty
from ..common.Collection import Collection
from ..common import utils
from ..common import constants


class Shapes(Collection):

    def __init__(self, instances:list=[], parent=None):
        ''' A collection of Shape instances: Stroke or Fill.'''
        super().__init__(instances, parent)

        # properties for context type of shape, e.g. 
        # a Stroke instace may be either table border or text underline or strike-through,
        # a Fill instance may be either cell shading or text highlight.
        self._table_strokes = Collection()
        self._table_fillings = Collection()

        self._text_underlines_strikes = Collection() # they're combined at this moment
        self._text_highlights = Collection()


    def from_dicts(self, raws:list):
        '''Initialize Stroke/Fill from dicts.'''
        # distinguish Stroke and Fill: whether keys 'start' and 'end' exist in dict
        for raw in raws:
            shape = Stroke(raw) if 'start' in raw else Fill(raw)
            # add to list
            self.append(shape)
        
        return self


    def _update_bbox(self, shape:Shape):
        ''' override. Do nothing.'''
        pass


    @lazyproperty
    def strokes(self):
        ''' Stroke Shapes. including table border, text underline and strike-through. 
            Cache it once calculated since it doesn't change generally.
        '''
        instances = list(filter(
            lambda shape: isinstance(shape, Stroke), self._instances))
        return Shapes(instances)


    @lazyproperty
    def fillings(self):
        ''' Fill Shapes, including cell shading and highlight. 
            Cache it once calculated since it doesn't change generally.
        '''
        # white bg-color is by default, so ignore those fillings
        instances = list(filter(
            lambda shape: isinstance(shape, Fill) and shape.color != utils.RGB_value((1,1,1)), self._instances))
        return Shapes(instances)


    @property
    def table_strokes(self):
        '''potential table borders.'''
        return self._table_strokes

    
    @property
    def table_fillings(self):
        '''potential table shadings.'''
        return self._table_fillings


    @property
    def text_highlights(self):
        '''potential text highlights.'''
        return self._text_highlights


    @property
    def text_underlines_strikes(self):
        '''potential text underlines and strike-through lines.'''
        return self._text_underlines_strikes


    def clean_up(self):
        '''Clean rectangles:
            - delete rectangles fully contained in another one (beside, they have same bg-color)
            - join intersected and horizontally aligned rectangles with same height and bg-color
            - join intersected and vertically aligned rectangles with same width and bg-color
        '''
        # sort in reading order
        self.sort_in_reading_order()

        # remove shapes out of page
        page_bbox = (0.0, 0.0, self.parent.width, self.parent.height)
        f = lambda shape: shape.bbox.intersects(page_bbox)
        shapes = filter(f, self._instances)

        # merge shapes if:
        # - same filling color, and
        # - intersected in same raw/col, or overlapped significantly
        shapes_unique = [] # type: list [Shape]
        for shape in shapes:
            for ref_shape in shapes_unique:
                # Do nothing if these two shapes in different bg-color
                if ref_shape.color!=shape.color: continue     

                # combine two shapes in a same row if any intersection exists
                # ideally the aligning threshold should be 1.0, tolerance is considered here
                if shape.horizontally_align_with(ref_shape, constants.FACTOR_SAME): 
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, 0.0)

                # combine two shapes in a same column if any intersection exists
                elif shape.vertically_align_with(ref_shape, constants.FACTOR_SAME):
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, 0.0)

                # combine two shapes if they have a large intersection
                else:
                    main_bbox = utils.get_main_bbox(shape.bbox, ref_shape.bbox, constants.FACTOR_A_HALF)

                if main_bbox:
                    ref_shape.update_bbox(main_bbox)
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


    def detect_initial_categories(self):
        ''' Detect shape type based on the position to text blocks. 
            It should run right after `clean_up()`.
        '''
        # reset all
        self._table_strokes.reset()
        self._table_fillings.reset()
        self._text_underlines_strikes.reset()
        self._text_highlights.reset()

        # all blocks in page (the original blocks without any further processing)
        blocks = self._parent.blocks
        blocks.sort_in_reading_order()

        # check positions between shapes and blocks
        for shape in self._instances:
            # try to determin shape semantic type
            rect_type = shape.semantic_type(blocks)     # type: RectType

            if rect_type==RectType.UNDERLINE_OR_STRIKE:
                self._text_underlines_strikes.append(shape)
            
            elif rect_type==RectType.BORDER:
                self._table_strokes.append(shape)

            elif rect_type==RectType.SHADING:
                self._table_fillings.append(shape)
            
            elif rect_type==RectType.HIGHLIGHT:
                self._text_highlights.append(shape)

            # if not determined, it should be the opposite type, e.g. table border for a Stroke, 
            # highlight for a Fill. However, condering margin, incorrectly organized blocks, e.g.
            # a text underline may have no intersection with the text block, so let's add the shape 
            # to both groups for conservation. It'll finally determined when parsing table structure
            # and text format.
            else:
                if isinstance(shape, Stroke):
                    self._table_strokes.append(shape)
                    self._text_underlines_strikes.append(shape)
                else:
                    self._text_highlights.append(shape)
                    self._table_fillings.append(shape)
    

    def plot(self, page):
        '''Plot shapes in PDF page.'''
        # different colors are used to show the shapes in detected semantic types
        # Due to overlaps between Stroke and Fill related groups, some shapes are plot twice.

        # -table shading
        color = (152/255, 251/255, 152/255)
        for shape in self._table_fillings: shape.plot(page, color)

        # - table borders
        color = (0, 0, 0)
        for shape in self._table_strokes: shape.plot(page, color)

        # - underline and strike-through
        color = (1, 0, 0)
        for shape in self._text_underlines_strikes: shape.plot(page, color)

        # highlight
        color = (1, 1, 0)
        for shape in self._text_highlights: shape.plot(page, color)
