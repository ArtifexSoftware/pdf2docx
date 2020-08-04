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
from ..common.base import RectType, TextDirection
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

    
    @property
    def text_direction(self):
        '''All lines contained in text block must have same text direction. Otherwise, set normal direction'''            
        res = set(line.text_direction for line in self.lines)
        # consider two text direction only:  left-right, bottom-top
        if TextDirection.IGNORE in res:
            return TextDirection.IGNORE
        elif len(res)==1:
            return list(res)[0]
        else:
            return TextDirection.LEFT_RIGHT


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


    def merge(self):
        '''Merge contained lines horizontally.'''
        self.lines.merge()


    def split(self):
        ''' Split contained lines vertically and create associated text blocks.'''
        blocks = [] # type: list[TextBlock]
        for lines in self.lines.split():
            text_block = TextBlock()
            text_block.lines.reset(list(lines))
            blocks.append(text_block)
        
        return blocks


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
              - the count of lines with a distance larger than `distance` is greater then `threshold`.
              - ImageSpan exists
              - vertical text exists
        '''
        num = len(self.lines)
        if num==1: return False

        # check image spans
        if self.lines.image_spans:
            return True

        # check text direction
        if self.is_vertical:
            return True

        # check the count of discrete lines
        cnt = 1
        for i in range(num-1):
            line = self.lines[i]
            next_line = self.lines[i+1]

            if line.horizontally_align_with(next_line):
                # horizontally aligned but not in a same row -> discrete block
                if not line.in_same_row(next_line):
                    return True
                
                # otherwise, check the distance only
                else:
                    if abs(line.bbox.x1-next_line.bbox.x0) > distance:
                        cnt += 1

        return cnt >= threshold

    
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
                        spans = span.split(rect, line.is_horizontal)
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

        # check text direction
        idx = 1 if self.is_horizontal else 0

        ref_line = None
        count = 0

        for line in self.lines:
            # count of lines
            if not line.in_same_row(ref_line):
                count += 1

            # update reference line
            ref_line = line            
        
        bbox = self.lines[0].bbox_raw   # first line
        first_line_height = bbox[idx+2] - bbox[idx]
        block_height = self.bbox_raw[idx+2]-self.bbox_raw[idx]
        
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


    def make_docx(self, p, bbox:tuple):
        ''' Create paragraph for a text block. Join line sets with TAB and set position according to bbox.
            ---
            Args:
              - p: docx paragraph instance
              - bbox: boundary box of paragraph

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
        # check text direction
        # normal direction by default, taking left border as a reference
        # when from bottom to top, taking bottom border as a reference
        idx = 0 if self.is_horizontal else 3

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
            round(abs(line.bbox_raw[idx]-bbox[idx]), 2) for line in self.lines
            ])
        for pos in all_pos:
            pf.tab_stops.add_tab_stop(Pt(pos))

        # add line by line
        for i, line in enumerate(self.lines):

            # left indent implemented with tab
            pos = round(abs(line.bbox_raw[idx]-bbox[idx]), 2)
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
            elif line.in_same_row(self.lines[i+1]):
                line_break = False
            
            if line_break:
                p.add_run('\n')
                current_pos = 0
            else:
                current_pos = round(abs(line.bbox_raw[(idx+2)%4]-bbox[idx]), 2)

        return p
