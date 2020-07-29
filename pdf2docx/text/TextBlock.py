# -*- coding: utf-8 -*-

'''
Text block objects based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---
https://pymupdf.readthedocs.io/en/latest/textpage.html

    {
        # raw dict
        # --------------------------------
        'type': 0,
        'bbox': (x0,y0,x1,y1),
        'lines': [ lines ]

        # introduced dict
        # --------------------------------
        'before_space': bs,
        'after_space': as,
        'line_space': ls
    }
'''

from docx.shared import Pt
from .Line import Line
from .Lines import Lines
from .ImageSpan import ImageSpan
from ..common.base import RectType
from ..common.Block import Block
from ..common import utils
from ..common import docx


class TextBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(TextBlock, self).__init__(raw)

        # collect lines
        self.lines = Lines(None, self).from_dicts(raw.get('lines', []))

        # set type
        self.set_text_block()

    @property
    def text(self) -> str:
        '''Get text content in block, joning each line with `\n`.'''
        lines = [line.spans.text for line in self.lines]
        return '\n'.join(lines)


    @property
    def sub_bboxes(self) -> list:
        '''bbox of sub-region, i.e. Line.'''
        return [line.bbox for line in self.lines]

    
    def is_horizontal_block(self):
        ''' Check whether each line is oriented horizontally.'''
        return all(line.dir[0]==1.0 for line in self.lines)


    def store(self) -> dict:
        res = super().store()
        res.update({
            'lines': self.lines.store()
        })
        return res


    def add(self, line:Line):
        '''Add line to TextBlock.'''
        if isinstance(line, Line):
            self.lines.append(line)


    def plot(self, page):
        '''Plot block/line/span area, in PDF page.
           ---
            Args: 
              - page: fitz.Page object
        '''
        # block border in blue
        blue = utils.RGB_component_from_name('blue')   
        page.drawRect(self.bbox, color=blue, fill=None, overlay=False)

        # lines and spans
        for line in self.lines:
            # line border in red
            red = utils.RGB_component_from_name('red')
            line.plot(page, red)

            # span regions in random color
            for span in line.spans:
                c = utils.RGB_component_from_name('')                
                span.plot(page, c)


    def contains_discrete_lines(self, distance:float=25, threshold:int=3) -> bool:
        ''' Check whether lines in block are discrete: 
            the count of lines with a distance larger than `distance` is greater then `threshold`.
        '''
        num = len(self.lines)
        if num==1: return False

        # check the count of discrete lines
        cnt = 1
        for i in range(num-1):
            bbox = self.lines[i].bbox
            next_bbox = self.lines[i+1].bbox

            if utils.is_horizontal_aligned(bbox, next_bbox):
                # horizontally aligned but not in a same row -> discrete block
                if not utils.in_same_row(bbox, next_bbox):
                    return True
                
                # otherwise, check the distance only
                else:
                    if abs(bbox.x1-next_bbox.x0) > distance:
                        cnt += 1

        return cnt >= threshold

    
    def merge_image(self, image:Block):
        '''Insert inline image to associated text block as a span.
            ---
            Args:
              - image: ImageBlock, target image block
        '''
        # get the inserting position
        for i,line in enumerate(self.lines):
            if image.bbox.x0 < line.bbox.x0:
                break
        else:
            i = 0

        # Step 1: insert image as a line in block
        # image span
        span = ImageSpan()
        span.from_image_block(image)

        # add span to line
        line = Line()
        line.add(span)
        self.lines.insert(i, line)

        # Step 2: merge image into span in line, especially overlap exists
        self.lines.merge()


    def parse_text_format(self, rects) -> bool:
        '''parse text format with style represented by rectangles.
            ---
            Args:
              - rects: Rectangles, potential styles applied on blocks
        '''
        flag = False

        # use each rectangle (a specific text format) to split line spans
        for rect in rects:

            # a same style rect applies on only one block
            if rect.type != RectType.UNDEFINED:
                continue

            # any intersection with current block?
            if not self.bbox.intersects(rect.bbox):
                continue

            # yes, then go further to lines in block            
            for line in self.lines:
                # any intersection in this line?
                intsec = rect.bbox & ( line.bbox + utils.DR )
                if not intsec: continue

                # yes, then try to split the spans in this line
                split_spans = []
                for span in line.spans: 
                    # include image span directly
                    if isinstance(span, ImageSpan):
                        split_spans.append(span)                   

                    # split text span with the format rectangle: span-intersection-span
                    else:
                        spans = span.split(rect)
                        split_spans.extend(spans)
                        flag = True
                                                
                # update line spans                
                line.spans.reset(split_spans)

        return flag


    def parse_line_spacing(self):
        '''Calculate average line spacing.

            The layout of pdf text block: line-space-line-space-line, excepting space before first line, 
            i.e. space-line-space-line, when creating paragraph in docx. So, an average line height = space+line.

            Then, the height of first line can be adjusted by updating paragraph before-spacing.
        '''
        ref_bbox = None
        count = 0

        for line in self.lines:
            # count of lines
            if not utils.in_same_row(line.bbox, ref_bbox):
                count += 1

            # update reference line
            ref_bbox = line.bbox            
        
        _, y0, _, y1 = self.lines[0].bbox_raw   # first line
        first_line_height = y1 - y0
        block_height = self.bbox.y1-self.bbox.y0
        
        # average line spacing
        if count > 1:
            line_space = (block_height-first_line_height)/(count-1)
        else:
            line_space = block_height        
        self.line_space = line_space

        # since the line height setting in docx may affect the original bbox in pdf, 
        # it's necessary to update the before spacing:
        # taking bottom left corner of first line as the reference point                
        self.before_space += first_line_height - line_space


    def make_docx(self, p, X0:float):
        ''' Create paragraph for a text block. Join line sets with TAB and set position according to bbox.
            ---
            Args:
              - p: docx paragraph instance
              - X0: left border of paragraph

            Generally, a pdf block is a docx paragraph, with block|line as line in paragraph.
            But without the context, it's not able to recognize a block line as word wrap, or a 
            separate line instead. A rough rule used here:
            
            block line will be treated as separate line by default, except
              - (1) this line and next line are actually in the same line (y-position)
              - (2) if the rest space of this line can't accommodate even one span of next line, 
                    it's supposed to be normal word wrap.

            Refer to python-docx doc for details on text format:
            https://python-docx.readthedocs.io/en/latest/user/text.html            
        '''
        # indent and space setting
        before_spacing = max(round(self.before_space, 1), 0.0)
        after_spacing = max(round(self.after_space, 1), 0.0)
        pf = docx.reset_paragraph_format(p)
        pf.space_before = Pt(before_spacing)
        pf.space_after = Pt(after_spacing)
        
        # restore default tabs
        pf.tab_stops.clear_all()

        # set line spacing for text paragraph
        pf.line_spacing = Pt(round(self.line_space,1))
        current_pos = 0.0

        # set all tab stops
        all_pos = set([
            round(line.bbox.x0-X0, 2) for line in self.lines if line.bbox.x0>=X0+utils.DM
            ])
        for pos in all_pos:
            pf.tab_stops.add_tab_stop(Pt(pos))

        # add line by line
        for i, line in enumerate(self.lines):

            # left indent implemented with tab
            pos = round(line.bbox.x0-X0, 2)
            docx.add_stop(p, Pt(pos), Pt(current_pos))

            # add line
            for span in line.spans:
                # add content
                span.make_docx(p)

            # break line? new line by default
            line_break = True
            # no more lines after last line
            if line==self.lines[-1]: 
                line_break = False            
            
            # do not break line if they're indeed in same line
            elif utils.in_same_row(self.lines[i+1].bbox, line.bbox):
                line_break = False
            
            if line_break:
                p.add_run('\n')
                current_pos = 0
            else:
                current_pos = round(line.bbox.x1-X0, 2)

        return p
