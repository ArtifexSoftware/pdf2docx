# -*- coding: utf-8 -*-

'''
Base classes.
'''

from enum import Enum


class BlockType(Enum):
    '''Block types.'''
    UNDEFINED = -1
    TEXT = 0
    IMAGE = 1
    LATTICE_TABLE = 2
    STREAM_TABLE = 3


class RectType(Enum):
    ''' Shape type in context:
        - not defined   : -1
        - highlight     : 0
        - underline     : 1
        - strike-through: 2
        - table border  : 10
        - cell shading  : 11
    '''
    UNDEFINED = -1
    HIGHLIGHT = 0
    UNDERLINE = 1
    STRIKE = 2
    BORDER = 10
    SHADING = 11


class TextDirection(Enum):
    '''Block types.'''
    IGNORE     = -1
    LEFT_RIGHT = 0 # from left to right within a line, and lines go from top to bottom
    BOTTOM_TOP = 1 # from bottom to top within a line, and lines go from left to right


class TextAlignment(Enum):
    '''Block types.'''
    LEFT    = 0
    CENTER  = 1
    RIGHT   = 2
    JUSTIFY = 3


class PlotControl(Enum):
    ''' Control what to show when plotting blocks.
        - layout       : plot all blocks and shapes
        - block        : plot all blocks
        - table        : plot lattice table blocks only
        - stream_table : plot stream table blocks only
        - shape        : plot rectangle shapes
    '''
    LAYOUT = 0
    BLOCK  = 1
    TABLE  = 2
    STREAM_TABLE = 3
    SHAPE  = 4


class IText:
    '''Text related interface considering text direction.'''
    @property
    def text_direction(self):
        '''Default text direction: from left to right.'''
        return TextDirection.LEFT_RIGHT

    @property
    def is_horizontal_text(self):
        '''Check whether text direction is from left to right.'''
        return self.text_direction == TextDirection.LEFT_RIGHT

    @property
    def is_vertical_text(self):
        return self.text_direction == TextDirection.BOTTOM_TOP