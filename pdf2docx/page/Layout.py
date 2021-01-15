# -*- coding: utf-8 -*-

'''Layout depends on Blocks and Shapes.

**Layout** here refers to the content and position of text, image and table. The target is to convert
source blocks and shapes to a *flow layout* that can be re-created as docx elements like paragraph and
table. In this library, The page structure/layout is maintained by ``TableBlock``. So, detecting and 
parsing table block is the principle steps.

The layout parsing idea:

1. Clean source blocks and shapes (run only once in Page level). The main step is to merge blocks 
   horizontally considering flow layout (only one block in horizontal direction).
#. Parse layout top-down (run only once in Page level). There's a lack of information from top level, 
   so this step is just to detect whether a two-columns page layout.
#. Parse layout bottom-up.
    (a) Detect explicit tables first based on shapes. 
    (#) Then, detect stream tables based on original text blocks and parsed explicit tables.
    (#) Move table contained blocks (text block or explicit table) to associated cell-layout.
#. Parse text format for text blocks in current layout.
#. Repeat above steps for cell-layout in parsed table level.
'''

from . import Page
from .Blocks import Blocks
from ..shape.Shapes import Shapes
from ..table.TablesConstructor import TablesConstructor


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
        self._table_parser = TablesConstructor(parent=self) # table parser
    

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
        # parse layout in top down mode
        self._parse_layout_top_down(settings)
    
        # parse layout in bottom up mode
        self._parse_layout_bottom_up(settings)

        # parse text format in current layout
        self._parse_text_format(settings)

        # parse sub-layout, i.e. cell layouts under table block
        for block in filter(lambda e: e.is_table_block(), self.blocks):
            block.parse(settings)


    # ----------------------------------------------------
    # wraping Blocks and Shapes methods
    # ----------------------------------------------------
    def clean_up(self, settings:dict):
        '''Clean up blocks and shapes, e.g. 
        
        * remove negative or duplicated instances,
        * merge text blocks horizontally (preparing for layout parsing)
        * detect semantic type of shapes

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

        # detect semantic type of shapes
        self.shapes.detect_initial_categories()


    def _parse_layout_top_down(self, settings:dict):
        '''Parse layout top-down (Page level only).'''
        if not isinstance(self._parent, Page.Page): return
        self._table_parser.page_layout_table()


    def _parse_layout_bottom_up(self, settings:dict):
        '''Parse layout bottom-up: 
        
        * detect explicit tables first based on shapes, 
        * then stream tables based on original text blocks and parsed explicit tables;
        * move table contained blocks (text block or explicit table) to associated cell layout.
        '''
        # parse table structure/format recognized from explicit shapes
        self._table_parser.lattice_tables(
                        settings['connected_border_tolerance'],
                        settings['min_border_clearance'],
                        settings['max_border_width'])
        
        # parse table structure based on implicit layout of text blocks
        self._table_parser.stream_tables(
                        settings['min_border_clearance'],
                        settings['max_border_width'],
                        settings['float_layout_tolerance'],
                        settings['line_separate_threshold'])
    

    def _parse_text_format(self, settings:dict):
        '''Parse text format, e.g. text highlight, paragraph indentation. 
        '''
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