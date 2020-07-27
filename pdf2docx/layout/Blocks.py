# -*- coding: utf-8 -*-

'''
A group of Text/Image or Table block.
@created: 2020-07-22
@author: train8808@gmail.com
'''

from ..common.base import BlockType
from ..common import utils
from ..common.Block import Block
from ..text.TextBlock import TextBlock
from ..text.ImageBlock import ImageBlock
from ..shape.Rectangle import Rectangle


class Blocks:
    '''Text block.'''
    def __init__(self, raws:list=[]):
        ''' Construct Text blocks (image blocks included) from a list of raw block dict.'''
        # initialize blocks
        self._blocks = [] # type: list [TextBlock or ImageBlock or TableBlock]
        for raw in raws:
            block = None
            # image block
            block_type = raw.get('type', -1) # type: int
            if block_type==BlockType.IMAGE.value:
                block = ImageBlock(raw)
            # text block
            elif block_type == BlockType.TEXT.value:
                block = TextBlock(raw)
            
            # add to list
            if block: self._blocks.append(block)


    def __getitem__(self, idx):
        try:
            blocks = self._blocks[idx]
        except IndexError:
            msg = f'Block index {idx} out of range'
            raise IndexError(msg)
        else:
            return blocks

    def __iter__(self):
        return (block for block in self._blocks)

    def __len__(self):
        return len(self._blocks)

    def reset(self, blocks:list):
        self._blocks = blocks

    def extend(self, blocks:list):
        self._blocks.extend(blocks)

    def append(self, block:Block):
        if block: self._blocks.append(block)

    def store(self):
        return [ block.store() for block in self._blocks]

    def preprocessing(self):
        '''Preprocessing for blocks initialized from the raw layout.'''

        # remove negative blocks
        self._blocks = list(filter(
            lambda block: all(x>0 for x in block.bbox_raw), self._blocks))

        # remove blocks with transformed text: text direction is not (1, 0)
        self._blocks = list(filter(
            lambda block: block.is_image_block() or all(line.dir[0]==1.0 for line in block.lines), self._blocks))

        # remove overlap blocks: no floating elements are supported
        self.remove_floating_images()        
        
        # sort in reading direction: from up to down, from left to right
        self._blocks.sort(
            key=lambda block: (block.bbox.y0, block.bbox.x0))
            
        # merge inline images into text block
        self.merge_inline_images()

        return True


    def parse_table_content(self):
        '''Add block lines to associated cells.'''

        # table blocks
        tables = list(filter(lambda block: block.is_table_block(), self._blocks))
        if not tables: return False

        # collect blocks in table region        
        blocks_in_tables = [[] for _ in tables] # type: list[list[Block]]
        blocks = []   # type: list[Block]
        for block in self._blocks:
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
                    cell.blocks.merge()

        # sort in natural reading order and update layout blocks
        blocks.extend(tables)
        blocks.sort(key=lambda block: (block.bbox.y0, block.bbox.x0))

        self._blocks = blocks

        return True


    def collect_table_content(self):
        ''' Collect bbox, e.g. Line of TextBlock, which may contained in an implicit table region.
            
            Table may exist on the following conditions:
             - (a) lines in blocks are not connected sequently -> determined by current block only
             - (b) multi-blocks are in a same row (horizontally aligned) -> determined by two adjacent blocks
        '''  

        res = [] # type: list[list[Rectangle]]

        table_lines = [] # type: list[Rect]
        new_line = True
        num = len(self._blocks)

        for i in range(num):
            block =self._blocks[i]
            next_block =self._blocks[i+1] if i<num-1 else Block()

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
            if utils.is_horizontal_aligned(block.bbox, next_block.bbox):
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
                res.append(rects)

                # reset table_blocks
                table_lines = []
        
        return res


    def parse_vertical_spacing(self, Y0:float):
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
            - Y0: top border, i.e. start reference of all blocks
        '''
        if not self._blocks: return

        ref_block = self._blocks[0]
        ref_pos = Y0
        for block in self._blocks:

            dw = 0.0

            # NOTE: the table bbox is counted on center-line of outer borders, so a half of top border
            # size should be excluded from the calculated vertical spacing
            if block.is_table_block() and block[0][0]:
                dw = block[0][0].border_width[0] / 2.0 # use top border of the first cell

                # calculate vertical spacing of blocks under this table
                block.parse_vertical_spacing()

            start_pos = block.bbox.y0 - dw
            para_space = start_pos - ref_pos

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

            # situation with very low probability, e.g. table to table
            else:
                pass

            # update reference block        
            ref_block = block
            ref_pos = block.bbox.y1 + dw


    def remove_floating_images(self):
        ''' Remove floating blocks, especially images. When a text block is floating behind 
            an image block, the background image block will be deleted, considering that 
            floating elements are not supported in python-docx when re-create the document.
        '''
        # get text/image blocks seperately, and suppose no overlap between text blocks
        text_blocks = list(
            filter( lambda block: block.is_text_block(),  self._blocks))
        image_blocks = list(
            filter( lambda block: block.is_image_block(),  self._blocks))

        # check image block: no significant overlap with any text/image blocks
        res_image_blocks = []
        for image_block in image_blocks:
            # 1. overlap with any text block?
            for text_block in text_blocks:            
                if utils.get_main_bbox(image_block.bbox, text_block.bbox, 0.75):
                    overlap = True
                    break
            else:
                overlap = False

            # yes, then this is an invalid image block
            if overlap: continue

            # 2. overlap with any valid image blocks?
            for valid_image in res_image_blocks:
                if utils.get_main_bbox(image_block.bbox, valid_image.bbox, 0.75):
                    overlap = True
                    break
            else:
                overlap = False
            
            # yes, then this is an invalid image block
            if overlap: continue

            # finally, add this image block
            res_image_blocks.append(image_block)

        # return all valid blocks
        self._blocks = []
        self._blocks.extend(text_blocks)
        self._blocks.extend(res_image_blocks)


    def merge_inline_images(self):
        '''Merge inline image blocks into text block: a block line or a line span.

           From docx aspect, inline image and text are in same paragraph; while they are not in pdf block level.
           Instead, there's overlap between these image block and text block, so have to merge image block into text block
           to avoid floating blocks.
        '''    
        # get all images blocks with index
        f = lambda item: item[1].is_image_block()
        index_images = list(filter(f, enumerate(self._blocks)))
        if not index_images: return False

        # get index of inline images: intersected with text block
        # assumption: an inline image intersects with only one text block
        index_inline = []
        num = len(index_images)
        for block in self._blocks:

            # suppose no overlap between two images
            if block.is_image_block(): continue

            # innore table block
            if block.is_table_block(): continue

            # all images found their block, then quit
            if len(index_inline)==num: break

            # check all images for current block
            for i, image in index_images:
                # an inline image belongs to only one block
                if i in index_inline: continue

                # horizontally aligned with current text block?
                # no, pass
                if not utils.is_horizontal_aligned(block.bbox, image.bbox):
                    continue

                # yes, inline image: set as a line span in block
                index_inline.append(i)
                block.merge_image(image)


        # remove inline images from top layout
        # the index of element in original list changes when any elements are removed
        # so try to delete item in reverse order
        for i in index_inline[::-1]:
            self._blocks.pop(i)

        # anything changed in this step?
        return True if index_inline else False


    def merge(self):
        '''Merge blocks aligned horizontally.'''
        res = [] # type: list[TextBlock]
        for block in self._blocks:
            # convert to text block if image block
            if block.is_image_block():
                text_block = block.to_text_block() # type: TextBlock
            else:
                text_block = block # type: TextBlock

            # add block directly if not aligned horizontally with previous block
            if not res or not utils.is_horizontal_aligned(text_block.bbox, res[-1].bbox):
                res.append(text_block)

            # otherwise, append to previous block as lines
            else:
                res[-1].lines.extend(list(text_block.lines))
        
        # sort lines in block
        for block in res:
            block.lines.sort()
        
        self._blocks = res


    def parse_text_format(self, rects):
        '''Parse text format with style represented by rectangles.
            ---
            Args:
              - rects: Rectangles, potential styles applied on blocks

            NOTE: `parse_text_format` must be implemented by TextBlock, ImageBlock and TableBlock.
        '''
        flag = False
        for block in self._blocks:
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
        if not self._blocks:
            return (utils.ITP, ) * 4 # 1 Inch = 72 pt

        # check candidates for left margin:
        list_bbox = list(map(lambda x: x.bbox, self._blocks))

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