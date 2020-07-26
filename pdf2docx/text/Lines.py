# -*- coding: utf-8 -*-

'''
A group of Line objects.

@created: 2020-07-24
@author: train8808@gmail.com
'''

from .Line import Line
from ..common import utils
from ..common.Block import Block

class Lines:
    '''Text line list.'''
    def __init__(self, raws:list=[], parent=None) -> None:
        ''' Construct text line from a list of raw line dict.'''
        self._lines = [ Line(raw) for raw in raws ] # type: list[Line]
        self._parent = parent # type: Block


    def __getitem__(self, idx):
        try:
            lines = self._lines[idx]
        except IndexError:
            msg = f'Line index {idx} out of range'
            raise IndexError(msg)
        else:
            return lines


    def __iter__(self):
        return (line for line in self._lines)


    def __len__(self):
        return len(self._lines)


    def append(self, line:Line):
        ''' append a line and update parent's bbox accordingly.'''
        if not line: return
        self._lines.append(line)
        if not self._parent is None: # Note: `if self._parent` does not work here
            self._parent.union(line.bbox)


    def extend(self, lines:list):
        for line in lines:
            self.append(line)


    def insert(self, nth:int, line:Line):
        '''Insert a line and update parent's bbox accordingly.'''
        if not line: return
        self._lines.insert(nth, line)
        if not self._parent is None:
            self._parent.union(line.bbox)


    def store(self) -> list:
        return [ line.store() for line in self._lines]

    
    def merge(self):
        ''' Merge lines aligned horizontally in a block.

            Generally, it is performed when inline image is added into block line.
        '''
        new_lines = [] # type: list[Line]
        for line in self._lines:        
            # add line directly if not aligned horizontally with previous line
            if not new_lines or not utils.is_horizontal_aligned(line.bbox, new_lines[-1].bbox):
                new_lines.append(line)
                continue

            # if it exists x-distance obviously to previous line,
            # take it as a separate line as it is
            if abs(line.bbox.x0-new_lines[-1].bbox.x1) > utils.DM:
                new_lines.append(line)
                continue

            # now, this line will be append to previous line as a span
            new_lines[-1].add(list(line.spans))

        # update lines in block
        self._lines = new_lines

    
    def sort(self):
        ''' Sort lines in a text block.        

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
        self._lines.sort(key=lambda line: (line.bbox.y0, line.bbox.x0))

        # split lines in separate row
        lines_in_rows = [] # type: list[list[Line]]

        for line in self._lines:

            # add lines to a row group if not in same row with previous line
            if not lines_in_rows or not utils.in_same_row(line.bbox, lines_in_rows[-1][-1].bbox):
                lines_in_rows.append([line])
            
            # otherwise, append current row group
            else:
                lines_in_rows[-1].append(line)
        
        # sort lines in each row
        self._lines = []
        for row in lines_in_rows:
            row.sort(key=lambda line: line.bbox.x0)
            self._lines.extend(row)