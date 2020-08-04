# -*- coding: utf-8 -*-

'''
A group of Text/Image or Table block.
@created: 2020-07-22
@author: train8808@gmail.com
'''

from ..common.Collection import Collection
from ..common.base import BlockType
from ..common import utils
from ..common.Block import Block
from ..text.TextBlock import TextBlock
from ..text.ImageBlock import ImageBlock
from ..table.TableBlock import TableBlock
from ..shape.Rectangle import Rectangle
from ..shape import Rectangles # avoid conflits:

class Blocks(Collection):
    '''Block collections.'''
    def __init__(self, instances:list=[], parent=None) -> None:
        ''' A collection of TextBlock and TableBlock instances. 
            ImageBlock is converted to ImageSpan contained in TextBlock.'''
        self._parent = parent # type: Block
        self._instances = []  # type: list[TextBlock or TableBlock]
    
        # Convert all original image blocks to text blocks, i.e. ImageSpan,
        # So we can focus on single TextBlock later on; TableBlock is also combination of TextBlocks.
        for block in instances:
            if isinstance(block, ImageBlock):
                text_block = block.to_text_block()
                self._instances.append(text_block)
            else:
                self._instances.append(block)


    def from_dicts(self, raws:list):
        for raw_block in raws:
            block_type = raw_block.get('type', -1) # type: int
            
            # image block -> text block
            if block_type==BlockType.IMAGE.value:
                block = ImageBlock(raw_block).to_text_block()
            
            # text block
            elif block_type == BlockType.TEXT.value:
                block = TextBlock(raw_block)

            # table block
            elif block_type in (BlockType.EXPLICIT_TABLE.value, BlockType.IMPLICIT_TABLE.value):
                block = TableBlock(raw_block)
            
            else:
                block = None            
            
            # add to list
            self.append(block)
        
        return self


    def text_blocks(self, level=0):
        '''Get text blocks contained in this Collection.
            ---
            Args:
              - level: 
                - 0: text blocks in top level only
                - 1: text blocks deep to table level
        '''
        # top level
        blocks = list(filter(
            lambda block: block.is_text_block(), self._instances))
        
        # table cell level
        if level>0:
            for table in self.table_blocks:
                for row in table:
                    for cell in row:
                        blocks.extend(cell.blocks.text_blocks(level))
        return blocks
    

    def image_spans(self, level=0):
        '''Get ImageSpan contained in this Collection.             
            ---
            Args:
              - level: 
                - 0: image span contained in top level text blocks
                - 1: image span deep to table blocks level

            NOTE:
            No ImageBlock exists in this collection since it's already converted to text block.
        '''
        
        # image span in top text block
        spans = []
        for block in self.text_blocks(level=0):
            spans.extend(block.lines.image_spans)
        
        # image span in table block level
        if level>0:
            for table in self.table_blocks:
                for row in table:
                    for cell in row:
                        spans.extend(cell.blocks.image_spans(level))        
        return spans


    @property
    def explicit_table_blocks(self):
        '''Get explicit table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_explicit_table_block(), self._instances))

    @property
    def implicit_table_blocks(self):
        '''Get implicit table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_implicit_table_block(), self._instances))

    @property
    def table_blocks(self):
        '''Get table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_table_block(), self._instances))


    def clean(self):
        '''Preprocessing for blocks initialized from the raw layout.'''

        # remove negative blocks
        self._instances = list(filter(
            lambda block: all(x>=0 for x in block.bbox_raw), self._instances))

        # remove blocks with transformed text: text direction is not (1, 0) or (0, -1)
        self._instances = list(filter(
            lambda block: block.is_horizontal or block.is_vertical, self._instances))
           
        # merge blocks horizontally, e.g. remove overlap blocks, since no floating elements are supported
        # NOTE: It's to merge blocks in physically horizontal direction, i.e. without considering text direction.
        self.merge_horizontally(text_direction=False)

        return True


    def parse_table_content(self):
        '''Add Text/Image block lines to associated cells of Table blocks.'''
        # table blocks
        tables = self.table_blocks
        if not tables: return False

        # collect blocks in table region        
        blocks_in_tables = [[] for _ in tables] # type: list[list[Block]]
        blocks = []   # type: list[Block]
        for block in self._instances:
            # ignore table block
            if block.is_table_block(): continue

            # collect blocks contained in table region
            for table, blocks_in_table in zip(tables, blocks_in_tables):
                if table.bbox.intersects(block.bbox):
                    blocks_in_table.append(block)
                    break
            
            # normal blocks
            else:
                blocks.append(block)

        # assign blocks to associated cells
        # ATTENTION: no nested table is considered
        for table, blocks_in_table in zip(tables, blocks_in_tables):
            for row in table:
                for cell in row:
                    if not cell: continue
                    # check candidate blocks
                    for block in blocks_in_table:                        
                        cell.add(block)

                    # merge blocks if contained blocks found
                    cell.blocks.merge_horizontally().split_vertically()

        # sort in natural reading order and update layout blocks
        blocks.extend(tables)
        self.reset(blocks).sort_in_reading_order()

        return True


    def collect_table_content(self):
        ''' Collect bbox, e.g. Line of TextBlock, which may contained in an implicit table region.
            
            Table may exist on the following conditions:
             - (a) lines in blocks are not connected sequently -> determined by current block only
             - (b) multi-blocks are in a same row (horizontally aligned) -> determined by two adjacent blocks
        '''      

        res = [] # type: list[Rectangles.Rectangles]

        table_lines = [] # type: list[Rect]
        new_line = True
        num = len(self._instances)

        for i in range(num):
            block =self._instances[i]
            next_block =self._instances[i+1] if i<num-1 else Block()

            table_end = False
            
            # there is gap between these two criteria, so consider condition (a) only if if it's the first block in new row
            # (a) lines in current block are connected sequently?
            # yes, counted as table lines
            if new_line and block.contains_discrete_lines(): 
                table_lines.extend(block.sub_bboxes)                
                # update line status
                new_line = False            

            # (b) multi-blocks are in a same row: check layout with next block?
            # yes, add both current and next blocks
            if block.horizontally_align_with(next_block):
                # if it's start of new table row: add the first block
                if new_line: 
                    table_lines.extend(block.sub_bboxes)
                
                # add next block
                table_lines.extend(next_block.sub_bboxes)

                # update line status
                new_line = False

            # no, consider to start a new row
            else:
                # table end 
                # - if it's a text line, i.e. no more than one block in a same line
                # - or the next block is also a table
                if new_line or block.is_table_block():
                    table_end = True

                # update line status            
                new_line = True

            # NOTE: close table detecting manually if last block
            if i==num-1:
                table_end = True

            # end of current table
            if table_lines and table_end: 
                # from fitz.Rect to Rectangle type
                rects = [Rectangle().update(line) for line in table_lines]
                res.append(Rectangles.Rectangles(rects))

                # reset table_blocks
                table_lines = []
        
        return res


    def parse_vertical_spacing(self, bbox:tuple):
        ''' Calculate external and internal vertical space for text blocks.
        
            - paragraph spacing is determined by the vertical distance to previous block. 
              For the first block, the reference position is top margin.
            
                It's easy to set before-space or after-space for a paragraph with python-docx,
                so, if current block is a paragraph, set before-space for it; if current block 
                is not a paragraph, e.g. a table, set after-space for previous block (generally, 
                previous block should be a paragraph).
            
            - line spacing is defined as the average line height in current block.

            ---
            Args:
            - bbox: reference boundary of all the blocks
        '''
        if not self._instances: return

        # check text direction
        # normal reading direction by default, i.e. from left to right, 
        # the reference boundary is top border, i.e. bbox[1].
        # regarding vertical text direction, e.g. from bottom to top, left border bbox[0] is the reference
        idx = 1 if self.is_horizontal else 0

        ref_block = self._instances[0]
        ref_pos = bbox[idx]

        for block in self._instances:
            # NOTE: the table bbox is counted on center-line of outer borders, so a half of top border
            # size should be excluded from the calculated vertical spacing
            if block.is_table_block():
                dw = block[0][0].border_width[0] / 2.0 # use top border of the first cell

                # calculate vertical spacing of blocks under this table
                block.parse_vertical_spacing()
            
            else:
                dw = 0.0

            start_pos = block.bbox_raw[idx] - dw
            para_space = max(start_pos-ref_pos, 0.0) # ignore negative value

            # ref to current (paragraph): set before-space for paragraph
            if block.is_text_block():

                # spacing before this paragraph
                block.before_space = para_space

                # calculate average line spacing in paragraph
                block.parse_line_spacing()

            # if ref to current (image): set before-space for paragraph
            elif block.is_image_block():
                block.before_space = para_space

            # ref (paragraph/image) to current: set after-space for ref paragraph        
            elif ref_block.is_text_block() or ref_block.is_image_block():
                ref_block.after_space = para_space

            # situation with very low probability, e.g. ref (table) to current (table)
            # we can't set before space for table in docx, but the tricky way is to
            # create a empty paragraph and set paragraph line spacing and before space
            else:
                block.before_space = para_space

            # update reference block        
            ref_block = block
            ref_pos = ref_block.bbox_raw[idx+2] + dw # assume same bottom border with top one


    def merge_horizontally(self, text_direction=True):
        '''Merge blocks aligned horizontally group by group.
            ---
            Args:
              - text_direction: whether consider text direction.
                if True, detect text direction based on line direction;
                if False, use default direction: from left to right.
        '''
        # get horizontally aligned blocks group by group
        fun = lambda a,b: a.horizontally_align_with(b, factor=0.0, text_direction=text_direction)
        groups = self.group(fun)
        
        # merge blocks in each group
        blocks = []
        for blocks_collection in groups:
            block = blocks_collection._merge_one()
            blocks.append(block)

        self.reset(blocks)

        return self


    def split_vertically(self):
        '''Split block lines in vertical direction.'''
        blocks = [] # type: list[TextBlock]
        for block in self._instances:
            blocks.extend(block.split())
        
        self.reset(blocks)

        return self


    def parse_text_format(self, rects):
        '''Parse text format with style represented by rectangles.
            ---
            Args:
              - rects: Rectangles, potential styles applied on blocks

            NOTE: `parse_text_format` must be implemented by TextBlock, ImageBlock and TableBlock.
        '''
        flag = False
        for block in self._instances:
            if block.parse_text_format(rects):
                flag = True        
        return flag


    def page_margin(self, width:float, height:float):
        '''Calculate page margin:
            - left: MIN(bbox[0])
            - right: MIN(left, width-max(bbox[2]))
            - top: MIN(bbox[1])
            - bottom: height-MAX(bbox[3])
            ---
            Args:
              - width: page width
              - height: page height
        '''
        # return normal page margin if no blocks exist
        if not self._instances:
            return (utils.ITP, ) * 4 # 1 Inch = 72 pt

        # check candidates for left margin:
        list_bbox = list(map(lambda x: x.bbox, self._instances))

        # left margin 
        left = min(map(lambda x: x.x0, list_bbox))

        # right margin
        x_max = max(map(lambda x: x.x1, list_bbox))
        right = width-x_max-utils.DM*2.0 # consider tolerance: leave more free space
        right = min(right, left)     # symmetry margin if necessary
        right = max(right, 0.0)      # avoid negative margin

        # top/bottom margin
        top = min(map(lambda x: x.y0, list_bbox))
        bottom = height-max(map(lambda x: x.y1, list_bbox))
        bottom = max(bottom, 0.0)

        # reduce calculated bottom margin -> more free space left,
        # to avoid page content exceeding current page
        bottom *= 0.5

        # use normal margin if calculated margin is large enough
        return (
            min(utils.ITP, left), 
            min(utils.ITP, right), 
            min(utils.ITP, top), 
            min(utils.ITP, bottom)
            )


    def _merge_one(self):
        ''' Merge all text blocks into one text block.
            
            NOTE:            
            Lines in text block must have same property, e.g. height, vertical distance, 
            because average line height is used when create docx. However, the contained lines 
            may be not reasonable after this step. So, this is just a pre-processing step focusing 
            on processing lines in horizontal direction, e.g. merging inline image to its text line.
            A further step, e.g. split lines vertically, must be applied before final making docx.
        '''
        # combine all lines into a TextBlock
        final_block = TextBlock()
        for block in self._instances:
            if not block.is_text_block(): continue
            for line in block.lines:
                final_block.add(line)

        # merge lines/spans contained in this textBlock
        final_block.lines.merge()

        return final_block

