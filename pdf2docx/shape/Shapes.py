'''A group of ``Shape`` instances.'''

from .Shape import Shape, Stroke, Fill, Hyperlink
from ..common.share import RectType
from ..common.Collection import Collection, ElementCollection
from ..common import share
from ..common import constants


class Shapes(ElementCollection):
    ''' A collection of ``Shape`` instances: ``Stroke`` or ``Fill``.'''

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


    def _update_bbox(self, e:Shape):
        ''' override. Do nothing.'''


    @property
    def strokes(self):
        ''' Stroke Shapes, including table border, text underline and strike-through.'''
        instances = list(filter(
            lambda shape: isinstance(shape, Stroke), self._instances))
        return Shapes(instances)


    @property
    def fillings(self):
        ''' Fill Shapes, including cell shading and highlight.'''
        # white bg-color is by default, so ignore those fillings
        instances = list(filter(
            lambda shape: isinstance(shape, Fill) and \
                shape.color != share.rgb_value((1,1,1)), self._instances))
        return Shapes(instances)


    @property
    def hyperlinks(self):
        ''' Hyperlink Shapes.'''
        instances = list(filter(
            lambda shape: isinstance(shape, Hyperlink), self._instances))
        return Shapes(instances)


    @property
    def table_strokes(self):
        '''Potential table borders.'''
        instances = list(filter(
            lambda shape: shape.has_potential_type(RectType.BORDER), self._instances))
        return ElementCollection(instances)


    @property
    def table_fillings(self):
        '''Potential table shadings.'''
        instances = list(filter(
            lambda shape: shape.has_potential_type(RectType.SHADING), self._instances))
        return ElementCollection(instances)


    @property
    def text_style_shapes(self):
        '''Potential text style based shapes,
        e.g. underline, strike-through, highlight and hyperlink.'''
        def f(shape):
            return shape.has_potential_type(RectType.HIGHLIGHT) or \
                    shape.has_potential_type(RectType.UNDERLINE) or \
                    shape.has_potential_type(RectType.STRIKE) or \
                    shape.has_potential_type(RectType.HYPERLINK)
        instances = set(filter(f, self._instances))
        return ElementCollection(instances)


    def clean_up(self, max_border_width:float, shape_min_dimension:float):
        """Clean rectangles.

        * Delete shapes out of page.
        * Delete small shapes (either width or height).
        * Merge shapes with same filling color.
        * Detect semantic type.

        Args:
            max_border_width (float): The max border width.
            shape_min_dimension (float): Ignore shape if both width and height
                is lower than this value.
        """
        if not self._instances: return

        # remove small shapes or shapes out of page; and
        # update bbox in case part of the shape is out of page
        page_bbox = self.parent.bbox
        cleaned_shapes = [] # type: list[Shape]
        for s in self:
            if max(s.bbox.width, s.bbox.height)<shape_min_dimension: continue # small shapes
            bbox_in_page = s.bbox.intersect(page_bbox)
            if bbox_in_page.is_empty: continue # shapes out of page
            cleaned_shapes.append(s.update_bbox(bbox_in_page)) # ignore out of page part

        # merge normal shapes if same filling color
        merged_shapes = self._merge_shapes(cleaned_shapes)

        # convert Fill instance to Stroke if looks like stroke
        shapes = []
        for shape in merged_shapes:
            if isinstance(shape, Fill):
                stroke = shape.to_stroke(max_border_width)
                shapes.append(stroke if stroke else shape)
            else:
                shapes.append(shape)
        self.reset(shapes)

        # detect semantic type
        self._parse_semantic_type()


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
            if shape.equal_to_type(RectType.BORDER) or shape.equal_to_type(RectType.SHADING):
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

        self.reset(shapes)


    def plot(self, page):
        '''Plot shapes for debug purpose.
        Different colors are used to display the shapes in detected semantic types, e.g.
        yellow for text based shape (stroke, underline and highlight). Due to overlaps
        between Stroke and Fill related groups, some shapes are plot twice.

        Args:
            page (fitz.Page): pdf page.
        '''
        # Table based shapes
        # - table shading
        color = (152/255, 251/255, 152/255)
        for shape in self.table_fillings: shape.plot(page, color)

        # - table borders
        color = (0, 0, 0)
        for shape in self.table_strokes: shape.plot(page, color)

        # Text based shapes
        # - underline
        # - strike-through
        # - highlight
        # - hyperlink
        color = (1, 1, 0)
        for shape in self.text_style_shapes: shape.plot(page, color)


    @staticmethod
    def _merge_shapes(shapes):
        '''Merge shapes if same filling color. Note the merged bbox must match source shapes
        as more as possible.'''
        # shapes excluding hyperlink first
        normal_shapes = list(filter(
            lambda shape: not shape.is_determined, shapes))

        # group by color and connectivity (with margin considered)
        def f(a, b):
            return a.color==b.color and a.bbox.intersects(b.get_expand_bbox(constants.TINY_DIST))
        groups = Collection(normal_shapes).group(f)

        merged_shapes = []
        for group in groups:
            merged_area = group.bbox.get_area()
            sum_area = sum(shape.bbox.get_area() for shape in group)
            if sum_area/merged_area >= constants.FACTOR_ALMOST:
                merged_shapes.append(group[0].update_bbox(group.bbox))
            else:
                merged_shapes.extend(group)

        # add hyperlinks back
        hyperlinks = filter(lambda shape: shape.equal_to_type(RectType.HYPERLINK), shapes)
        merged_shapes.extend(hyperlinks)
        return merged_shapes


    def _parse_semantic_type(self):
        ''' Detect shape type based on the position to text blocks.

        .. note::
            Stroke shapes are grouped on connectivity to each other, but in some cases,
            the gap between borders and underlines/strikes are very close, which leads
            to an incorrect table structure. So, it's required to distinguish them in
            advance, though we needn't to ensure 100% accuracy. They are finally determined
            when parsing table structure and text format.
        '''
        # blocks in page (the original blocks without any further processing)
        blocks = self._parent.blocks
        blocks.sort_in_reading_order()

        # check positions between shapes and text blocks
        for shape in self._instances:
            shape.parse_semantic_type(blocks)
