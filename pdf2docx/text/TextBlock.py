# -*- coding: utf-8 -*-

'''Text block objects based on PDF raw dict extracted with ``PyMuPDF``.

Data structure based on this `link <https://pymupdf.readthedocs.io/en/latest/textpage.html>`_::

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
from .Lines import Lines
from ..image.ImageSpan import ImageSpan
from ..common.share import RectType, TextDirection, TextAlignment
from ..common.Block import Block
from ..common.share import rgb_component_from_name
from ..common import constants
from ..common import docx


class TextBlock(Block):
    '''Text block.'''
    def __init__(self, raw:dict=None):
        raw = raw or {}
        
        # remove key 'bbox' since it is calculated from contained lines
        if 'bbox' in raw: raw.pop('bbox') 
        super().__init__(raw)

        # collect lines
        self.lines = Lines(parent=self).restore(raw.get('lines', []))

        # set type
        self.set_text_block()


    @property
    def text(self):
        '''Text content in block.'''
        lines_text = [line.text for line in self.lines]
        return ''.join(lines_text)

    
    @property
    def text_direction(self):
        '''All lines contained in text block must have same text direction. 
        Otherwise, set normal direction.
        '''            
        res = set(line.text_direction for line in self.lines)
        # consider two text direction only:  left-right, bottom-top
        if TextDirection.IGNORE in res:
            return TextDirection.IGNORE
        elif len(res)==1:
            return list(res)[0]
        else:
            return TextDirection.LEFT_RIGHT


    @property
    def average_row_gap(self):
        '''Average distance between adjacent two physical rows.'''
        idx = 1 if self.is_horizontal_text else 0
        rows = self.lines.group_by_physical_rows()
        num = len(rows)

        # no gap if single row
        if num==1: return None
        
        # multi-lines block
        block_height = self.bbox[idx+2]-self.bbox[idx]
        f_max_row_height = lambda row: max(abs(line.bbox[idx+2]-line.bbox[idx]) for line in row)
        sum_row_height = sum(map(f_max_row_height, rows))
        return (block_height-sum_row_height) / (num-1)
    

    @property
    def row_count(self):
        '''Count of physical rows.'''
        return len(self.lines.group_by_physical_rows())


    def is_flow_layout(self, *args):
        '''Check if flow layout'''
        return self.lines.is_flow_layout(*args)


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


    def strip(self, delete_end_line_hyphen:bool):
        '''Strip each Line instance.'''
        self.lines.strip(delete_end_line_hyphen)


    def plot(self, page):
        '''Plot block/line/span area for debug purpose.
        
        Args:
            page (fitz.Page): pdf page.
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
        '''Parse text format with style represented by rectangles.
        
        Args:
            rects (Shapes): Shapes representing potential styles applied on blocks.
        '''
        flag = False

        # use each rectangle (a specific text format) to split line spans
        for rect in rects:

            # a same style rect applies on only one block
            # EXCEPTION: hyperlink shape is determined in advance
            if rect.type!=RectType.HYPERLINK and rect.is_determined: continue

            # any intersection with current block?
            if not self.bbox.intersects(rect.bbox): continue

            # yes, then go further to lines in block
            if self.lines.parse_text_format(rect):
                flag = True

        return flag


    def parse_horizontal_spacing(self, bbox,
                    line_separate_threshold:float,
                    line_break_width_ratio:float,
                    line_break_free_space_ratio:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float,
                    condense_char_spacing:float):
        ''' Set horizontal spacing based on lines layout and page bbox.
        
        * The general spacing is determined by paragraph alignment and indentation.
        * The detailed spacing of block lines is determined by tab stops.

        Multiple alignment modes may exist in block (due to improper organized lines
        from ``PyMuPDF``), e.g. some lines align left, and others right. In this case,
        **LEFT** alignment is set, and use ``TAB`` to position each line.
        '''
        # NOTE: in PyMuPDF CS, horizontal text direction is same with positive x-axis,
        # while vertical text is on the contrary, so use f = -1 here
        idx0, idx1, f = (0, 2, 1.0) if self.is_horizontal_text else (3, 1, -1.0)
        
        # text alignment
        self.alignment = self._parse_alignment(bbox, 
            (idx0, idx1, f),
            line_separate_threshold,
            lines_left_aligned_threshold,
            lines_right_aligned_threshold,
            lines_center_aligned_threshold)

        # if still can't decide, set LEFT by default and ensure position by TAB stops        
        if self.alignment == TextAlignment.NONE:
            self.alignment = TextAlignment.LEFT

            # NOTE: relative stop position to left boundary of block is calculated, 
            # so block.left_space is required
            fun = lambda line: round((line.bbox[idx0]-self.bbox[idx0])*f, 1) # relative position to block
            all_pos = set(map(fun, self.lines))
            self.tab_stops = list(filter(lambda pos: pos>=constants.MINOR_DIST, all_pos))
        
        # adjust left/right indentation:
        # - set single side indentation if single line
        # - add minor space if multi-lines
        row_count = self.row_count
        if row_count==1 and self.alignment == TextAlignment.LEFT:
            self.right_space = 0

        elif row_count==1 and self.alignment == TextAlignment.RIGHT:
            self.left_space = 0
        
        elif row_count==1 and self.alignment == TextAlignment.CENTER:
            self.left_space = 0
            self.right_space = 0
        
        # parse line break
        self.lines.parse_line_break(bbox, 
            line_break_width_ratio, 
            line_break_free_space_ratio, 
            condense_char_spacing)


    def parse_relative_line_spacing(self):
        '''Calculate relative line spacing, e.g. `spacing = 1.02`.  Relative line spacing is based on standard 
        single line height, which is font-related. 

        .. note::
            The line spacing could be updated automatically when changing the font size, while the layout might
            be broken in exact spacing mode, e.g. overlapping of lines.
        '''
        # return default line spacing if any images exists
        for line in self.lines:
            if list(span for span in line.spans if isinstance(span, ImageSpan)):
                self.line_space = constants.DEFULT_LINE_SPACING
                return

        # otherwise, calculate average line spacing
        idx = 1 if self.is_horizontal_text else 0
        block_height = self.bbox[idx+2]-self.bbox[idx]
        
        # An approximate expression: 
        # standard_line_height * relative_line_spacing = block_height
        rows = self.lines.group_by_physical_rows()        
        fun_max_line_height = lambda line: max(span.line_height for span in line.spans)
        fun_max_row_height = lambda row: max(fun_max_line_height(line) for line in row)
        standard_height = sum(fun_max_row_height(row) for row in rows)
        line_space = block_height/standard_height

        # overlap may exist when multi-rows, so set minimum spacing  -> default spacing
        if len(rows)>1: line_space = max(line_space, constants.DEFULT_LINE_SPACING)
        self.line_space = line_space


    def parse_exact_line_spacing(self):
        '''Calculate exact line spacing, e.g. `spacing = Pt(12)`. 

        The layout of pdf text block: line-space-line-space-line, excepting space before first line, 
        i.e. space-line-space-line, when creating paragraph in docx. So, an average line height is 
        ``space+line``. Then, the height of first line can be adjusted by updating paragraph before-spacing.

        .. note::
            Compared with the relative spacing mode, it has a more precise layout, but less flexible editing
            ability, especially changing the font size.
        '''

        # check text direction
        idx = 1 if self.is_horizontal_text else 0       

        bbox = self.lines[0].bbox   # first line
        first_line_height = bbox[idx+2] - bbox[idx]
        block_height = self.bbox[idx+2]-self.bbox[idx]
        
        # average line spacing
        count = self.row_count # count of rows
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
        '''Create paragraph for a text block.

        Refer to ``python-docx`` doc for details on text format:

        * https://python-docx.readthedocs.io/en/latest/user/text.html
        * https://python-docx.readthedocs.io/en/latest/api/enum/WdAlignParagraph.html#wdparagraphalignment
        
        Args:
            p (Paragraph): ``python-docx`` paragraph instance.

        .. note::
            The left position of paragraph is set by paragraph indent, rather than ``TAB`` stop.
        '''
        pf = docx.reset_paragraph_format(p)
        # vertical spacing
        before_spacing = max(round(self.before_space, 1), 0.0)
        after_spacing = max(round(self.after_space, 1), 0.0)

        pf.space_before = Pt(before_spacing)
        pf.space_after = Pt(after_spacing)        

        # line spacing
        pf.line_spacing = round(self.line_space, 2)


        # horizontal alignment
        # - alignment mode
        if self.alignment==TextAlignment.LEFT:
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT            
            # set tab stops to ensure line position
            for pos in self.tab_stops:
                pf.tab_stops.add_tab_stop(Pt(self.left_space + pos))

        elif self.alignment==TextAlignment.RIGHT:
            pf.alignment = WD_ALIGN_PARAGRAPH.RIGHT            

        elif self.alignment==TextAlignment.CENTER:
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER

        else:
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        # - paragraph indentation
        # NOTE: different left spacing setting in case first line indent and hanging
        if self.first_line_space<0: # hanging
            pf.left_indent  = Pt(self.left_space-self.first_line_space)
        else: # first line indent
            pf.left_indent  = Pt(self.left_space)
        pf.right_indent  = Pt(self.right_space)

        # - first line indentation
        pf.first_line_indent = Pt(self.first_line_space)

        # add lines        
        self.lines.make_docx(p)

        return p



    def _parse_alignment(self, bbox,
                    text_direction_param:tuple, 
                    line_separate_threshold:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float):
        '''Detect text alignment mode based on layout of internal lines. It can't decide when only
        one line, in such case, the alignment mode is determined by externally check.
        
        Args:
            text_direction_param (tuple): ``(x0_index, x1_index, direction_factor)``, 
                e.g. ``(0, 2, 1)`` for horizontal text, while ``(3, 1, -1)`` for vertical text.
        '''
        # indexes based on text direction
        idx0, idx1, f = text_direction_param

        # check external position: text block to parent layout
        d_left   = round((self.bbox[idx0]-bbox[idx0])*f, 1) # left margin
        d_right  = round((bbox[idx1]-self.bbox[idx1])*f, 1) # right margin
        d_center = round((d_left-d_right)/2.0, 1)           # center margin
        d_left   = max(d_left, 0.0)
        d_right  = max(d_right, 0.0)
        W = abs(bbox[idx1]-bbox[idx0]) # bbox width

        # NOTE: set horizontal space
        self.left_space  = d_left
        self.right_space = d_right

        # --------------------------------------------------------------------------
        # First priority: 
        # significant distance exists in any two adjacent lines -> set NONE temporarily. 
        # Assign left-align to it later and ensure exact position of each line by TAB stop. 
        # --------------------------------------------------------------------------
        rows = self.lines.group_by_physical_rows() # lines in each physical row
        for row in rows:
            if len(row)==1: continue
            dis = [(row[i].bbox[idx0]-row[i-1].bbox[idx1])*f>=line_separate_threshold \
                        for i in range(1, len(row))]
            if any(dis):
                return TextAlignment.NONE

        # --------------------------------------------------------------------------
        # determined by position to external bbox if one line only
        # the priority: center > left > right
        # --------------------------------------------------------------------------
        # |    ============    | -> center
        # |   ================ | -> left
        # |        =========== | -> right
        if len(rows) == 1: 
            if abs(d_center) < lines_center_aligned_threshold: 
                return TextAlignment.CENTER
            elif d_left <= 0.25*W:
                return TextAlignment.LEFT
            else:
                return TextAlignment.RIGHT

        # --------------------------------------------------------------------------
        # Check alignment of internal lines:
        # When count of lines >= 3:
        # - left-alignment based on lines excepting the first line
        # - right-alignment based on lines excepting the last line
        # the exact position of first line is considered by first-line-indent
        # =========     =======   =========  | =========   =========
        # =========   =========     =======  |   =======   =======
        # =========   =========     =======  |
        # ======      =========     =====    |
        # --------------------------------------------------------------------------
        X0 = [lines[0].bbox[idx0]  for lines in rows]
        X1 = [lines[-1].bbox[idx1] for lines in rows]
        X  = [(x0+x1)/2.0 for (x0, x1) in zip(X0, X1)]

        if len(rows) >= 3: X0, X1 = X0[1:], X1[0:-1]
        left_aligned   = abs(max(X0)-min(X0))<=lines_left_aligned_threshold
        right_aligned  = abs(max(X1)-min(X1))<=lines_right_aligned_threshold
        center_aligned = abs(max(X)-min(X))<=lines_center_aligned_threshold # coarse margin for center alignment

        if left_aligned and right_aligned:
            # need further external check if two lines only
            if len(rows)>=3 or (d_left+d_right)/W < constants.FACTOR_A_FEW:
                self.first_line_space = rows[0][0].bbox[idx0] - rows[1][0].bbox[idx0]
                return TextAlignment.JUSTIFY
            else:
                return TextAlignment.CENTER

        elif center_aligned:
            return TextAlignment.CENTER

        elif left_aligned:
            self.first_line_space = rows[0][0].bbox[idx0] - rows[1][0].bbox[idx0]
            return TextAlignment.LEFT

        elif right_aligned:
            return TextAlignment.RIGHT

        else:
            return TextAlignment.NONE