# -*- coding: utf-8 -*-

'''A group of Line objects.
'''

import logging
import string
from docx.shared import Pt
from .Line import Line
from .TextSpan import TextSpan
from ..image.ImageSpan import ImageSpan
from ..common.Collection import ElementCollection
from ..common.docx import add_stop
from ..common.share import TextAlignment
from ..common import constants


class Lines(ElementCollection):
    '''Collection of text lines.'''

    @property
    def unique_parent(self):
        '''Whether all contained lines have same parant.'''
        if not bool(self): return False

        first_line = self._instances[0]
        return all(line.same_source_parent(first_line) for line in self._instances)


    def append(self, line:Line):
        """Override. Append a line and update line pid and parent bbox.

        Args:
            line (Line): Target line to add.
        """
        super().append(line)

        # update original parent id
        if not self._parent is None:
            line.pid = id(self._parent)


    def restore(self, raws:list):
        '''Construct lines from raw dicts list.'''
        for raw in raws:
            line = Line(raw)
            self.append(line)
        return self


    @property
    def image_spans(self):
        '''Get all ImageSpan instances.'''
        spans = []
        for line in self._instances:
            spans.extend(line.image_spans)
        return spans

    
    def join(self, line_overlap_threshold:float, line_merging_threshold:float):
        '''Merge lines aligned horizontally, e.g. make inline image as a span in text line.'''
        # skip if empty
        if not self._instances: return self

        # valid to merge lines on condition that every tow lines are in same row
        def valid_joining_lines(line, candidates):
            return all(line.in_same_row(_line) for _line in candidates)
        
        # merge lines
        def get_merged_line(candidates):
            line = candidates[0]
            for c_line in candidates[1:]:
                line.add(c_line.spans)
            return line

        # sort lines
        self.sort()

        # check each line
        lines = Lines()
        candidates = [self._instances[0]] # first line
        for i in range(1, len(self._instances)):
            pre_line, line = self._instances[i-1], self._instances[i]
           
            # ignore this line if overlap with previous line
            if line.get_main_bbox(pre_line, threshold=line_overlap_threshold):
                logging.warning('Ignore Line "%s" due to overlap', line.text)
                continue

            # add line directly if not aligned horizontally with previous line
            if not line.in_same_row(pre_line):
                to_join_line = False

            # if it exists x-distance obviously to previous line,
            # take it as a separate line as it is
            elif abs(line.bbox.x0-pre_line.bbox.x1) > line_merging_threshold:
                to_join_line = False 

            # now, this line will be append to previous line as a span
            else:
                to_join_line = True

            # add line directly
            if not to_join_line:
                # merge candidate lines (if any)
                if candidates: lines.append(get_merged_line(candidates))
                candidates = []

                # add this line
                lines.append(line)
            
            # prepare for merging lines: valid
            elif valid_joining_lines(line, candidates):
                candidates.append(line)
            
            # prepare for merging lines: invalid -> add each line directly
            else:
                # release candidate lines
                for c_line in candidates: lines.append(c_line)
                candidates = []

                # add this line
                lines.append(line)

        # NOTE: in case last group
        if candidates: lines.append(get_merged_line(candidates))

        # update lines in block
        self.reset(lines)


    def split_back(self):
        '''Split lines into groups, in which all lines are from same original text block.

        Returns:
            list: A list of Lines contained in same original text block.
        '''
        fun = lambda a,b: a.same_source_parent(b)
        groups = self.group(fun)

        # NOTE: group() may destroy the order of lines, so sort in line level
        for group in groups: group.sort()

        return groups

    
    def split_vertically_by_text(self, line_break_free_space_ratio:float, new_paragraph_free_space_ratio:float):
        '''Split lines into separate paragraph, because ``PyMuPDF`` stores lines in ``block``,
        rather than real paragraph.

        .. note::
            Considered only normal reading direction, from left to right, from top
            to bottom.
        '''
        rows = self.group_by_physical_rows()

        # skip if only one row
        num = len(rows)
        if num==1: return rows

        # standard row width with first row excluded, considering potential indentation of fist line
        W = max(row[-1].bbox[2]-row[0].bbox[0] for row in rows[1:])
        H = sum(row[0].bbox[3]-row[0].bbox[1] for row in rows) / num

        # check row by row
        res = []
        lines = Lines()
        punc = tuple(constants.SENTENSE_END_PUNC)
        start_of_para = end_of_para = False # start/end of paragraph
        start_of_sen = end_of_sen = False   # start/end of sentense
        for row in rows:
            end_of_sen = row[-1].text.strip().endswith(punc)
            w =  row[-1].bbox[2]-row[0].bbox[0]

            # end of a sentense and free space at the end -> end of paragraph
            if end_of_sen and w/W <= 1.0-line_break_free_space_ratio:
                end_of_para = True

            # start of sentense and free space at the start -> start of paragraph
            elif start_of_sen and (W-w)/H >= new_paragraph_free_space_ratio:
                start_of_para = True

            # take action
            if end_of_para:
                lines.extend(row)
                res.append(lines)
                lines = Lines()
            elif start_of_para:
                res.append(lines)
                lines = Lines()
                lines.extend(row)
            else:
                lines.extend(row)

            # for next round
            start_of_sen = end_of_sen
            start_of_para = end_of_para = False
        
        # close the action
        if lines: res.append(lines)

        return res


    def strip(self, delete_end_line_hyphen:bool):
        '''Remove redundant blanks of each line and update bbox accordingly.'''
        # strip each line and update bbox: 
        # keep at least one blank at both sides in case extra blanks existed
        strip_status = []
        strip_status.extend([line.strip() for line in self._instances])
        stripped = any(strip_status)
        if stripped: self._parent.update_bbox(self.bbox) # update bbox        

        # word process:
        # - it might miss blank between words from adjacent lines
        # - it's optional to delete hyphen since it might not at the line end
        #   after conversion

        punc_ex_hyphen = ''.join(c for c in string.punctuation if c!='-')
        def is_end_of_english_word(c):
            return c.isalnum() or (c and c in punc_ex_hyphen)
        
        for i, line in enumerate(self._instances[:-1]):
            # last char in this line
            end_span = line.spans[-1]
            if not isinstance(end_span, TextSpan): continue
            end_chars = end_span.chars
            if not end_chars: continue 
            end_char = end_chars[-1]

            # first char in next line
            start_span = self._instances[i+1].spans[0]
            if not isinstance(start_span, TextSpan): continue
            start_chars = start_span.chars
            if not start_chars: continue 
            next_start_char = start_chars[0]            

            # delete hyphen if next line starts with lower case letter
            if delete_end_line_hyphen and \
                end_char.c.endswith('-') and next_start_char.c.islower(): 
                end_char.c = '' # delete hyphen in a tricky way


            # add a space if both the last char and the first char in next line are alphabet,  
            # number, or English punctuation (excepting hyphen)
            if is_end_of_english_word(end_char.c) and is_end_of_english_word(next_start_char.c):
                end_char.c += ' ' # add blank in a tricky way
            
        return stripped


    def sort(self):
        '''Sort lines considering text direction.

        Taking natural reading direction for example: reading order for rows, from left to 
        right for lines in row.

        In the following example, A should come before B.

        ::

                         +-----------+
            +---------+  |           |
            |   A     |  |     B     |
            +---------+  +-----------+
        
        Steps:

            * Sort lines in reading order, i.e. from top to bottom, from left to right.
            * Group lines in row.
            * Sort lines in row: from left to right.
        '''
        # sort in reading order
        self.sort_in_reading_order()

        # split lines in separate row
        lines_in_rows = [] # type: list[list[Line]]

        for line in self._instances:

            # add lines to a row group if not in same row with previous line
            if not lines_in_rows or not line.in_same_row(lines_in_rows[-1][-1]):
                lines_in_rows.append([line])
            
            # otherwise, append current row group
            else:
                lines_in_rows[-1].append(line)
        
        # sort lines in each row: consider text direction
        idx = 0 if self.is_horizontal_text else 3
        self._instances = []
        for row in lines_in_rows:
            row.sort(key=lambda line: line.bbox[idx])
            self._instances.extend(row)


    def is_flow_layout(self, float_layout_tolerance:float, line_separate_threshold:float):
        '''Check if flow layout. 
        
        A flow layout satisfy condition that lines in each physical row have:
        
        * same original text block
        * enough overlap in vertical direction.
        * no significant gap between adjacent two lines.
        '''
        # group lines in same row
        fun = lambda a, b: a.horizontally_align_with(b, factor=float_layout_tolerance) and \
                            not a.vertically_align_with(b, factor=constants.FACTOR_ALMOST) 
        groups = self.group(fun)        
        
        # check each row
        idx = 0 if self.is_horizontal_text else 3
        for lines in groups:
            num = len(lines)
            if num==1: continue

            # same original parent
            if not all(line.same_source_parent(lines[0]) for line in lines):
                return False

            # check vertical overlap
            if not all(line.in_same_row(lines[0]) for line in lines):
                return False

            # check distance between lines
            for i in range(1, num):
                dis = abs(lines[i].bbox[idx]-lines[i-1].bbox[(idx+2)%4])
                if dis >= line_separate_threshold: return False

        return True


    def parse_text_format(self, rect):
        '''Parse text format with style represented by rectangle shape.
        
        Args:
            rect (Shape): Potential style shape applied on blocks.
        
        Returns:
            bool: Whether a valid text style.
        '''
        flag = False

        for line in self._instances:
            # any intersection in this line?
            intsec = rect.bbox & line.get_expand_bbox(constants.MAJOR_DIST)
            
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


    def parse_line_break(self, bbox, 
                line_break_width_ratio:float, 
                line_break_free_space_ratio:float,
                condense_char_spacing:float):
        '''Whether hard break each line. In addition, condense charaters at end of line to avoid unexpected 
        line break. PDF sets precisely width of each word, here just an approximation to set condense spacing
        for last two words.

        Args:
            bbox (Rect): bbox of parent layout, e.g. page or cell.
            line_break_width_ratio (float): user defined threshold, break line if smaller than this value.
            line_break_free_space_ratio (float): user defined threshold, break line if exceeds this value.
            condense_char_spacing (float): user defined condense char spacing to avoid unexpected line break.

        Hard line break helps ensure paragraph structure, but pdf-based layout calculation may
        change in docx due to different rendering mechanism like font, spacing. For instance, when
        one paragraph row can't accommodate a Line, the hard break leads to an unnecessary empty row.
        Since we can't 100% ensure a same structure, it's better to focus on the content - add line
        break only when it's necessary to, e.g. short lines.
        '''

        block = self.parent        
        idx0, idx1 = (0, 2) if block.is_horizontal_text else (3, 1)
        block_width = abs(block.bbox[idx1]-block.bbox[idx0])
        layout_width = bbox[idx1] - bbox[idx0]

        # hard break if exceed the width ratio
        line_break = block_width/layout_width <= line_break_width_ratio

        # check by each physical row
        rows = self.group_by_physical_rows()
        single_row = len(rows)==1
        for lines in rows:
            # ----------------------------
            # line break
            # ----------------------------
            for line in lines: line.line_break = 0

            # check the end line depending on text alignment
            if block.alignment == TextAlignment.RIGHT:
                end_line = lines[0]
                free_space = abs(block.bbox[idx0]-end_line.bbox[idx0])
            else:
                end_line = lines[-1]
                free_space = abs(block.bbox[idx1]-end_line.bbox[idx1])
            
            if block.alignment == TextAlignment.CENTER: free_space *= 2 # two side space
            
            # break line if 
            # - width ratio lower than the threshold; or 
            # - free space exceeds the threshold
            if line_break or free_space/block_width > line_break_free_space_ratio:
                end_line.line_break = 1

            # ----------------------------
            # character spacing
            # ----------------------------
            row_width = abs(lines[-1].bbox[idx1]-lines[0].bbox[idx0])
            if block_width-row_width>constants.MINOR_DIST: continue
            last_span = lines[-1].spans[-1]
            if isinstance(last_span, TextSpan) and not single_row: 
                # condense characters if negative value
                last_span.char_spacing = condense_char_spacing

        
        # no break for last row
        for line in rows[-1]: line.line_break = 0


    def make_docx(self, p):
        '''Create lines in paragraph.'''
        block = self.parent        
        idx0, idx1 = (0, 2) if block.is_horizontal_text else (3, 1)
        current_pos = block.left_space
        
        for i, line in enumerate(self._instances):
            # left indentation implemented with tab
            pos = block.left_space + (line.bbox[idx0]-block.bbox[idx0])
            if pos>block.left_space and block.tab_stops: # sometimes set by first line indentation
                add_stop(p, Pt(pos), Pt(current_pos))

            # add line
            line.make_docx(p)

            # update stop position            
            if line==self._instances[-1]: break
            if line.in_same_row(self._instances[i+1]):
                current_pos = pos + abs(line.bbox[idx1]-block.bbox[idx0])
            else:
                current_pos = block.left_space