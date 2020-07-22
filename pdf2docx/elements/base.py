# -*- coding: utf-8 -*-

'''
Base classes.
'''

import fitz
from enum import Enum


class BlockType(Enum):
    TEXT = 0
    IMAGE = 1
    EXPLICIT_TABLE = 2
    IMPLICIT_TABLE = 3

class RectType(Enum):
    UNDEFINED = -1
    HIGHLIGHT = 0
    UNDERLINE = 1
    STRIKE = 2
    BORDER = 10
    SHADING = 11


class BBox:
    '''Boundary box with attribute in fitz.Rect type.'''
    def __init__(self, raw: dict):
        self._bbox = raw.get('bbox', None)

    @property
    def bbox(self) -> fitz.Rect:
        return fitz.Rect(self._bbox) if self._bbox else fitz.rect()

    def update(self, rect):
        fitz_rect = fitz.Rect(rect)
        self._bbox = (fitz_rect.x0, fitz_rect.y0, fitz_rect.x1, fitz_rect.y1)

    def store(self) -> dict:
        return { 'bbox': self._bbox }
