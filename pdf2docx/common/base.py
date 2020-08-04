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
    EXPLICIT_TABLE = 2
    IMPLICIT_TABLE = 3


class RectType(Enum):
    ''' Rectangle type in context:
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


class PlotControl(Enum):
    ''' Control what to show when plotting blocks.
        - layout         : plot all blocks
        - table          : plot explicit table blocks only
        - implicit_table : plot implicit table blocks only
        - shape          : plot rectangle shapes
    '''
    LAYOUT = 0
    TABLE = 1
    IMPLICIT_TABLE = 2
    SHAPE = 3


class IText:
    '''Text related interface considering text direction.'''
    @property
    def text_direction(self):
        '''Default text direction: from left to right.'''
        return TextDirection.LEFT_RIGHT

    @property
    def is_horizontal(self):
        '''Check whether text direction is from left to right.'''
        return self.text_direction == TextDirection.LEFT_RIGHT

    @property
    def is_vertical(self):
        return self.text_direction == TextDirection.BOTTOM_TOP