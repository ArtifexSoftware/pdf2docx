# -*- coding: utf-8 -*-

'''
Parsing table blocks:
- lattice table: explicit borders represented by rectangles
- stream table : borderless table recognized from layout of text blocks.

@created: 2020-08-16
@author: train8808@gmail.com
'''


from ..common.base import RectType
from ..common.constants import MAX_W_BORDER, DR
from ..layout.Blocks import Blocks
from ..shape.Rectangle import Rectangle
from ..shape.Rectangles import Rectangles
from ..text.Lines import Lines
from .TableStructure import TableStructure
from .Border import HBorder, VBorder


class TablesConstructor(TableStructure):

    def __init__(self, blocks:Blocks, rects:Rectangles):
        '''Object parsing TableBlock.'''
        self._blocks = blocks
        self._rects = rects


    def lattice_tables(self):
        '''Parse table with explicit borders/shadings represented by rectangle shapes.'''
        # group rects: each group may be a potential table
        fun = lambda a,b: a.bbox & b.bbox
        groups = self._rects.group(fun)

        # parse table with each group
        tables = Blocks()
        for group in groups:
            # parse table structure based on rects in border type
            table = self.parse_structure(group, detect_border=True)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add table to page level
            table.set_lattice_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return unique_tables


    def combined_tables(self):
        ''' Parse table with outer borders extracted from shading rects, 
            and inner borders parsed from layout of text blocks.

            Combined with lattice and stream table parsing methods, this table 
            is to simulate the shading shape in docx. 
        '''
        shading_rects = self._shading_rects(width_threshold=MAX_W_BORDER)

        # table based on each shading rect
        tables = Blocks()
        for rect in shading_rects:

            # boundary borders
            x0, y0, x1, y1 = rect.bbox_raw
            top = HBorder().finalize(y0)
            bottom = HBorder().finalize(y1)
            left = VBorder().finalize(x0)
            right = VBorder().finalize(x1)

            top.set_boundary_borders((left, right))
            bottom.set_boundary_borders((left, right))
            left.set_boundary_borders((top, bottom))
            right.set_boundary_borders((top, bottom))

            # lines contained in shading rect
            table_lines = Lines()
            for block in self._blocks:
                if rect.bbox.contains(block.bbox):
                    table_lines.extend(block.lines)
            
            # potentail borders contained in shading rect
            showing_borders = Rectangles()
            for rect_ in self._rects:
                if rect.bbox.intersects(rect_.bbox):
                    showing_borders.append(rect_)
            
            # parse borders based on contents in cell
            table_rects = self.stream_borders(table_lines, (top, bottom, left, right), showing_borders)
            if not table_rects: continue

            # get potential cell shading: note consider not processed rect only
            table_bbox = table_rects.bbox
            table_rects.extend(filter(
                lambda rect: table_bbox.intersects(rect.bbox) and rect.type==RectType.UNDEFINED, self._rects))

            # parse table: don't have to detect borders since it's determined already
            table_rects.sort_in_reading_order() # required
            table = self.parse_structure(table_rects, detect_border=False)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add parsed table to page level blocks
            table.set_stream_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return unique_tables


    def stream_tables(self, X0:float=-1, X1:float=-1):
        ''' Parse borderless table based on the layout of text/image blocks.
            ---
            Args:
            - X0, X1: left and right boundaries of allowed table region

            Since no cell borders exist in this case, there may be various probabilities of table structures. 
            Among which, we use the simplest one, i.e. 1-row and n-column, to make the docx look like pdf.

            Ensure no horizontally aligned blocks in each column, so that these blocks can be converted to
            paragraphs consequently in docx.
        '''
        if len(self._blocks)<=1: return []      

        # potential bboxes
        tables_lines = self._blocks.collect_stream_lines()

        # parse tables
        tables = Blocks()
        margin = 1.0
        for table_lines in tables_lines:
            # boundary borders
            y0 = min([rect.bbox.y0 for rect in table_lines])
            y1 = max([rect.bbox.y1 for rect in table_lines])
            top = HBorder((y0-margin, y0))
            bottom = HBorder((y1, y1+margin))
            left = VBorder((X0-margin, X0))
            right = VBorder((X1, X1+margin))

            top.set_boundary_borders((left, right))
            bottom.set_boundary_borders((left, right))
            left.set_boundary_borders((top, bottom))
            right.set_boundary_borders((top, bottom))

            # potentail borders contained in shading rect
            bbox = (X0-margin, y0-margin, X1+margin, y1+margin)
            showing_borders = Rectangles()
            for rect in self._rects:
                if rect.bbox.intersects(bbox):
                    showing_borders.append(rect)

            # parse borders based on contents in cell
            table_rects = self.stream_borders(table_lines, (top, bottom, left, right), showing_borders)
            if not table_rects: continue

            # get potential cell shading: note consider not processed rect only
            table_bbox = table_rects.bbox
            table_rects.extend(filter(
                lambda rect: table_bbox.intersects(rect.bbox) and rect.type==RectType.UNDEFINED, self._rects))

            # parse table: don't have to detect borders since it's determined already
            table_rects.sort_in_reading_order() # required
            table = self.parse_structure(table_rects, detect_border=False)
            tables.append(table)

        # check if any intersection with previously parsed tables
        unique_tables = self._remove_floating_tables(tables)
        for table in unique_tables:
            # add parsed table to page level blocks
            # in addition, ignore table if contains only one cell since it's unnecessary for stream table
            if table.num_rows>1 or table.num_cols>1:
                table.set_stream_table_block()

        # assign text contents to each table
        self._blocks.assign_table_contents(unique_tables)

        return unique_tables


    @staticmethod
    def _remove_floating_tables(tables:Blocks):
        '''Delete table has intersection with previously parsed tables.'''
        unique_tables = []
        fun = lambda a,b: a.bbox & b.bbox
        for group in tables.group(fun):
            # single table
            if len(group)==1:
                table = group[0]
            
            # intersected tables: keep the table with the most cells only 
            # since no floating elements are supported with python-docx
            else:
                sorted_group = sorted(group, 
                            key=lambda table: table.num_rows*table.num_cols)
                table = sorted_group[-1]
            
            unique_tables.append(table)
        
        return unique_tables


    def _shading_rects(self, width_threshold:float):
        ''' Detect shading rects.
            ---
            Args:
            - width_threshold: float, suppose shading rect width is larger than this value

            NOTE: Shading borders are checked after parsing lattice tables.            
            
            Note to distinguish shading shape and highlight: 
            - there exists at least one text block contained in shading rect,
            - or no any intersetions with other text blocks (empty block is deleted already);
            - otherwise, highlight rect
        '''
        # lattice tables
        lattice_tables = self._blocks.lattice_table_blocks

        # check rects
        shading_rects = [] # type: list[Rectangle]
        for rect in self._rects:

            # focus on rect not parsed yet
            if rect.type != RectType.UNDEFINED: continue

            # not in lattice table region
            for table in lattice_tables:
                if table.bbox.contains(rect.bbox):
                    skip = True
                    break
            else:
                skip = False
            if skip: continue

            # potential shading rects: min-width > 6 Pt
            x0, y0, x1, y1 = rect.bbox_raw
            if min(x1-x0, y1-y0) <= width_threshold:
                continue

            # now shading rect or highlight rect:
            # shading rect contains at least one text block
            shading = False
            expand_bbox = rect.bbox + DR / 0.2 # expand 2.5 Pt
            for block in self._blocks:
                if expand_bbox.contains(block.bbox):
                    shading = True
                    break

                # do not containing but intersecting with text block -> can't be shading rect
                elif expand_bbox.intersects(block.bbox):
                    break
                
                # no chance any more
                elif block.bbox.y0 > rect.bbox.y1: 
                    break
            
            if shading:
                shading_rects.append(rect)            

        return shading_rects


