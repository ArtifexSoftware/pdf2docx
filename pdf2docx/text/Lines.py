# -*- coding: utf-8 -*-

'''A group of Line objects.
'''

from docx.shared import Pt
from .Line import Line
from ..image.ImageSpan import ImageSpan
from ..common.Collection import Collection
from ..common.docx import add_stop
from ..common.share import TextAlignment
from ..common import constants


class Lines(Collection):
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
                print(f'Ignore Line "{line.text}" due to overlap')
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


    def strip(self):
        '''Remove redundant blanks of each line.'''
        # strip each line
        status = [line.strip() for line in self._instances]

        # update bbox
        stripped = any(status)
        if stripped: self._parent.update_bbox(self.bbox)

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


    def group_by_columns(self):
        '''Group lines into columns.'''
        # split in columns
        fun = lambda a,b: a.vertically_align_with(b, text_direction=False)
        groups = self.group(fun)
        
        # NOTE: increasing in x-direction is required!
        groups.sort(key=lambda group: group.bbox.x0)
        return groups


    def group_by_rows(self):
        '''Group lines into rows.'''
        # split in rows, with original text block considered
        fun = lambda a,b: a.horizontally_align_with(b, factor=constants.FACTOR_A_FEW)
        groups = self.group(fun)

        # NOTE: increasing in y-direction is required!
        groups.sort(key=lambda group: group.bbox.y0)

        return groups


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


    def parse_line_break(self, line_free_space_ratio_threshold):
        '''Whether hard break each line.

        Hard line break helps ensure paragraph structure, but pdf-based layout calculation may
        change in docx due to different rendering mechanism like font, spacing. For instance, when
        one paragraph row can't accommodate a Line, the hard break leads to an unnecessary empty row.
        Since we can't 100% ensure a same structure, it's better to focus on the content - add line
        break only when it's necessary to, e.g. explicit free space exists.
        '''
        block = self.parent        
        idx0 = 0 if block.is_horizontal_text else 3
        idx1 = (idx0+2)%4 # H: x1->2, or V: y0->1
        width = abs(block.bbox[idx1]-block.bbox[idx0])

        # space for checking line break
        if block.alignment == TextAlignment.RIGHT:
            delta_space = block.left_space_total - block.left_space
            idx = idx0
        else:
            delta_space = block.right_space_total - block.right_space
            idx = idx1        

        for i, line in enumerate(self._instances):            
            if line==self._instances[-1]: # no more lines after last line
                line.line_break = 0
            
            elif line.in_same_row(self._instances[i+1]):
                line.line_break = 0
            
            # break line if free space exceeds a threshold
            elif (abs(block.bbox[idx]-line.bbox[idx]) + delta_space) / width > line_free_space_ratio_threshold:
                line.line_break = 1
            
            # break line if next line is a only a space (otherwise, MS Word leaves it in previous line)
            elif not self._instances[i+1].text.strip():
                line.line_break = 1
            
            else:
                line.line_break = 0


    def make_docx(self, p):
        '''Create lines in paragraph.'''
        block = self.parent        
        idx0 = 0 if block.is_horizontal_text else 3
        idx1 = (idx0+2)%4 # H: x1->2, or V: y0->1
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