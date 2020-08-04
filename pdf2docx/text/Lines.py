# -*- coding: utf-8 -*-

'''
A group of Line objects.

@created: 2020-07-24
@author: train8808@gmail.com
'''


from .Line import Line
from ..common import utils
from ..common.Collection import Collection


class Lines(Collection):
    '''Text line list.'''

    def from_dicts(self, raws:list):
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
            elif utils.get_main_bbox(instance.bbox, line.bbox, threshold=0.5):
                return True
        
        return False

    
    def merge(self):
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
            if abs(line.bbox.x0-lines[-1].bbox.x1) > utils.DM:
                lines.append(line)
                continue

            # now, this line will be append to previous line as a span
            lines[-1].add(list(line.spans))

        # update lines in block
        self.reset(list(lines))


    def split(self):
        ''' Split vertical lines.'''
        # get horizontally aligned lines group by group
        fun = lambda a,b: a.horizontally_align_with(b, factor=0.0)
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
        idx = 0 if self.is_horizontal else 3
        self._instances = []
        for row in lines_in_rows:
            row.sort(key=lambda line: line.bbox_raw[idx])
            self._instances.extend(row)