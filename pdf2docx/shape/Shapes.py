# -*- coding: utf-8 -*-

'''
A group of Shape (Stroke or Fill) instances.

@created: 2020-09-15
@author: train8808@gmail.com
'''

from .Shape import Shape, Stroke, Fill
from ..common.share import RectType, lazyproperty
from ..common.Collection import Collection
from ..common import share
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
            lambda shape: isinstance(shape, Fill) and shape.color != share.rgb_value((1,1,1)), self._instances))
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


    def clean_up(self, max_border_width:float, shape_merging_threshold:float, shape_min_dimension:float):
        '''Clean rectangles:
            - delete rectangles fully contained in another one (beside, they have same bg-color)
            - join intersected and horizontally aligned rectangles with same height and bg-color
            - join intersected and vertically aligned rectangles with same width and bg-color
        '''
        if not self._instances: return
        
        # sort in reading order
        self.sort_in_reading_order()

        # clean up shapes:
        # - remove shapes out of page
        # - remove small shapes
        page_bbox = (0.0, 0.0, self.parent.width, self.parent.height)
        f = lambda shape: shape.bbox.intersects(page_bbox) and \
                        (shape.bbox.width>=shape_min_dimension or shape.bbox.height>=shape_min_dimension)
        shapes = filter(f, self._instances)

        # merge shapes if:
        # - same filling color, and
        # - intersected in same raw/col, or overlapped significantly
        shapes_unique = [] # type: list [Shape]
        for shape in shapes:
            for ref_shape in shapes_unique:
                # Do nothing if these two shapes in different bg-color
                if ref_shape.color!=shape.color: continue     

                # # combine two shapes in a same row if any intersection exists
                # if shape.in_same_row(ref_shape): 
                #     main_bbox = shape.get_main_bbox(ref_shape, 0.0)

                # # combine two shapes if they have a large intersection
                # else:
                main_bbox = shape.get_main_bbox(ref_shape, threshold=shape_merging_threshold)

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
                stroke = shape.to_stroke(max_border_width)
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
            # try to determin shape semantic type:
            # - check if text underline/strike for a stroke
            # - check if table shading for a fill
            rect_type = shape.semantic_type(blocks)     # type: RectType

            # set the type if succeeded
            if rect_type==RectType.UNDERLINE_OR_STRIKE:
                self._text_underlines_strikes.append(shape)
            
            elif rect_type==RectType.SHADING:
                self._table_fillings.append(shape)
            

            # otherwise, it should be the opposite type, e.g. 
            # table border for a Stroke, highlight for a Fill. 
            else:
                # However, condering margin, incorrectly organized blocks, e.g.
                # a text underline may have no intersection with the text block, so add the stroke shape 
                # to both groups for conservation. It'll finally determined when parsing table structure
                # and text format.
                if isinstance(shape, Stroke):
                    self._table_strokes.append(shape)
                    self._text_underlines_strikes.append(shape)
                
                # for a fill shape, it should be a highlight if parsing table shading failed
                else:
                    self._text_highlights.append(shape)
    

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
