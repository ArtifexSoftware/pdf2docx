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
from ..common.share import RectType, TextDirection, TextAlignment
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
        '''Get text content in block, joning each line with ``\\n``.'''
        lines_text = [line.text for line in self.lines]
        return '\n'.join(lines_text)

    
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
        fun = lambda a,b: a.in_same_row(b)
        rows = self.lines.group(fun)
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
        fun = lambda a,b: a.in_same_row(b)
        rows = self.lines.group(fun)
        return len(rows)


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


    def strip(self):
        '''Strip each Line instance.'''
        self.lines.strip()


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
        
        # decide text alignment by internal lines in first priority; if can't decide, check
        # with page layout.
        int_alignment = self._internal_alignment((idx0, idx1, f),
                        line_separate_threshold,
                        lines_left_aligned_threshold,
                        lines_right_aligned_threshold,
                        lines_center_aligned_threshold)
        ext_alignment = self._external_alignment(bbox,
                        (idx0, idx1, f),
                        lines_center_aligned_threshold)
        self.alignment = int_alignment if int_alignment!=TextAlignment.UNKNOWN else ext_alignment

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
        if self.alignment == TextAlignment.LEFT:
            if row_count==1:
                self.right_space = 0
            else:
                self.right_space -= constants.MAJOR_DIST

        elif self.alignment == TextAlignment.RIGHT:
            if row_count==1:
                self.left_space = 0
            else:
                self.left_space -= constants.MAJOR_DIST

        elif self.alignment == TextAlignment.CENTER:
            if row_count==1:
                self.left_space = 0
                self.right_space = 0
            else:
                self.left_space -= constants.MAJOR_DIST
                self.right_space -= constants.MAJOR_DIST

            
        # parse line break
        layout_width = bbox[idx1] - bbox[idx0]
        block_width = self.bbox[idx1] - self.bbox[idx0]
        self.lines.parse_line_break(block_width/layout_width, line_break_width_ratio)


    def parse_line_spacing_relatively(self):
        '''Calculate relative line spacing, e.g. `spacing = 1.02`. 

        It's complicated to calculate relative line spacing, e.g. considering font style. 
        A simple rule is used:

            line_height = 1.3 * font_size

        .. note::
            The line spacing could be updated automatically when changing the font size, while the layout might
            be broken in exact spacing mode, e.g. overlapping of lines.
        '''
        factor = 1.22

        # block height
        idx = 1 if self.is_horizontal_text else 0
        block_height = self.bbox[idx+2]-self.bbox[idx]
        
        # The layout of pdf text block:    line-space-line-space-line, while
        # The layout of paragraph in docx: line-space-line-space-line-space, note the extra space at the end.
        # So, (1) calculate the line spacing x => x*1.3*sum_{n-1}(H_i) + Hn = H, 
        #     (2) calculate the extra space at the end, to be excluded from the before space of next block.
        fun = lambda a,b: a.in_same_row(b)
        rows = self.lines.group(fun)
        count = len(rows)
        
        max_line_height = lambda row: max(abs(line.bbox[idx+2]-line.bbox[idx]) for line in row)
        last_line_height = max_line_height(rows[-1])

        if count > 1:
            sum_pre_line_height = sum(max_line_height(row) for row in rows[:-1])            
            self.line_space = (block_height-last_line_height)/sum_pre_line_height/factor
        else:
            self.line_space = 1.0
        
        # extra space at the end
        end_space = (self.line_space*factor-1.0) * last_line_height if self.line_space>1.0 else 0.0
        return end_space


    def parse_line_spacing_exactly(self):
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
        pf.line_spacing = Pt(round(self.line_space, 1))

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



    def _internal_alignment(self, text_direction_param:tuple, 
                    line_separate_threshold:float,
                    lines_left_aligned_threshold:float,
                    lines_right_aligned_threshold:float,
                    lines_center_aligned_threshold:float):
        '''Detect text alignment mode based on layout of internal lines. 
        
        Args:
            text_direction_param (tuple): ``(x0_index, x1_index, direction_factor)``, 
                e.g. ``(0, 2, 1)`` for horizontal text, while ``(3, 1, -1)`` for vertical text.
        '''
        # get lines in each physical row
        fun = lambda a,b: a.in_same_row(b)
        rows = self.lines.group(fun)

        # indexes based on text direction
        idx0, idx1, f = text_direction_param

        # --------------------------------------------------------------------------
        # First priority: significant distance exists in any two adjacent lines ->
        # set unknown alignment temporarily. Assign left-align to it later and ensure
        # exact position of each line by TAB stop. 
        # --------------------------------------------------------------------------
        for row in rows:
            if len(row)==1: continue
            dis = [(row[i].bbox[idx0]-row[i-1].bbox[idx1])*f>=line_separate_threshold \
                        for i in range(1, len(row))]
            if any(dis):
                return TextAlignment.NONE

        # just one row -> can't decide -> full possibility
        if len(rows) < 2: return TextAlignment.UNKNOWN

        # --------------------------------------------------------------------------
        # Then check alignment of internal lines:
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
            return TextAlignment.JUSTIFY if len(rows)>=3 else TextAlignment.UNKNOWN

        elif left_aligned:
            self.first_line_space = rows[0][0].bbox[idx0] - rows[1][0].bbox[idx0]
            return TextAlignment.LEFT

        elif right_aligned:
            return TextAlignment.RIGHT

        elif center_aligned:
            return TextAlignment.CENTER

        else:
            return TextAlignment.NONE


    def _external_alignment(self, bbox:list, 
            text_direction_param:tuple,
            lines_center_aligned_threshold:float):
        '''Detect text alignment mode based on the position to external bbox. 
        
        Args:
            bbox (list): Page or Cell bbox where this text block locates in.
            text_direction_param (tuple): ``(x0_index, x1_index, direction_factor)``, e.g. 
                ``(0, 2, 1)`` for horizontal text, while ``(3, 1, -1)`` for vertical text.
        '''
        # indexes based on text direction
        idx0, idx1, f = text_direction_param

        # distance to the bbox
        d_left   = round((self.bbox[idx0]-bbox[idx0])*f, 1) # left margin
        d_right  = round((bbox[idx1]-self.bbox[idx1])*f, 1) # right margin
        d_center = round((d_left-d_right)/2.0, 1)           # center margin
        d_left   = max(d_left, 0.0)
        d_right  = max(d_right, 0.0)

        # NOTE: set horizontal space
        self.left_space  = d_left
        self.right_space = d_right

        # block location: left/center/right
        if abs(d_center) < lines_center_aligned_threshold: 
            return TextAlignment.CENTER
        else:
            return TextAlignment.LEFT if abs(d_left) <= abs(d_right) else TextAlignment.RIGHT