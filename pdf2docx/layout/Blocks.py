# -*- coding: utf-8 -*-

'''
A group of Text/Image or Table block.
@created: 2020-07-22
@author: train8808@gmail.com
'''


from ..common.base import BlockType
from ..common import utils
from ..common.Block import Block
from ..text.TextBlock import ImageBlock, TextBlock


class Blocks:
    '''Text block.'''
    def __init__(self, raws: list [dict]) -> None:
        ''' Construct Text blocks (image blocks included) from a list of raw block dict.'''
        # initialize blocks
        self._blocks = [] # type: list [Block]
        for raw in raws:
            block = None
            # image block
            block_type = raw.get('type', -1)
            if block_type==BlockType.IMAGE:
                block = ImageBlock(raw)
            # text block
            elif block_type == BlockType.TEXT:
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

    def extend(self, blocks:list[Block]):
        self._blocks.extend(blocks)

    def append(self, block:Block):
        if block: self._blocks.append(block)

    def store(self) -> list:
        return [ block.store() for block in self._blocks]


    @utils.debug_plot('Preprocessing', plot=False)
    def preprocessing(self, **kwargs):
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


    def merge_inline_images(self) -> bool:
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


    def merge_blocks(blocks):
        '''merge blocks aligned horizontally.'''
        res = []
        for block in blocks:
            # convert to text block if image block
            if is_image_block(block):
                text_block = convert_image_to_text_block(block)
            else:
                text_block = block

            # add block directly if not aligned horizontally with previous block
            if not res or not utils.is_horizontal_aligned(text_block['bbox'], res[-1]['bbox']):
                res.append(text_block)

            # otherwise, append to previous block as lines
            else:
                res[-1]['lines'].extend(text_block['lines'])

                # update bbox
                res[-1]['bbox'] = (
                    min(res[-1]['bbox'][0], text_block['bbox'][0]),
                    min(res[-1]['bbox'][1], text_block['bbox'][1]),
                    max(res[-1]['bbox'][2], text_block['bbox'][2]),
                    max(res[-1]['bbox'][3], text_block['bbox'][3])
                    )
        
        # sort lines in block
        for block in res:
            sort_lines(block) 

        return res


    def sort_lines(block):
        ''' Sort lines in block.        

            In the following example, A should come before B.
                            +-----------+
                +---------+  |           |
                |   A     |  |     B     |
                +---------+  +-----------+

            Steps:
                (a) sort lines in reading order, i.e. from top to bottom, from left to right.
                (b) group lines in row
                (c) sort lines in row: from left to right
        '''
        # sort in reading order
        block['lines'].sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))

        # split lines in separate row
        lines_in_rows = [] # [ [lines in row1], [...] ]
        for line in block.get('lines', []):

            # add lines to a row group if not in same row with previous line
            if not lines_in_rows or not utils.in_same_row(line['bbox'], lines_in_rows[-1][-1]['bbox']):
                lines_in_rows.append([line])
            
            # otherwise, append current row group
            else:
                lines_in_rows[-1].append(line)
        
        # sort lines in each row
        lines = []
        for row in lines_in_rows:
            row.sort(key=lambda line: line['bbox'][0])
            lines.extend(row)

        block['lines'] = lines


    def convert_image_to_text_block(image):
        '''convert image block to text block: a span'''
        # convert image as a span in line
        image_line = {
            "wmode": 0,
            "dir"  : (1, 0),
            "bbox" : image['bbox'],
            "spans": [image]
            }
        
        # insert line to block
        block = {
            'type': -1,
            'bbox': image['bbox'],
            'lines': [image_line]
        }

        # set text block
        set_text_block(block)

        return block    


    def parse_vertical_spacing(self, Y0:float, Y1:float):
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
            - Y0, Y1: the blocks are restricted in a vertical range within (Y0, Y1)
        '''
        if not self._blocks: return

        ref_block = self._blocks[0]
        ref_pos = Y0
        for block in self._blocks:

            dw = 0.0

            # NOTE: the table bbox is counted on center-line of outer borders, so a half of top border
            # size should be excluded from the calculated vertical spacing
            if block.is_table_block() and block.cells[0][0]:
                dw = block.cells[0][0].border_width[0] / 2.0 # use top border of the first cell

            start_pos = block.bbox.y0 - dw
            para_space = start_pos - ref_pos

            # ref to current (paragraph): set before-space for paragraph
            if block.is_text_block():

                # spacing before this paragraph
                block.before_space = para_space

                # calculate average line spacing in paragraph
                # e.g. line-space-line-space-line, excepting first line -> space-line-space-line,
                # so an average line height = space+line
                # then, the height of first line can be adjusted by updating paragraph before-spacing.
                # 
                ref_bbox = None
                count = 0
                for line in block.lines:
                    # count of lines
                    if not utils.in_same_row(line.bbox, ref_bbox):
                        count += 1
                    # update reference line
                    ref_bbox = line.bbox            
                
                _, y0, _, y1 = block.lines[0].bbox_raw   # first line
                first_line_height = y1 - y0
                block_height = block.bbox.y1-block.bbox.y0
                if count > 1:
                    line_space = (block_height-first_line_height)/(count-1)
                else:
                    line_space = block_height
                block.line_space = line_space

                # if only one line exists, don't have to set line spacing, use default setting,
                # i.e. single line instead
                if count > 1:
                    # since the line height setting in docx may affect the original bbox in pdf, 
                    # it's necessary to update the before spacing:
                    # taking bottom left corner of first line as the reference point                
                    para_space = para_space + first_line_height - line_space
                    block.before_space = para_space

                # adjust last block to avoid exceeding current page <- seems of no use
                free_space = Y1-(ref_pos+para_space+block_height) 
                if free_space<=0:
                    block.before_space = para_space+free_space-utils.DM*2.0

            # if ref to current (image): set before-space for paragraph
            elif block.is_image_block():
                block.before_space = para_space

            # ref (paragraph/image) to current: set after-space for ref paragraph        
            elif ref_block.is_table_block():
                ref_block.after_space = para_space

            # situation with very low probability, e.g. table to table
            else:
                pass

            # update reference block        
            ref_block = block
            ref_pos = block.bbox.y1 + dw