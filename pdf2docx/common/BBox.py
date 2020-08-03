# -*- coding: utf-8 -*-

'''
Object with a boundary box, e.g. Block, Line, Span.
'''

import copy
import fitz
from .base import IText
from .utils import get_main_bbox

class BBox(IText):
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
    
   
    def vertically_align_with(self, bbox, factor:float=0.0, text_direction:bool=True):
        ''' Check whether two boxes have enough intersection in vertical direction, i.e. perpendicular to reading direction.
            ---
            Args:
              - bbox: BBox to check with
              - factor: threshold of overlap ratio, the larger it is, the higher probability the two bbox-es are aligned.
              - text_direction: consider text direction or not. True by default, from left to right if False.

            ```
            +--------------+
            |              |
            +--------------+ 
                    L1
                    +-------------------+
                    |                   |
                    +-------------------+
                            L2
            ```
            
            An enough intersection is defined based on the minimum width of two boxes:
            ```
            L1+L2-L>factor*min(L1,L2)
            ```
        '''
        if not bbox: return False

        # text direction
        is_horizontal = self.is_horizontal if text_direction else True
        idx = 0 if is_horizontal else 1

        L1 = self.bbox_raw[idx+2]-self.bbox_raw[idx]
        L2 = bbox.bbox_raw[idx+2]-bbox.bbox_raw[idx]
        L = max(self.bbox_raw[idx+2], bbox.bbox_raw[idx+2]) - min(self.bbox_raw[idx], bbox.bbox_raw[idx])

        return L1+L2-L>=factor*max(L1,L2)


    def horizontally_align_with(self, bbox, factor:float=0.0, text_direction:bool=True):
        ''' Check whether two boxes have enough intersection in horizontal direction, i.e. along the reading direction.
            ---
            Args:
              - bbox: BBox to check with
              - factor: threshold of overlap ratio, the larger it is, the higher probability the two bbox-es are aligned.
              - text_direction: consider text direction or not. True by default, from left to right if False.

            ```
            +--------------+
            |              | L1  +--------------------+
            +--------------+     |                    | L2
                                 +--------------------+
            ```
            
            An enough intersection is defined based on the minimum width of two boxes:
            ```
            L1+L2-L>factor*min(L1,L2)
            ```
        '''
        if not bbox: return False

        # text direction
        is_horizontal = self.is_horizontal if text_direction else True
        idx = 1 if is_horizontal else 0
        
        L1 = self.bbox_raw[idx+2]-self.bbox_raw[idx]
        L2 = bbox.bbox_raw[idx+2]-bbox.bbox_raw[idx]
        L = max(self.bbox_raw[idx+2], bbox.bbox_raw[idx+2]) - min(self.bbox_raw[idx], bbox.bbox_raw[idx])

        return L1+L2-L>=factor*max(L1,L2)


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
            return False, f'Inconsistent type: {self.__class__.__name__} v.s. {bbox.__class__.__name__}'
        
        if self.bbox_raw!=bbox.bbox_raw and not get_main_bbox(self.bbox, bbox.bbox, threshold):
            return False, f'Inconsistent bbox: {self.bbox_raw} v.s. {bbox.bbox_raw}'
        
        return True, ''

    def store(self):
        '''Store in json format.'''
        return { 'bbox': self._bbox }