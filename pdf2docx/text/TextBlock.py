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

from docx.shared import (Pt,Inches)
from docx.enum.text import WD_ALIGN_PARAGRAPH
from .Lines import Lines
from ..image.ImageSpan import ImageSpan
from ..common.share import (RectType, TextAlignment, lower_round)
from ..common.Block import Block
from ..common.share import (rgb_component_from_name, lower_round)
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
        '''Text content in block. Note image is counted as a placeholder ``<image>``.'''
        lines_text = [line.text for line in self.lines]
        return ''.join(lines_text)

    @property
    def raw_text(self):
        '''Raw text content in block without considering images.'''
        lines_text = [line.raw_text for line in self.lines]
        return ''.join(lines_text)

    @property
    def white_space_only(self):
        '''If this block contains only white space or not. If True, this block is safe to be removed.'''
        return all(line.white_space_only for line in self.lines)

    @property
    def text_direction(self):
        '''All lines contained in text block must have same text direction. 
        Otherwise, set normal direction.
        '''            
        return self.lines.text_direction

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


    def parse_text_format(self, shapes):
        '''Parse text format with style represented by rectangles.
        
        Args:
            shapes (Shapes): Shapes representing potential styles applied on blocks.
        '''
        flag = False

        # use each rectangle (a specific text format) to split line spans
        for shape in shapes:

            # a same style shape applies on only one block
            # EXCEPTION: hyperlink shape is determined in advance
            if not shape.equal_to_type(RectType.HYPERLINK) and shape.is_determined: continue

            # any intersection with current block?
            if not self.bbox.intersects(shape.bbox): continue

            # yes, then go further to lines in block
            if self.lines.parse_text_format(shape):
                flag = True

        return flag


    def parse_horizontal_spacing(self, bbox,
                    line_separate_threshold:float,
                    line_break_width_ratio:float,
                    line_break_free_space_ratio:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float):
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
            self.lines.parse_tab_stop(line_separate_threshold)
        
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
            line_break_free_space_ratio)


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

        # ------------------------------------
        # vertical spacing
        # ------------------------------------
        before_spacing = max(round(self.before_space, 1), 0.0)
        after_spacing = max(round(self.after_space, 1), 0.0)
        pf.space_before = Pt(before_spacing)
        pf.space_after = Pt(after_spacing)        

        # line spacing
        if self.line_space_type==0: # exact line spacing
            pf.line_spacing = Pt(round(self.line_space, 1))
        else: # relative line spacing
            pf.line_spacing = round(self.line_space, 2)

        # ------------------------------------
        # horizontal alignment
        # ------------------------------------
        # (1) set paragraph indentation
        # NOTE: different left spacing setting in case first line indent and hanging
        left_space  = self.left_space        
        if self.first_line_space<0: # in case hanging
            left_space -= self.first_line_space           
        
        pf.left_indent  = Pt(left_space)
        pf.right_indent  = Pt(self.right_space)
        pf.first_line_indent = Pt(self.first_line_space)

        # (2) set alignment mode and adjust indentation:
        # round indention on the opposite side to lower bound (inches), so it saves more space to 
        # avoid unexpected line break
        if self.alignment==TextAlignment.LEFT:
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT            
            # set tab stops to ensure line position
            for pos in self.tab_stops:
                pf.tab_stops.add_tab_stop(Pt(self.left_space + pos))
            
            # adjust right indent
            d = lower_round(self.right_space/constants.ITP, 1)
            pf.right_indent = Inches(d)

        elif self.alignment==TextAlignment.RIGHT:
            pf.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            
            # adjust left indent
            d = lower_round(left_space/constants.ITP, 1)
            pf.left_indent = Inches(d)

        elif self.alignment==TextAlignment.CENTER:
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # adjust both left and right indent
            d = lower_round(left_space/constants.ITP, 1)
            pf.left_indent = Inches(d)
            d = lower_round(self.right_space/constants.ITP, 1)
            pf.right_indent = Inches(d)

        else:
            pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        # ------------------------------------
        # add lines
        # ------------------------------------
        for line in self.lines: line.make_docx(p)

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
        def external_alignment():         
            if abs(d_center) < lines_center_aligned_threshold: 
                return TextAlignment.CENTER
            elif d_left <= 0.25*W:
                return TextAlignment.LEFT
            else:
                return TextAlignment.RIGHT
        
        if len(rows) == 1: return external_alignment()

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
            alignment = TextAlignment.JUSTIFY if len(rows)>=3 else external_alignment()

        elif center_aligned:
            alignment = TextAlignment.CENTER

        elif left_aligned:            
            alignment = TextAlignment.LEFT

        elif right_aligned:
            # change right alignment to left if two lines only
            alignment = TextAlignment.RIGHT if len(rows)>=3 else TextAlignment.LEFT

        else:
            alignment = TextAlignment.NONE
        
        # set first line space in case left/justify
        if alignment==TextAlignment.LEFT or alignment==TextAlignment.JUSTIFY:
            self.first_line_space = rows[0][0].bbox[idx0] - rows[1][0].bbox[idx0]
        
        return alignment