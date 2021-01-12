# -*- coding: utf-8 -*-

'''Layout depends on Blocks and Shapes.
'''

from . import Page
from .Blocks import Blocks
from ..shape.Shapes import Shapes
from ..table.TablesConstructor import TablesConstructor
from ..table.Cell import Cell
from ..common.share import debug_plot
from ..common import constants


class Layout:
    '''Object representing the whole page, e.g. margins, blocks, shapes, spacing.'''

    def __init__(self, blocks:Blocks=None, shapes:Shapes=None, parent=None):
        ''' Initialize layout.

        Args:
            blocks (Blocks): Blocks representing text/table contents.
            shapes (Shapes): Shapes representing table border, shading and text style like underline, highlight.
            parent (Page, Cell): The object that this layout belonging to.
        '''
        self._parent = parent
        self.blocks = blocks or Blocks(parent=self)
        self.shapes = shapes or Shapes(parent=self)        
        self._tables_constructor = TablesConstructor(parent=self) # table parser


    @property
    def is_page_level(self): return isinstance(self._parent, Page.Page)

    @property
    def is_table_level(self): return isinstance(self._parent, Cell)

    @property
    def bbox(self): return self._parent.working_bbox


    def margin(self, factor_top:float=0.5, factor_bottom:float=0.5, default_margin:float=constants.ITP):
        """Calculate layout margin.

        Args:
            factor_top (float, optional): Reduce calculated top margin to leave some free space. Defaults to 0.5.
            factor_bottom (float, optional): Reduce calculated bottom margin to leave some free space. Defaults to 0.5.
            default_margin (float, optional): Default margin. Defaults to ``constants.ITP``.

        Returns:
            tuple: ``(left, right, top, bottom)``.
        """
        # return default margin if no blocks exist
        if not self.blocks and not self.shapes: return (default_margin, ) * 4

        x0, y0, x1, y1 = self._parent.bbox
        u0, v0, u1, v1 = self.blocks.bbox | self.shapes.bbox

        # margin
        left = max(u0-x0, 0.0)
        right = max(x1-u1-constants.MINOR_DIST, 0.0)
        top = max(v0-y0, 0.0)
        bottom = max(y1-v1, 0.0)

        # reduce calculated top/bottom margin to leave some free space
        top *= factor_top
        bottom *= factor_bottom

        # use normal margin if calculated margin is large enough
        return (
            min(default_margin, left), 
            min(default_margin, right), 
            min(default_margin, top), 
            min(default_margin, bottom)
            )


    def store(self):
        '''Store parsed layout in dict format.'''
        return {
            'blocks': self.blocks.store(),
            'shapes': self.shapes.store(),
        }


    def restore(self, data:dict):
        '''Restore Layout from parsed results.'''
        self.blocks.restore(data.get('blocks', []))
        self.shapes.restore(data.get('shapes', []))
        return self

    
    def parse(self, settings:dict=None):
        '''Parse layout.'''
        # preprocessing all blocks and shapes from page level, 
        # e.g. change block order, clean negative block
        if self.is_page_level: self.clean_up(settings)

        self.merge_blocks(settings)
        self.detect_semantic_shapes()

        # top-down
        print('xxx')
    
        # parse table blocks: 
        #  - table structure/format recognized from rectangles
        self.parse_lattice_tables(settings)
        
        #  - cell contents extracted from text blocks
        self.parse_stream_tables(settings)

        # parse text format, e.g. highlight, underline
        self.parse_text_format()
        
        # paragraph / line spacing        
        self.parse_spacing(settings)

        # parse sub-layout, i.e. layout under table block
        for block in filter(lambda e: e.is_table_block(), self.blocks):
            block.parse(settings)


    # ----------------------------------------------------
    # wraping Blocks and Shapes methods
    # ----------------------------------------------------
    def clean_up(self, settings):
        '''Clean up blocks and shapes, e.g. remove negative or duplicated instances.'''
        # clean up blocks first
        self.blocks.clean_up()

        # clean up shapes
        self.shapes.clean_up(settings['max_border_width'], 
                            settings['shape_merging_threshold'],
                            settings['shape_min_dimension'])
    
    
    @debug_plot('Cleaned Blocks')
    def merge_blocks(self, settings):
        '''pre-process blocks for layout parsing.'''
        self.blocks.merge(settings['float_image_ignorable_gap'],
                            settings['line_overlap_threshold'],
                            settings['line_merging_threshold'])

        return self.blocks    
    

    @debug_plot('Cleaned Shapes')
    def detect_semantic_shapes(self):
        '''Detect semantic type based on the positions to text blocks, 
        e.g. table border v.s. text underline, table shading v.s. text highlight.
        
        .. note::
            Stroke shapes are grouped on connectivity to each other, but in some cases, 
            the gap between borders and underlines/strikes are very close, which leads
            to an incorrect table structure. So, it's required to distinguish them in
            advance, though we needn't to ensure 100% accuracy.
        '''
        self.shapes.detect_initial_categories()
        return self.shapes    


    @debug_plot('Lattice Table Structure')
    def parse_lattice_tables(self, settings):
        '''Parse table structure based on explicit stroke shapes.'''
        return self._tables_constructor.lattice_tables(
                            settings['connected_border_tolerance'],
                            settings['min_border_clearance'],
                            settings['max_border_width'],
                            settings['float_layout_tolerance'],
                            settings['line_overlap_threshold'],
                            settings['line_merging_threshold'],
                            settings['line_separate_threshold'])


    @debug_plot('Stream Table Structure')
    def parse_stream_tables(self, settings):
        '''Parse table structure based on layout of blocks.'''
        return self._tables_constructor.stream_tables(
                            settings['min_border_clearance'],
                            settings['max_border_width'],
                            settings['float_layout_tolerance'],
                            settings['line_overlap_threshold'],
                            settings['line_merging_threshold'],
                            settings['line_separate_threshold'])


    @debug_plot('Final Layout')
    def parse_text_format(self):
        '''Parse text format in both page and table context.'''
        text_shapes =   list(self.shapes.text_underlines_strikes) + \
                        list(self.shapes.text_highlights) + \
                        list(self.shapes.hyperlinks)
        self.blocks.parse_text_format(text_shapes)
        return self.blocks
 

    def parse_spacing(self, settings):
        '''Calculate external and internal vertical space for Blocks instances.'''
        self.blocks.parse_spacing(
                            settings['line_separate_threshold'],
                            settings['line_free_space_ratio_threshold'],
                            settings['lines_left_aligned_threshold'],
                            settings['lines_right_aligned_threshold'],
                            settings['lines_center_aligned_threshold'])
