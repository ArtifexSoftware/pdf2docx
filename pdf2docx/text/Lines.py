# -*- coding: utf-8 -*-

'''
A group of Line objects.

@created: 2020-07-24
@author: train8808@gmail.com
'''

from docx.shared import Pt
from .Line import Line
from ..common.utils import get_main_bbox
from ..common.constants import DM
from ..common.Collection import Collection
from ..common import docx

class Lines(Collection):
    '''Text line list.'''

    @property
    def unique_parent(self):
        '''Whether all contained lines have same parant.'''
        if not bool(self): return False

        first_line = self._instances[0]
        return all(line.same_parent_with(first_line) for line in self._instances)

    def append(self, line:Line):
        '''Override. Append a line and update line pid and parent bbox.'''
        super().append(line)

        # update original parent id
        if not self._parent is None:
            line.pid = id(self._parent)


    def from_dicts(self, raws:list):
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


    def intersects(self, line:Line):
        ''' Whether intersection exists between any line and given line.'''
        is_image_line = bool(line.image_spans)
        for instance in self._instances:

            # for image line, no any intersection is allowed
            if instance.image_spans or is_image_line:
                if instance.bbox.intersects(line.bbox):
                    return True
            
            # otherwise, the overlap tolerance is larger
            elif get_main_bbox(instance.bbox, line.bbox, threshold=0.5):
                return True
        
        return False

    
    def join(self):
        ''' Merge lines aligned horizontally in a block. The main purposes:
            - remove overlapped lines, e.g. floating images
            - make inline image as a span in text line logically
        '''
        # skip if empty
        if not self._instances: return self
    
        # sort lines
        self.sort()

        # check each line
        lines = Lines([self._instances[0]])
        for line in self._instances:
            
            # skip if intersection exists
            if lines.intersects(line):
                continue

            # add line directly if not aligned horizontally with previous line
            if not line.horizontally_align_with(lines[-1]):
                lines.append(line)
                continue

            # if it exists x-distance obviously to previous line,
            # take it as a separate line as it is
            if abs(line.bbox.x0-lines[-1].bbox.x1) > DM:
                lines.append(line)
                continue

            # now, this line will be append to previous line as a span
            lines[-1].add(list(line.spans))

        # update lines in block
        self.reset(lines)


    def split(self):
        ''' Split vertical lines and try to make lines in same original text block grouped together.

            To the first priority considering docx recreation, horizontally aligned lines must be assigned to same group.
            After that, if only one line in each group, lines in same original text block can be group together again 
            even though they are in different physical lines.
        '''
        # split vertically
        # set a non-zero but small factor to avoid just overlaping in same edge
        fun = lambda a,b: a.horizontally_align_with(b, factor=0.1)
        groups = self.group(fun)

        # check count of lines in each group
        for group in groups:
            if len(group) > 1: # first priority
                break
        
        # now one line per group -> docx recreation is fullfilled, 
        # then consider lines in same original text block
        else:
            fun = lambda a,b: a.same_parent_with(b)
            groups = self.group(fun)

        return groups


    def sort(self):
        ''' Sort lines considering text direction.
            Taking natural reading direction for example:
            reading order for rows, from left to right for lines in row.

            In the following example, A should come before B.
            ```
                             +-----------+
                +---------+  |           |
                |   A     |  |     B     |
                +---------+  +-----------+
            ```
            Steps:
              - sort lines in reading order, i.e. from top to bottom, from left to right.
              - group lines in row
              - sort lines in row: from left to right
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


    def group_by_columns(self):
        ''' Group lines into columns.'''
        # sort lines in column first: from left to right, from top to bottom
        self.sort_in_line_order()
        
        #  lines list in each column
        cols_lines = [] # type: list[Lines]

        # collect lines column by column
        col_line = Line()
        for line in self._instances:
            # same column group if vertically aligned
            if col_line.vertically_align_with(line):
                cols_lines[-1].append(line)
            
            # otherwise, start a new column group
            else:
                cols_lines.append(Lines([line]))
                col_line = Line() # reset
                
            col_line.union(line)

        return cols_lines


    def group_by_rows(self):
        ''' Group lines into rows.'''
        # sort lines in row first mode: from top to bottom, from left to right
        self.sort_in_reading_order()

        # collect lines row by row
        rows = [] # type: list[Lines]
        row_line = Line()
        for line in self._instances:
            # same row group if horizontally aligned
            if row_line.horizontally_align_with(line):
                rows[-1].append(line)
            
            # otherwise, start a new row group
            else:
                rows.append(Lines([line]))
                row_line = Line() # reset

            row_line.union(line)
        
        # further step:
        # merge rows if in same original text block
        lines_list = [] # type: list[Lines]
        ref = Lines()
        for row in rows:
            # same parent text block: merge to previous group
            if ref.unique_parent and row.unique_parent and row[0].same_parent_with(ref[0]):
                lines_list[-1].extend(row)
            
            # otherwise, append it directly
            else:
                lines_list.append(row)
            
            # update reference
            ref = row

        return lines_list


    def make_docx(self, p):
        '''Create lines in paragraph.'''
        block = self.parent        
        idx = 0 if block.is_horizontal_text else 3
        current_pos = block.left_space

        for i, line in enumerate(self._instances):

            # left indentation implemented with tab
            pos = block.left_space + (line.bbox[idx]-block.bbox[idx])
            if pos>block.left_space:
                docx.add_stop(p, Pt(pos), Pt(current_pos))

            # add line
            line.make_docx(p)

            # hard line break is necessary, otherwise the paragraph structure may change in docx,
            # which leads to the pdf-based layout calculation becomes wrong
            line_break = True

            # no more lines after last line
            if line==self._instances[-1]: line_break = False            
            
            # do not break line if they're indeed in same line
            elif line.in_same_row(self._instances[i+1]):
                line_break = False
            
            if line_break:
                p.add_run('\n')
                current_pos = block.left_space
            else:
                current_pos = pos + line.bbox.width