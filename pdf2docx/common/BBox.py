# -*- coding: utf-8 -*-

'''
Object with a boundary box, e.g. Block, Line, Span.
'''

import copy
import fitz


class BBox:
    '''Boundary box with attribute in fitz.Rect type.'''
    def __init__(self, raw:dict={}):
        bbox = raw.get('bbox', (0,0,0,0))
        self._bbox = tuple([round(x,1) for x in bbox])

    def __bool__(self):
        '''Real object when bbox is defined.'''
        return bool(self.bbox)
    
    @property
    def bbox_raw(self):
        return self._bbox

    @property
    def bbox(self):
        return fitz.Rect(self._bbox) if self._bbox else fitz.rect()

    def copy(self):
        return copy.deepcopy(self)

    def update(self, rect):
        fitz_rect = fitz.Rect(rect)
        bbox = (fitz_rect.x0, fitz_rect.y0, fitz_rect.x1, fitz_rect.y1)
        self._bbox = tuple([round(x,1) for x in bbox])
        return self

    def union(self, rect):
        fitz_rect = self.bbox | fitz.Rect(rect)
        return self.update(fitz_rect)

    def store(self):
        return { 'bbox': self._bbox }