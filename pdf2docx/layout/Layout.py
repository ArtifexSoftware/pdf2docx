# -*- coding: utf-8 -*-

'''Layout depends on Blocks and Shapes.

**Layout** here refers to the content and position of text, image and table. The target is to convert
source blocks and shapes to a *flow layout* that can be re-created as docx elements like paragraph and
table. In this library, The page structure/layout is maintained by ``TableBlock``. So, detecting and 
parsing table block is the principle steps.

The layout parsing idea:

1. Clean source blocks and shapes in Page level. The main step is to merge blocks 
   horizontally considering flow layout (only one block in horizontal direction).
#. Parse Section and Column layout in Page level. This step is just to detect whether 
   a two-columns layout.
#. Parse table layout in Column level.
    (a) Detect explicit tables first based on shapes. 
    (#) Then, detect stream tables based on original text blocks and parsed explicit tables.
    (#) Move table contained blocks (text block or explicit table) to associated cell-layout.
#. Parse text format for text blocks in current layout.
#. Repeat above steps for cell-layout in parsed table level.
'''

from ..common import constants
from ..text.TextBlock import TextBlock
from ..shape.Shapes import Shapes


class Layout:
    '''Blocks and shapes structure and formats.'''

    def __init__(self, blocks=None, shapes=None):
        ''' Initialize layout.

        Args:
            blocks (Blocks): Blocks representing text/table contents.
            shapes (Shapes): Shapes representing table border, shading and text style like underline, highlight.
            parent (Page, Column, Cell): The object that this layout belonging to.
        '''
        from .Blocks import Blocks # avoid import conflicts
        from ..table.TablesConstructor import TablesConstructor

        self.blocks = Blocks(instances=blocks, parent=self)
        self.shapes = Shapes(instances=shapes, parent=self)        
        self._table_parser = TablesConstructor(parent=self) # table parser


    def working_bbox(self, *args, **kwargs):
        '''Working bbox of current Layout.'''
        raise NotImplementedError


    def constains(self, *args, **kwargs):
        '''Whether given element is contained in this layout.'''
        raise NotImplementedError


    def store(self):
        '''Store parsed layout in dict format.'''
        return {
            'blocks': self.blocks.store(),
            'shapes': self.shapes.store()
        }


    def restore(self, data:dict):
        '''Restore Layout from parsed results.'''
        self.blocks.restore(data.get('blocks', []))
        self.shapes.restore(data.get('shapes', []))
        return self


    def assign_blocks(self, blocks:list):
        '''Add blocks to this layout. 
        
        Args:
            blocks (list): a list of text/table block to add.
        
        .. note::
            If a text block is partly contained, it must deep into line -> span -> char.
        '''
        for block in blocks: self._assign_block(block)


    def assign_shapes(self, shapes:list):
        '''Add shapes to this cell. 
        
        Args:
            shapes (list): a list of Shape instance to add.
        '''
        # add shape if contained in cell
        for shape in shapes:
            if self.working_bbox & shape.bbox: self.shapes.append(shape)


    def clean_up(self, settings:dict):
        '''Clean up blocks and shapes, e.g. 
        
        * remove negative or duplicated instances,
        * merge text blocks horizontally (preparing for layout parsing)
        * detect semantic type of shapes
        '''
        # clean up blocks first
        self.blocks.clean_up(settings['float_image_ignorable_gap'],
                        settings['line_overlap_threshold'],
                        settings['line_merging_threshold'])

        # clean up shapes        
        self.shapes.clean_up(settings['max_border_width'], 
                        settings['shape_merging_threshold'],
                        settings['shape_min_dimension'])
        
        # check shape semantic type
        self.shapes.detect_initial_categories()


    def parse(self, settings:dict):
        '''Parse layout.

        Args:
            settings (dict): Layout parsing parameters.
        '''
        # parse tables
        self._parse_table_layout(settings)

        # improve layout after table parsing
        self._improve_layout(settings)

        # parse text format in current layout
        self._parse_text_format(settings)

        # parse sub-layout, i.e. cell layouts under table block
        for block in filter(lambda e: e.is_table_block(), self.blocks):
            block.parse(settings)


    def _assign_block(self, block):
        '''Add block to this cell. 
        
        Args:
            block (TextBlock, TableBlock): Text/table block to add. 
        '''
        # add block directly if fully contained in cell
        if self.contains(block, constants.FACTOR_ALMOST):
            self.blocks.append(block)
            return
        
        # add nothing if no intersection
        if not self.bbox & block.bbox: return

        # otherwise, further check lines in text block
        if not block.is_text_image_block():  return
        
        # NOTE: add each line as a single text block to avoid overlap between table block and combined lines
        split_block = TextBlock()
        lines = [line.intersects(self.bbox) for line in block.lines]
        split_block.add(lines)
        self.blocks.append(split_block)


    def _parse_table_layout(self, settings:dict):
        '''Parse table layout: 
        
        * detect explicit tables first based on shapes, 
        * then stream tables based on original text blocks and parsed explicit tables;
        * move table contained blocks (text block or explicit table) to associated cell layout.
        '''
        # check shape semantic type
        self.shapes.detect_initial_categories()
        
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
    

    def _improve_layout(self, settings):
        '''Adjust layout after table parsing:

        * split blocks in current level back to original layout if possible
        * merge adjacent and similar blocks in vertical direction
        '''
        # blocks are joined horizontally in clean up stage, now change back to original layout
        self.blocks.split_back(
            settings['float_layout_tolerance'], 
            settings['line_separate_threshold'])
        
        # one paragraph may be split in separate blocks by `PyMuPDF`, now merge them together
        # by checking vertical distance
        self.blocks.join_vertically(
            settings['block_merging_threshold']
        )
    

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
                        settings['line_break_width_ratio'],
                        settings['line_break_free_space_ratio'],
                        settings['lines_left_aligned_threshold'],
                        settings['lines_right_aligned_threshold'],
                        settings['lines_center_aligned_threshold'])