# -*- coding: utf-8 -*-

'''
A group of Text/Image or Table block.
@created: 2020-07-22
@author: train8808@gmail.com
'''

from docx.shared import Pt
from ..common.constants import DM
from ..common.Collection import Collection
from ..common.base import BlockType
from ..common.Block import Block
from ..common.docx import reset_paragraph_format
from ..text.TextBlock import TextBlock
from ..text.Line import Line
from ..text.Lines import Lines
from ..image.ImageBlock import ImageBlock
from ..table.TableBlock import TableBlock
from ..table.Cell import Cell
from . import Layout


class Blocks(Collection):
    '''Block collections.'''
    def __init__(self, instances:list=[], parent=None):
        ''' A collection of TextBlock and TableBlock instances. 
            ImageBlock is converted to ImageSpan contained in TextBlock.'''
        self._parent = parent # type: Block
        self._instances = []  # type: list[TextBlock or TableBlock]
    
        # Convert all original image blocks to text blocks, i.e. ImageSpan,
        # So we can focus on single TextBlock later on; TableBlock is also combination of TextBlocks.
        for block in instances:
            if isinstance(block, ImageBlock):
                text_block = block.to_text_block()
                self.append(text_block)
            else:
                self.append(block)

    def _update(self, block:Block):
        ''' Override. The parent of block is generally Layout or Cell, which is not necessary to 
            update its bbox. So, do nothing but required here.
        '''
        pass


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
            elif block_type in (BlockType.LATTICE_TABLE.value, BlockType.STREAM_TABLE.value):
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
    def lattice_table_blocks(self):
        '''Get lattice table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_lattice_table_block(), self._instances))

    @property
    def stream_table_blocks(self):
        '''Get stream table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_stream_table_block(), self._instances))

    @property
    def table_blocks(self):
        '''Get table blocks contained in this Collection.'''
        return list(filter(
            lambda block: block.is_table_block(), self._instances))


    def clean(self):
        '''Preprocess blocks initialized from the raw layout.'''

        # filter function:
        # - remove blocks out of page
        # - remove transformed text: text direction is not (1, 0) or (0, -1)
        # - remove empty blocks
        page_bbox = (0.0, 0.0, self.parent.width, self.parent.height)
        f = lambda block:   block.bbox.intersects(page_bbox) and \
                            block.text.strip() and (
                            block.is_horizontal_text or block.is_vertical_text)
        self.reset(filter(f, self._instances))
           
        # merge blocks horizontally, e.g. remove overlap blocks, since no floating elements are supported
        # NOTE: It's to merge blocks in physically horizontal direction, i.e. without considering text direction.
        self.sort_in_reading_order().join_horizontally(text_direction=False)

        return True


    def assign_table_contents(self, tables):
        '''Add Text/Image/table block lines to associated cells of given tables.'''
        if not tables: return

        # collect text blocks in table region        
        blocks_in_tables = [[] for _ in tables] # type: list[list[Block]]
        blocks = []   # type: list[Block]
        for block in self._instances:

            # lines in block for further check if necessary
            lines = block.lines if block.is_text_block() else []

            # collect blocks contained in table region
            # NOTE: there is a probability that only a part of a text block is contained in table region, 
            # while the rest is in normal block region.
            for table, blocks_in_table in zip(tables, blocks_in_tables):

                # fully contained in one table
                if table.bbox.contains(block.bbox):
                    blocks_in_table.append(block)
                    break
                
                # not possible in current table, then check next table
                elif not table.bbox.intersects(block.bbox): continue
                
                # deep into line level for text block
                elif block.is_text_block():
                    text_block = TextBlock()
                    rest_lines = []
                    for line in lines:
                        if table.bbox.intersects(line.bbox):
                            text_block.add(line)
                        else:
                            rest_lines.append(line)
                    
                    # summary
                    blocks_in_table.append(text_block)
                    if rest_lines:
                        lines = rest_lines # for forther check
                    else:
                        break # no more lines
            
            # Now, this block (or part of it) belongs to previous layout
            else:
                if block.is_table_block():
                    blocks.append(block)
                else:
                    text_block = TextBlock()
                    for line in lines:
                        text_block.add(line)
                    blocks.append(text_block)

        # assign blocks to associated cells
        for table, blocks_in_table in zip(tables, blocks_in_tables):
            # no contents for this table
            if not blocks_in_table: continue
            for row in table:
                for cell in row:
                    if not cell: continue
                    # check candidate blocks
                    for block in blocks_in_table:
                        cell.add(block)
                    # process cell blocks further: ensure converting float layout to flow layout
                    cell.blocks.join_horizontally().split_vertically()

        # sort in natural reading order and update layout blocks
        blocks.extend(tables)
        self.reset(blocks).sort_in_reading_order()


    def collect_stream_lines(self):
        ''' Collect lines of text block, which may contained in a stream table region.

            NOTE: PyMuPDF may group multi-lines in a row as a text block while each line belongs to different
            cell. So, deep into line level here when collecting table contents regions.
            
            Table may exist on the following conditions:
             - (a) lines in blocks are not connected sequently -> determined by current block only
             - (b) multi-blocks are in a same row (horizontally aligned) -> determined by two adjacent blocks
        '''

        res = [] # type: list[Lines]

        # get sub-lines from block
        def sub_lines(block):
            return block.lines if block.is_text_block() else [Line().update(block.bbox)]

        new_line = True
        num = len(self._instances)
        table_lines = Lines()
        for i in range(num):
            block = self._instances[i]
            next_block = self._instances[i+1] if i<num-1 else Block()

            table_end = False
            
            # there is gap between these two criteria, so consider condition (a) only if it's the first block in new row.
            # (a) lines in current block are connected sequently?
            # yes, counted as table lines
            if new_line and block.contains_discrete_lines(): 
                table_lines.extend(sub_lines(block))  # deep into line level
                
                # update line status
                new_line = False            

            # (b) multi-blocks are in a same row: check layout with next block?
            # yes, add both current and next blocks
            if block.horizontally_align_with(next_block, factor=0.1):
                # if it's start of new table row: add the first block
                if new_line: table_lines.extend(sub_lines(block))
                
                # add next block
                table_lines.extend(sub_lines(next_block))

                # update line status
                new_line = False

            # no, consider to start a new row
            else:
                # table end if it's a text line, i.e. no more than one block in a same line
                if new_line: table_end = True

                # update line status            
                new_line = True

            # NOTE: close table detecting manually if last block
            if i==num-1: table_end = True

            # end of current table
            if table_lines and table_end: 
                res.append(table_lines)                
                table_lines = Lines() # reset table_blocks

        return res


    def parse_spacing(self):
        ''' Calculate external and internal vertical space for text blocks.
        
            - paragraph spacing is determined by the vertical distance to previous block. 
              For the first block, the reference position is top margin.
            
                It's easy to set before-space or after-space for a paragraph with python-docx,
                so, if current block is a paragraph, set before-space for it; if current block 
                is not a paragraph, e.g. a table, set after-space for previous block (generally, 
                previous block should be a paragraph).
            
            - line spacing is defined as the average line height in current block.
        '''
        if not self._instances: return

        # bbox of blocks
        # - page level, e.g. blocks in top layout
        # - table level, e.g. blocks in table cell
        if isinstance(self.parent, Layout.Layout): 
            bbox = self.parent.bbox

        elif isinstance(self.parent, Cell):
            cell = self.parent
            x0,y0,x1,y1 = cell.bbox
            w_top, w_right, w_bottom, w_left = cell.border_width
            bbox = (x0+w_left/2.0, y0+w_top/2.0, x1-w_right/2.0, y1-w_bottom/2.0)
        else:
            return

        # check text direction for vertical space calculation:
        # - normal reading direction (from left to right)    -> the reference boundary is top border, i.e. bbox[1].
        # - vertical text direction, e.g. from bottom to top -> left border bbox[0] is the reference
        idx = 1 if self.is_horizontal_text else 0

        ref_block = self._instances[0]
        ref_pos = bbox[idx]

        for block in self._instances:

            #---------------------------------------------------------
            # alignment mode and left spacing:
            # - horizontal block -> take left boundary as reference
            # - vertical block   -> take bottom boundary as reference
            #---------------------------------------------------------
            block.parse_horizontal_spacing(bbox)

            #---------------------------------------------------------
            # vertical space calculation
            #---------------------------------------------------------

            # NOTE: the table bbox is counted on center-line of outer borders, so a half of top border
            # size should be excluded from the calculated vertical spacing
            if block.is_table_block():
                dw = block[0][0].border_width[0] / 2.0 # use top border of the first cell

                # calculate vertical spacing of blocks under this table
                block.parse_spacing()
            
            else:
                dw = 0.0

            start_pos = block.bbox[idx] - dw
            para_space = start_pos-ref_pos

            # modify vertical space in case the block is out of bootom boundary
            dy = max(block.bbox[idx+2]-bbox[idx+2], 0.0)
            para_space -= dy
            para_space = max(para_space, 0.0) # ignore negative value

            # ref to current (paragraph): set before-space for paragraph
            if block.is_text_block():

                # spacing before this paragraph
                block.before_space = start_pos-ref_pos # keep negative value temperally

                # calculate average line spacing in paragraph
                # NOTE: adjust before space if negative value
                block.parse_line_spacing()

            # if ref to current (image): set before-space for paragraph
            elif block.is_image_block():
                block.before_space = para_space

            # ref (paragraph/image) to current: set after-space for ref paragraph        
            elif ref_block.is_text_block() or ref_block.is_image_block():
                ref_block.after_space = para_space

            # situation with very low probability, e.g. ref (table) to current (table)
            # we can't set before space for table in docx, but the tricky way is to
            # create an empty paragraph and set paragraph line spacing and before space
            else:
                block.before_space = max(para_space, DM) # let para_space>=1 Pt to accommodate the dummy paragraph


            # update reference block        
            ref_block = block
            ref_pos = ref_block.bbox[idx+2] + dw # assume same bottom border with top one

        # NOTE: when a table is at the end of a page, a dummy paragraph with a small line spacing 
        # is added after this table, to avoid unexpected page break. Accordingly, this extra spacing 
        # must be remove in other place, especially the page space is run out.
        # Here, reduce the last row of table.
        block = self._instances[-1]
        if block.is_table_block():
            block[-1].height -= DM # same value used when creating docx


    def join_horizontally(self, text_direction=True):
        ''' Join lines in horizontally aligned blocks into new TextBlock.
            ---
            Args:
            - text_direction: whether consider text direction.
              If True, detect text direction based on line direction;
              if False, use default direction: from left to right.

            This function converts potential float layout into flow layout, e.g. remove overlapped lines, 
            reposition inline images, so that make rebuilding such layout in docx possible.
        '''
        # get horizontally aligned blocks group by group
        fun = lambda a,b: a.horizontally_align_with(b, factor=0.0, text_direction=text_direction)
        groups = self.group(fun)
        
        # merge text blocks in each group
        blocks = []
        for blocks_collection in groups:
            block = blocks_collection._merge_one()
            blocks.append(block)
        
        # add table blocks
        blocks.extend(self.table_blocks)

        self.reset(blocks)

        return self


    def split_vertically(self):
        ''' Split the joined lines in vertical direction.

            With preceding joining step, current text block may contain lines coming from various original blocks.
            Considering that different text block may have different line properties, e.g. height, spacing, 
            this function is to split them back to original text block. But the original layout may not reasonable for
            re-building docx, so a high priority is to split them vertically, which converts potential float layout to
            flow layout.
        '''
        blocks = [] # type: list[TextBlock]
        for block in self._instances:
            if block.is_text_block():
                blocks.extend(block.split())
            else:
                blocks.append(block)
        
        self.reset(blocks).sort_in_reading_order()

        return self


    def parse_text_format(self, rects):
        '''Parse text format with style represented by rectangles.
            ---
            Args:
              - rects: Shapes, potential styles applied on blocks

            NOTE: `parse_text_format` must be implemented by TextBlock, ImageBlock and TableBlock.
        '''
        # parse text block style one by one
        for block in self._instances:
            block.parse_text_format(rects)

        return True    


    def make_page(self, doc):
        ''' Create page based on parsed block structure. 
            ---
            Args:
            - doc: python-docx Document or _Cell object
        '''
        for block in self._instances:

            # make paragraphs
            if block.is_text_block():
                # new paragraph
                p = doc.add_paragraph()
                block.make_docx(p)
            
            # make table
            elif block.is_table_block():

                # create dummy paragraph if table before space is set
                # line spacing: table before_space/2.0
                # before space: table before space / 2.0
                if block.before_space:
                    h = int(10*block.before_space/2.0)/10.0 # round(x,1), but to lower bound
                    h = max(h, 1.0) # 1.0 is the minimum value in docx
                    p = doc.add_paragraph()
                    pf = reset_paragraph_format(p)
                    pf.space_before = Pt(h)
                    pf.space_after = Pt(0)
                    pf.line_spacing = Pt(h)

                # new table            
                table = doc.add_table(rows=block.num_rows, cols=block.num_cols)
                table.autofit = False
                table.allow_autofit  = False
                block.make_docx(table)
                
        # NOTE: If a table is at the end of a page, a new paragraph will be automatically 
        # added by the rending engine, e.g. MS Word, which resulting in an unexpected
        # page break. The solution is to never put a table at the end of a page, so add
        # an empty paragraph and reset its format, particularly line spacing, when a table
        # is created.
        if bool(self) and self._instances[-1].is_table_block():
            p = doc.add_paragraph()
            reset_paragraph_format(p, Pt(DM)) # a small line height


    def _merge_one(self):
        ''' Merge all text blocks into one text block.
            
            NOTE:            
            Lines in text block must have same property, e.g. height, vertical distance, 
            because average line height is used when create docx. However, the contained lines 
            may be not reasonable after this step. So, this is just a pre-processing step focusing 
            on processing lines in horizontal direction, e.g. merging inline image to its text line.
            A further step, e.g. `split_vertically()`, must be applied before final making docx.
        '''
        # combine all lines into a TextBlock
        final_block = TextBlock()
        for block in self._instances:
            if not block.is_text_block(): continue
            for line in block.lines:
                final_block.add(line) # keep empty line, may help to identify table layout

        # merge lines/spans contained in this textBlock
        final_block.lines.join()

        return final_block

