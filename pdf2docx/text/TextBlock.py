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
        'line_space': ls,

        'alignment': 0,
        'left_space': 10.0,
        'right_space': 0.0,

        'tab_stops': [15.4, 35.0]
    }
'''

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .Line import Line
from .Lines import Lines
from ..image.ImageSpan import ImageSpan
from ..common.share import TextDirection, TextAlignment
from ..common.Block import Block
from ..common.share import rgb_component_from_name
from ..common import constants
from ..common import docx


class TextBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}
        
        # remove key 'bbox' since it is calculated from contained lines
        if 'bbox' in raw: raw.pop('bbox') 
        super().__init__(raw)

        # collect lines
        self.lines = Lines(parent=self).restore(raw.get('lines', []))

        # set type
        self.set_text_block()        


    @property
    def text(self):
        '''Get text content in block, joning each line with `\n`.'''
        lines_text = [line.text for line in self.lines]
        return '\n'.join(lines_text)

    
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


    def is_flow_layout(self, float_layout_tolerance:float):
        '''Check if flow layout: same bottom-left point for lines in same row.'''
        # lines in same row
        fun = lambda a, b: a.horizontally_align_with(b, factor=float_layout_tolerance)
        groups = self.lines.group(fun)
        
        # check bottom-left point of lines
        for lines in groups:
            points = set([line.bbox[3] for line in lines])
            if max(points)-min(points)>constants.MINOR_DIST: return False
        return True


    def store(self):
        res = super().store()
        res.update({
            'lines': self.lines.store()
        })
        return res


    def add(self, line_or_lines):
        '''Add line or lines to TextBlock.'''        
        if isinstance(line_or_lines, (Lines, list, tuple)):
            for line in line_or_lines:
                self.lines.append(line)
        else:
            self.lines.append(line_or_lines)


    def split(self):
        ''' Split contained lines vertically and create associated text blocks.'''
        blocks = [] # type: list[TextBlock]
        for lines in self.lines.split(threshold=constants.FACTOR_A_FEW):
            text_block = TextBlock()
            text_block.lines.reset(list(lines))
            blocks.append(text_block)
        
        return blocks


    def strip(self):
        '''strip each Line instance.'''
        self.lines.strip()


    def plot(self, page):
        '''Plot block/line/span area, in PDF page.
           ---
            Args: 
              - page: fitz.Page object
        '''
        # block border in blue
        blue = rgb_component_from_name('blue')   
        super().plot(page, stroke=blue, dashes='[3.0 3.0] 0')

        # lines and spans
        for line in self.lines:
            # line border in red
            red = rgb_component_from_name('red')
            line.plot(page, stroke=red)

            # span regions in random color
            for span in line.spans:
                c = rgb_component_from_name('')                
                span.plot(page, color=c)


    def parse_text_format(self, rects):
        '''parse text format with style represented by rectangles.
            ---
            Args:
              - rects: Shapes, potential styles applied on blocks
        '''
        flag = False

        # use each rectangle (a specific text format) to split line spans
        for rect in rects:

            # a same style rect applies on only one block
            if rect.is_determined: continue

            # any intersection with current block?
            if not self.bbox.intersects(rect.bbox): continue

            # yes, then go further to lines in block            
            for line in self.lines:
                # any intersection in this line?
                intsec = rect.bbox & line.get_expand_bbox(constants.TINY_DIST)
                
                if not intsec: 
                    if rect.bbox.y1 < line.bbox.y0: break # lines must be sorted in advance
                    continue

                # yes, then try to split the spans in this line
                split_spans = []
                for span in line.spans: 
                    # include image span directly
                    if isinstance(span, ImageSpan): split_spans.append(span)                   

                    # split text span with the format rectangle: span-intersection-span
                    else:
                        spans = span.split(rect, line.is_horizontal_text)
                        split_spans.extend(spans)
                        flag = True
                                                
                # update line spans                
                line.spans.reset(split_spans)

        return flag


    def parse_horizontal_spacing(self, bbox,
                    line_separate_threshold:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float):
        ''' Set horizontal spacing based on lines layout and page bbox.
            - The general spacing is determined by paragraph alignment and indentation.
            - The detailed spacing of block lines is determined by tab stops.

            Multiple alignment modes may exist in block (due to improper organized lines
            from PyMuPDF), e.g. some lines align left, and others right. In this case,
            LEFT alignment is set, and use TAB to position each line.
        '''
        # NOTE: in PyMuPDF CS, horizontal text direction is same with positive x-axis,
        # while vertical text is on the contrary, so use f = -1 here
        idx0, idx1, f = (0, 2, 1.0) if self.is_horizontal_text else (3, 1, -1.0)
        
        # the idea is to detect alignments based on internal lines and external bbox,
        # the alignment mode fulfilled with both these two criteria is preferred.
        int_mode = self._internal_alignments((idx0, idx1, f),
                        line_separate_threshold,
                        lines_left_aligned_threshold,
                        lines_right_aligned_threshold,
                        lines_center_aligned_threshold)
        ext_mode = self._external_alignments(bbox, 
                        (idx0, idx1, f),
                        lines_center_aligned_threshold) # set horizontal space additionally
        mode = int_mode & ext_mode

        # now, decide the alignment accordingly
        for align_mode in TextAlignment:
            if align_mode.value==mode:
                self.alignment = align_mode
                break
        else:
            self.alignment = TextAlignment.LEFT # LEFT by default

        # tab stops for block lines
        if self.alignment != TextAlignment.LEFT: return

        # NOTE: relative stop position to left boundary of block is calculated, so block.left_space is required
        fun = lambda line: round((line.bbox[idx0]-self.bbox[idx0])*f, 1) # relative position to block
        all_pos = set(map(fun, self.lines))
        self.tab_stops = list(filter(lambda pos: pos>=constants.MINOR_DIST, all_pos))        


    def parse_line_spacing(self):
        '''Calculate average line spacing.

            The layout of pdf text block: line-space-line-space-line, excepting space before first line, 
            i.e. space-line-space-line, when creating paragraph in docx. So, an average line height = space+line.

            Then, the height of first line can be adjusted by updating paragraph before-spacing.
        '''

        # check text direction
        idx = 1 if self.is_horizontal_text else 0

        ref_line = None
        count = 0

        for line in self.lines:
            # count of lines
            if not line.in_same_row(ref_line): count += 1

            # update reference line
            ref_line = line            
        
        bbox = self.lines[0].bbox   # first line
        first_line_height = bbox[idx+2] - bbox[idx]
        block_height = self.bbox[idx+2]-self.bbox[idx]
        
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

        # if before spacing is negative, set to zero and adjust calculated line spacing accordingly
        if self.before_space < 0:
            self.line_space += self.before_space / count
            self.before_space = 0.0


    def make_docx(self, p):
        ''' Create paragraph for a text block.
            ---
            Args:
              - p: docx paragraph instance

            NOTE:
            - the left position of paragraph set by paragraph indent, rather than TAB stop
            - hard line break is used for line in block.

            Generally, a pdf block is a docx paragraph, with block->line as line in paragraph.
            But without the context, it's not able to recognize a block line as word wrap, or a 
            separate line instead. A rough rule used here: block line will be treated as separate 
            line, except this line and next line are indeed in the same line.

            Refer to python-docx doc for details on text format:
            - https://python-docx.readthedocs.io/en/latest/user/text.html
            - https://python-docx.readthedocs.io/en/latest/api/enum/WdAlignParagraph.html#wdparagraphalignment
        '''
        pf = docx.reset_paragraph_format(p)

        # vertical spacing
        before_spacing = max(round(self.before_space, 1), 0.0)
        after_spacing = max(round(self.after_space, 1), 0.0)

        pf.space_before = Pt(before_spacing)
        pf.space_after = Pt(after_spacing)        

        # line spacing
        pf.line_spacing = Pt(round(self.line_space, 1))

        # horizontal alignment
        # for multi-lines paragraph, set both left and right indentation; this hard restriction may lead to
        # unexpected line break especially different font used in docx. So, just add one side indentation for
        # single line paragraph.
        if self.alignment==TextAlignment.LEFT:
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf.left_indent  = Pt(self.left_space)
            # set tab stops to ensure line position
            for pos in self.tab_stops:
                pf.tab_stops.add_tab_stop(Pt(self.left_space + pos))

        elif self.alignment==TextAlignment.RIGHT:
            pf.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pf.right_indent  = Pt(self.right_space)

        elif self.alignment==TextAlignment.CENTER:
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER

        else:
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            pf.left_indent  = Pt(self.left_space)
            pf.right_indent  = Pt(self.right_space)

        # add lines        
        self.lines.make_docx(p)

        return p



    def _internal_alignments(self, text_direction_param:tuple, 
                    line_separate_threshold:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float):
        ''' Detect text alignment mode based on layout of internal lines. 
            Return possibility of the alignments, left-center-right-justify e.g. 
            - 0b1000 = left align
            - 0b0100 = center align
            - 0b1111 = possible to any alignment mode
            ---
            Args:
            - text_direction_param: (x0_index, x1_index, direction_factor), e.g. (0, 2, 1) for horizontal text, 
            while (3, 1, -1) for vertical text.
        '''
        # get lines in each physical row
        fun = lambda a,b: a.in_same_row(b)
        rows = self.lines.group(fun)

        # just one row -> can't decide -> full possibility
        if len(rows) < 2: return 0b1111

        # indexes based on text direction
        idx0, idx1, f = text_direction_param

        # --------------------------------------------------------------------------
        # First priority: significant distance exists in any two adjacent lines -> align left
        # --------------------------------------------------------------------------
        for row in rows:
            if len(row)==1: continue
            for i in range(1, len(row)):
                dis = (row[i].bbox[idx0]-row[i-1].bbox[idx1])*f
                if dis >= line_separate_threshold:
                    return 0b1000

        # --------------------------------------------------------------------------
        # Then check alignment of internal lines
        # --------------------------------------------------------------------------
        X0 = [lines[0].bbox[idx0]  for lines in rows]
        X1 = [lines[-1].bbox[idx1] for lines in rows]
        X  = [(x0+x1)/2.0 for (x0, x1) in zip(X0, X1)]

        left_aligned   = abs(max(X0)-min(X0))<=lines_left_aligned_threshold
        right_aligned  = abs(max(X1)-min(X1))<=lines_right_aligned_threshold
        center_aligned = abs(max(X)-min(X))  <=lines_center_aligned_threshold # coarse margin for center alignment

        # Note the case that all lines aligned left, but with last line removed, it becomes justify mode.
        if left_aligned and len(rows)>=3: # at least 2 lines excepting the last line
            X1 = X1[0:-1]
            right_aligned = abs(max(X1)-min(X1))<=lines_right_aligned_threshold
            if right_aligned: return 0b0001

        # use bits to represent alignment status
        mode = (int(left_aligned), int(center_aligned), int(right_aligned), 0)
        res = 0
        for i, x in enumerate(mode): res += x * 2**(3-i)
        
        return res


    def _external_alignments(self, bbox:list, 
            text_direction_param:tuple,
            lines_center_aligned_threshold:float):
        ''' Detect text alignment mode based on the position to external bbox. 
            Return possibility of the alignments, left-center-right-justify, e.g. 
            - 0b1000 = left align
            - 0b0100 = center align
            - 0b1111 = possible to any alignment mode
            ---
            Args:
            - bbox: page or cell bbox where this text block locates in.
            - text_direction_param: (x0_index, x1_index, direction_factor), e.g. (0, 2, 1) for horizontal text, 
            while (3, 1, -1) for vertical text.
        '''
        # indexes based on text direction
        idx0, idx1, f = text_direction_param

        # position to the bbox
        d_left   = round((self.bbox[idx0]-bbox[idx0])*f, 1) # left margin
        d_right  = round((bbox[idx1]-self.bbox[idx1])*f, 1) # right margin
        d_center = round((d_left-d_right)/2.0, 1)           # center margin
        d_left   = max(d_left, 0.0)
        d_right  = max(d_right, 0.0)

        # NOTE: set horizontal space
        self.left_space  = d_left
        self.right_space = d_right

        # first priority -> overall layout of block and bbox: 
        # - when the width is as long as the bbox -> we can't decide the mode
        # - when the width is half lower than the bbox -> check close to left or right side
        width_ratio = (self.bbox[idx1]-self.bbox[idx0]) / (bbox[idx1]-bbox[idx0])
        if width_ratio >= constants.FACTOR_MOST: 
            return 0b1111
        
        elif width_ratio < 0.5:
            return 0b1000 if abs(d_left) <= abs(d_right) else 0b0010
        
        # then, check if align center precisely
        elif abs(d_center) < lines_center_aligned_threshold: 
            return 0b0100

        # otherwise, we can't decide it
        else:
            return 0b1111
        