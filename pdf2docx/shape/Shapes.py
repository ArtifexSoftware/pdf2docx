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
        self._table_borders = Collection()
        self._table_shadings = Collection()

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
    def table_borders(self):
        '''potential table borders.'''
        return self._table_borders

    
    @property
    def table_shadings(self):
        '''potential table shadings.'''
        return self._table_shadings


    @property
    def text_highlights(self):
        '''potential text highlights.'''
        return self._text_highlights


    @property
    def text_underlines_strikes(self):
        '''potential text underlines and strike-through lines.'''
        return self._text_underlines_strikes


    @property
    def potential_shadings(self):
        ''' Potential shading shapes to process. Note to distinguish shading shape with highlight: 
            - there exists at least one text block contained in shading rect,
            - or no any intersetions with other text blocks (empty block is deleted already);
            - otherwise, highlight rect
        '''
        # needn't to consider shapes in parsed tables
        tables = self._parent.blocks.table_blocks
        def shape_in_parsed_tables(shape):
            for table in tables:
                if table.bbox.contains(shape.bbox): return True
            return False

        # check shapes
        shading_shapes = [] # type: list[Fill]
        for shape in self.fillings:

            # focus on shape not parsed yet
            if shape.type != RectType.UNDEFINED: continue

            # not in parsed table region
            if shape_in_parsed_tables(shape): continue

            # cell shading or highlight:
            # shading shape contains at least one text block
            shading = False
            for block in self._parent.blocks:
                if shape.contains(block, threshold=constants.FACTOR_A_FEW):
                    shading = True
                    break
                
                # no chance any more
                elif block.bbox.y0 > shape.bbox.y1: 
                    break
            
            if shading: shading_shapes.append(shape)            

        return Shapes(shading_shapes)


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
        ''' Detect shape type based on the position to text blocks. It should run right after `clean_up()`.

            Though looks like a line segment, difference exists between table border and text format line,
            including underline and strike-through:
            - underline or strike-through is always contained in a certain text block
            - table border is never contained in a text block, though intersection exists due to incorrectly 
            organized text blocks

            Though looks like a filling area, difference exists between table shading and text highlight:
            - table shading either contains at least one text block (with margin considered),
            - or no any intersetions with other text blocks;
            - otherwise, it's a text highlight
        '''
        # reset all
        self._table_borders.reset()
        self._table_shadings.reset()
        self._text_underlines_strikes.reset()
        self._text_highlights.reset()

        # all blocks in page (the original blocks without any further processing)
        blocks = self._parent.blocks
        blocks.sort_in_reading_order()

        # check positions between shapes and blocks
        for shape in self._instances:
            # object type: Stroke or Fill
            is_stroke = isinstance(shape, Stroke)
            found = False

            # then, check context type
            for block in self._parent.blocks:
                
                # no intersection any more since it's sorted
                if block.bbox.y0 > shape.bbox.y1: break

                # border v.s. underline & strike-through
                if is_stroke:
                    # text style line always contained in a certain block, even a block line
                    # a very strict margin: threshold=0.0 for this case
                    if block.contains(shape, threshold=constants.FACTOR_FEW):
                        # deep into block line because a real border may be very close to a text block
                        if any([line.contains(shape, threshold=constants.FACTOR_FEW) for line in block.lines]):
                            self._text_underlines_strikes.append(shape)
                            found = True
                            break

                # shading v.s. highlight
                else:
                    # table shading always contains at least a text block, but considering incorrectly organized
                    # text blocks, it contains at least a block line for conservation
                    if not shape.contains(block, threshold=constants.FACTOR_A_FEW):
                        if any([shape.contains(line, threshold=constants.FACTOR_A_FEW) for line in block.lines]):
                            self._table_shadings.append(shape)
                            found = True
                            break            
            
            # now, already checked with all blocks
            if found: continue
            # a stroke not contained in any blocks -> table border
            if is_stroke:
                self._table_borders.append(shape)
            
            # a fill doesn't contain any blocks -> text heightlight
            else:
                self._text_highlights.append(shape)

