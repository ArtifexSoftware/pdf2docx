# -*- coding: utf-8 -*-

'''
Object with a boundary box, e.g. Block, Line, Span.
'''

import copy
import fitz
from .utils import get_main_bbox

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
        '''top-left, bottom-right points of bbox, (x0, y0, x1, y1).'''
        return self._bbox

    @property
    def bbox(self):
        '''bbox in fitz.Rect type.'''
        return fitz.Rect(self._bbox) if self._bbox else fitz.rect()

    def copy(self):
        '''make a deep copy.'''
        return copy.deepcopy(self)

    def update(self, rect):
        '''Update current bbox to specified `rect`.
            ---
            Args:
              - rect: fitz.rect or raw bbox like (x0, y0, x1, y1)
        '''
        fitz_rect = fitz.Rect(rect)
        bbox = (fitz_rect.x0, fitz_rect.y0, fitz_rect.x1, fitz_rect.y1)
        self._bbox = tuple([round(x,1) for x in bbox])
        return self

    def union(self, rect):
        '''Update current bbox to the union with specified `rect`.
            ---
            Args:
              - rect: fitz.rect or raw bbox like (x0, y0, x1, y1)
        '''
        fitz_rect = self.bbox | fitz.Rect(rect)
        return self.update(fitz_rect)


    def compare(self, bbox, threshold=0.9):
        '''Whether has same type and bbox.'''
        if not isinstance(bbox, self.__class__):
            return False, f'Inconsistent type: {self.__class__} v.s. {bbox.__class__}'
        
        if not get_main_bbox(self.bbox, bbox.bbox, threshold):
            return False, f'Inconsistent bbox: ({self.bbox_raw}) v.s. ({bbox.bbox_raw})'
        
        return True, ''

    def store(self):
        '''Store in json format.'''
        return { 'bbox': self._bbox }