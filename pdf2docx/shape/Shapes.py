# -*- coding: utf-8 -*-

'''A group of ``Shape`` instances.
'''

from .Shape import Shape, Stroke, Fill, Hyperlink
from ..common.share import RectType, lazyproperty
from ..common.Collection import Collection, ElementCollection
from ..common import share


class Shapes(ElementCollection):
    ''' A collection of ``Shape`` instances: ``Stroke`` or ``Fill``.'''
    def __init__(self, instances:list=None, parent=None):
        
        super().__init__(instances, parent)

        # properties for context type of shape, e.g. 
        # a Stroke instace may be either table border or text underline or strike-through,
        # a Fill instance may be either cell shading or text highlight.
        self._table_strokes = ElementCollection()
        self._table_fillings = ElementCollection()

        self._text_underlines_strikes = ElementCollection() # they're combined at this moment
        self._text_highlights = ElementCollection()


    def restore(self, raws:list):
        '''Clean current instances and restore them from source dicts.'''
        self.reset()
        # Distinguish specified type by key like `start`, `end` and `uri`.
        for raw in raws:
            if 'start' in raw:
                shape = Stroke(raw)
            elif 'uri' in raw:
                shape = Hyperlink(raw)
            else:
                shape = Fill(raw)
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


    @lazyproperty
    def hyperlinks(self):
        ''' Hyperlink Shapes.'''
        instances = list(filter(
            lambda shape: isinstance(shape, Hyperlink), self._instances))
        return Shapes(instances)


    @property
    def table_strokes(self):
        '''Potential table borders.'''
        return self._table_strokes

    
    @property
    def table_fillings(self):
        '''Potential table shadings.'''
        return self._table_fillings


    @property
    def text_highlights(self):
        '''Potential text highlights.'''
        return self._text_highlights


    @property
    def text_underlines_strikes(self):
        '''Potential text underlines and strike-through lines.'''
        return self._text_underlines_strikes


    def clean_up(self, max_border_width:float, shape_merging_threshold:float, shape_min_dimension:float):
        """Clean rectangles.

        * Delete small shapes (either width or height).
        * Delete shapes out of page.
        * Merge shapes with same filling color and significant overlap.
        * Detect semantic type.

        Args:
            max_border_width (float): The max border width.
            shape_merging_threshold (float): Merge shape if the intersection exceeds this value.
            shape_min_dimension (float): Ignore shape if both width and height is lower than this value.
        """
        if not self._instances: return

        # clean up shapes:
        # - remove shapes out of page
        # - remove small shapes
        page_bbox = self.parent.bbox
        f = lambda shape: shape.bbox.intersects(page_bbox) and \
                        (shape.bbox.width>=shape_min_dimension or shape.bbox.height>=shape_min_dimension)
        cleaned_shapes = list(filter(f, self._instances))

        # merge normal shapes if same filling color and significant overlap        
        merged_shapes = []
        normal_shapes = list(filter(
            lambda shape: shape.type==RectType.UNDEFINED, cleaned_shapes))        
        f = lambda a, b: a.color==b.color and (
            a.get_main_bbox(b, threshold=shape_merging_threshold) or \
            b.get_main_bbox(a, threshold=shape_merging_threshold))        
        for group in Collection(normal_shapes).group(f):
            merged_shapes.append(group[0].update_bbox(group.bbox))
        
        # add hyperlinks
        hyperlinks = filter(lambda shape: shape.type==RectType.HYPERLINK, cleaned_shapes)
        merged_shapes.extend(hyperlinks)
                
        # convert Fill instance to Stroke if looks like stroke
        shapes = []
        for shape in merged_shapes:
            if isinstance(shape, Fill):
                stroke = shape.to_stroke(max_border_width)
                shapes.append(stroke if stroke else shape)
            else:
                shapes.append(shape)
        self.reset(shapes).sort_in_reading_order() # sort in reading order


    def detect_initial_categories(self):
        ''' Detect shape type based on the position to text blocks. 

        .. note::
            Stroke shapes are grouped on connectivity to each other, but in some cases, 
            the gap between borders and underlines/strikes are very close, which leads
            to an incorrect table structure. So, it's required to distinguish them in
            advance, though we needn't to ensure 100% accuracy.
        '''
        # reset all
        self._table_strokes.reset()
        self._table_fillings.reset()
        self._text_underlines_strikes.reset()
        self._text_highlights.reset()

        # blocks in page (the original blocks without any further processing)
        blocks = self._parent.blocks
        blocks.sort_in_reading_order()

        # check positions between shapes and text blocks
        for shape in self._instances:
            # try to determin shape semantic type:
            # - check if text underline/strike for a stroke
            # - check if table shading for a fill
            rect_type = shape.semantic_type(blocks.text_blocks)     # type: RectType

            # set the type if succeeded
            if rect_type==RectType.HYPERLINK:
                continue

            elif rect_type==RectType.UNDERLINE_OR_STRIKE:
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
    

    def assign_to_tables(self, tables:list):
        """Add Shape to associated cells of given tables.

        Args:
            tables (list): A list of TableBlock instances.
        """
        if not tables: return

        # assign shapes to table region        
        shapes_in_tables = [[] for _ in tables] # type: list[list[Shape]]
        shapes = []   # type: list[Shape]
        for shape in self._instances:
            # exclude explicit table borders which belongs to current layout
            if shape.type in (RectType.BORDER, RectType.SHADING):
                shapes.append(shape)
                continue

            for table, shapes_in_table in zip(tables, shapes_in_tables):
                # fully contained in one table
                if table.bbox.contains(shape.bbox):
                    shapes_in_table.append(shape)
                    break

                # not possible in current table, then check next table
                elif not table.bbox.intersects(shape.bbox):
                    continue
            
            # Now, this shape belongs to previous layout
            else:
                shapes.append(shape)

        # assign shapes to associated cells
        for table, shapes_in_table in zip(tables, shapes_in_tables):
            # no contents for this table
            if not shapes_in_table: continue
            table.assign_shapes(shapes_in_table)

        self.reset(shapes).sort_in_reading_order()


    def plot(self, page):
        '''Plot shapes for debug purpose.
        
        Args:
            page (fitz.Page): pdf page.
        '''
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
