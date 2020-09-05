# -*- coding: utf-8 -*-

'''
Object with a bounding box, e.g. Block, Line, Span.

Based on `PyMuPDF`, the coordinates are provided relative to the un-rotated page; while this
`pdf2docx` library works under real page coordinate system, i.e. with rotation considered. 
So, any instances created by this Class are always applied a rotation matrix automatically.

In other words, the bbox parameter used to create BBox instance MUST be relative to un-rotated
CS. If final coordinates are provided, should update it after creating an empty object, e.g.
`BBox().update(final_bbox)`.
'''

import copy
import fitz
from .base import IText
from .utils import get_main_bbox

class BBox(IText):
    '''Boundary box with attribute in fitz.Rect type.'''

    # all coordinates are related to un-rotated page in PyMuPDF
    # e.g. Matrix(0.0, 1.0, -1.0, 0.0, 842.0, 0.0)
    ROTATION_MATRIX = fitz.Matrix(0.0) # rotation angle = 0 degree by default

    @classmethod
    def set_rotation_matrix(cls, rotation_matrix):
        if rotation_matrix and isinstance(rotation_matrix, fitz.Matrix):
            cls.ROTATION_MATRIX = rotation_matrix

    @classmethod
    def pure_rotation_matrix(cls):
        '''Pure rotation matrix used for calculating text direction after rotation.'''
        a,b,c,d,e,f = cls.ROTATION_MATRIX
        return fitz.Matrix(a,b,c,d,0,0)

    def __init__(self, raw:dict={}):
        '''Initialize BBox and convert to the real (rotation considered) page coordinate system.'''
        if 'bbox' in raw:
            rect = fitz.Rect(raw['bbox']) * BBox.ROTATION_MATRIX
        else:
            rect = fitz.Rect()
        self.update(rect)

    def __bool__(self):
        '''Real object when bbox is defined.'''
        return bool(self.bbox)

    def distance(self, bbox:tuple):
        '''x-distance to the given bbox.
            ---
            Args:
            - bbox: container bbox, e.g. the valid docx page region.
        '''
        # NOTE: in PyMuPDF CS, horizontal text direction is dame with positive x-axis,
        # while vertical text is on the contrarory
        idx0, f = (0, 1) if self.is_horizontal else (3, -1)
        dx = (self.bbox[idx0]-bbox[idx0]) * f

        # NOTE: consider modification when exceeds right boundary.
        # dx = max(line.bbox.x1-X1, 0)
        idx1 = (idx0+2) % 4
        dt = max((self.bbox[idx1]-bbox[idx1])*f, 0)

        # this value is generally used to set tab stop in docx, 
        # so prefer a lower value to avoid exceeding line width.
        # 1 pt = 1/28.35 = 0.035 cm
        return int(dx-dt) 
    
   
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
        if not bbox or not bool(self): return False

        # text direction
        is_horizontal = self.is_horizontal if text_direction else True
        idx = 0 if is_horizontal else 1

        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = bbox.bbox[idx+2]-bbox.bbox[idx]
        L = max(self.bbox[idx+2], bbox.bbox[idx+2]) - min(self.bbox[idx], bbox.bbox[idx])

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
        if not bbox or not bool(self): return False

        # text direction
        is_horizontal = self.is_horizontal if text_direction else True
        idx = 1 if is_horizontal else 0
        
        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = bbox.bbox[idx+2]-bbox.bbox[idx]
        L = max(self.bbox[idx+2], bbox.bbox[idx+2]) - min(self.bbox[idx], bbox.bbox[idx])

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
        self.bbox = fitz.Rect([round(x,1) for x in rect])
        return self


    def union(self, bbox):
        '''Update current bbox to the union with specified `rect`.
            ---
            Args:
              - bbox: BBox, the target to get union
        '''
        return self.update(self.bbox | bbox.bbox)


    def compare(self, bbox, threshold=0.9):
        '''Whether has same type and bbox.'''
        if not isinstance(bbox, self.__class__):
            return False, f'Inconsistent type: {self.__class__.__name__} v.s. {bbox.__class__.__name__}'
        
        if not get_main_bbox(self.bbox, bbox.bbox, threshold):
            return False, f'Inconsistent bbox: {self.bbox} v.s. {bbox.bbox}'
        
        return True, ''


    def store(self):
        '''Store in json format.'''
        return { 'bbox': tuple([x for x in self.bbox]) }