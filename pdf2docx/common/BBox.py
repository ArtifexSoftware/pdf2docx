# -*- coding: utf-8 -*-

'''
Object with a boundary box, e.g. Block, Line, Span.
'''

import fitz


class BBox:
    '''Boundary box with attribute in fitz.Rect type.'''
    def __init__(self, raw: dict) -> None:
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