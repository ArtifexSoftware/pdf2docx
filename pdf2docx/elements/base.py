# -*- coding: utf-8 -*-

'''
Base classes.
'''

import fitz
from enum import Enum


class BlockType(Enum):
    UNDEFINED = -1
    TEXT = 0
    IMAGE = 1
    EXPLICIT_TABLE = 2
    IMPLICIT_TABLE = 3


class RectType(Enum):
    '''
    Rectangle type in context:
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


class BBox:
    '''Boundary box with attribute in fitz.Rect type.'''
    def __init__(self, raw: dict):
        bbox = raw.get('bbox', (0,0,0,0))
        self._bbox = tuple([round(x,1) for x in bbox])

    
    @property
    def bbox_raw(self) -> tuple:
        return self._bbox

    @property
    def bbox(self) -> fitz.Rect:
        return fitz.Rect(self._bbox) if self._bbox else fitz.rect()

    def update(self, rect):
        fitz_rect = fitz.Rect(rect)
        bbox = (fitz_rect.x0, fitz_rect.y0, fitz_rect.x1, fitz_rect.y1)
        self._bbox = tuple([round(x,1) for x in bbox])

    def store(self) -> dict:
        return { 'bbox': self._bbox }


class Spacing:
    '''Spacing used in docx.'''
    def __init__(self, *args, **kwargs):
        # introduced attributes
        self.before_space = None
        self.after_space = None
        self.line_space = None
