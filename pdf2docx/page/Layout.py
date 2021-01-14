# -*- coding: utf-8 -*-

'''Layout depends on Blocks and Shapes.

There are typically two kinds of layouts, the Page layout and Cell layout.
'''

from . import Page
from .Blocks import Blocks
from ..shape.Shapes import Shapes
from ..table.TablesConstructor import TablesConstructor
from ..table.Cell import Cell


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
    def parent(self): return self._parent

    @property
    def is_page_level(self): return isinstance(self._parent, Page.Page)

    @property
    def is_table_level(self): return isinstance(self._parent, Cell)

    @property
    def bbox(self): return self._parent.working_bbox    


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


    def parse(self, settings:dict):
        '''Parse layout.

        Args:
            settings (dict): Layout parsing parameters.
        '''
        # parse layout by top-down mode
        # TODO
    
        # parse layout by bottom-up mode
        self._parse_layout_bottom_up(settings)

        # parse sub-layout, i.e. layout under table block
        for block in filter(lambda e: e.is_table_block(), self.blocks):
            block.parse(settings)


    # ----------------------------------------------------
    # wraping Blocks and Shapes methods
    # ----------------------------------------------------
    def clean_up(self, settings:dict):
        '''Clean up blocks and shapes, e.g. remove negative or duplicated instances.

        .. note::
            This method is for Page level only since it runs once for all.
        '''
        # clean up blocks first
        self.blocks.clean_up(settings['float_image_ignorable_gap'],
                            settings['line_overlap_threshold'],
                            settings['line_merging_threshold'])

        # clean up shapes        
        self.shapes.clean_up(settings['max_border_width'], 
                            settings['shape_merging_threshold'],
                            settings['shape_min_dimension'])
        
        # set page margin
        self._parent.cal_margin()

        # detect semantic type of shapes
        self.shapes.detect_initial_categories()


    def _parse_layout_bottom_up(self, settings:dict):
        '''Parse layout from bottom to up: 
        
        * detect single explicit table first,
        * then table and text block forms upper layout, i.e. stream table
        * finally parse text format and spacing.
        '''
        # parse table blocks: 
        #  - table structure/format recognized from rectangles        
        self._tables_constructor.lattice_tables(
                            settings['connected_border_tolerance'],
                            settings['min_border_clearance'],
                            settings['max_border_width'])
        
        #  - cell contents extracted from text blocks
        self._tables_constructor.stream_tables(
                            settings['min_border_clearance'],
                            settings['max_border_width'],
                            settings['float_layout_tolerance'],
                            settings['line_separate_threshold'])

        # parse text format, e.g. highlight, underline
        text_shapes =   list(self.shapes.text_underlines_strikes) + \
                        list(self.shapes.text_highlights) + \
                        list(self.shapes.hyperlinks)
        self.blocks.parse_text_format(text_shapes)
        
        # paragraph / line spacing         
        self.blocks.parse_spacing(
                            settings['line_separate_threshold'],
                            settings['line_free_space_ratio_threshold'],
                            settings['lines_left_aligned_threshold'],
                            settings['lines_right_aligned_threshold'],
                            settings['lines_center_aligned_threshold'])