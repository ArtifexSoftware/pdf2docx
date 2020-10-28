# -*- coding: utf-8 -*-

'''
Object with a bounding box, e.g. Block, Line, Span.

Based on `PyMuPDF`, the coordinates are provided relative to the un-rotated page; while this
`pdf2docx` library works under real page coordinate system, i.e. with rotation considered. 
So, any instances created by this Class are always applied a rotation matrix automatically.

In other words, the bbox parameter used to create BBox instance MUST be relative to un-rotated
CS. If final coordinates are provided, should update it after creating an empty object, e.g.
`BBox().update_bbox(final_bbox)`.
'''

import copy
import fitz
from .base import IText
from . import constants


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


    def __init__(self, raw:dict=None):
        ''' Initialize BBox and convert to the real (rotation considered) page coordinate system.'''        
        self.bbox = fitz.Rect()

        # NOTE: Any coordinates provided in raw is in original page CS (without considering page rotation).
        if raw is None: raw = {}
        if 'bbox' in raw:
            rect = fitz.Rect(raw['bbox']) * BBox.ROTATION_MATRIX
            self.update_bbox(rect)


    def __bool__(self):
        '''Real object when bbox is defined.'''
        return bool(self.bbox)
    

    def __repr__(self): return f'{self.__class__.__name__}({tuple(self.bbox)})'


    # ------------------------------------------------
    # bbox operations
    # ------------------------------------------------
    def copy(self):
        '''make a deep copy.'''
        return copy.deepcopy(self)


    def get_expand_bbox(self, dt:float):
        '''Get expanded bbox with margin dt in both x- and y- direction. Note this method doesn't change its bbox.'''
        return self.bbox + (-dt, -dt, dt, dt)


    def update_bbox(self, rect):
        '''Update current bbox to specified `rect`.
            ---
            Args:
              - rect: fitz.rect or raw bbox like (x0, y0, x1, y1) in real page CS (with rotation considered).
        '''
        self.bbox = fitz.Rect([round(x,1) for x in rect])
        return self


    def union_bbox(self, bbox):
        '''Update current bbox to the union with specified `rect`.
            ---
            Args:
              - bbox: BBox, the target to get union
        '''
        return self.update_bbox(self.bbox | bbox.bbox)


    # --------------------------------------------
    # location relationship to other Bbox
    # -------------------------------------------- 
    def contains(self, bbox, threshold:float=1.0):
        '''Whether given bbox is contained in this instance, with margin considered.'''
        # it's not practical to set a general threshold to consider the margin, so two steps:
        # - set a coarse but acceptable area threshold,
        # - check the length in main direction strictly

        if not bbox: return False

        # A contains B => A & B = B
        intersection = self.bbox & bbox.bbox
        factor = round(intersection.getArea()/bbox.bbox.getArea(), 2)
        if factor<threshold: return False

        # check length
        if self.bbox.width >= self.bbox.height:
            return self.bbox.width+constants.MINOR_DIST >= bbox.bbox.width
        else:
            return self.bbox.height+constants.MINOR_DIST >= bbox.bbox.height
   

    def get_main_bbox(self, bbox, threshold:float=0.95):
        ''' If the intersection with `bbox` exceeds the threshold, return the union of
            these two bbox-es; else return None.
        '''
        bbox_1 = self.bbox
        bbox_2 = bbox.bbox if hasattr(bbox, 'bbox') else fitz.Rect(bbox)
        
        # areas
        b = bbox_1 & bbox_2
        if not b: return None # no intersection

        a1, a2, a = bbox_1.getArea(), bbox_2.getArea(), b.getArea()        

        # Note: if bbox_1 and bbox_2 intersects with only an edge, b is not empty but b.getArea()=0
        # so give a small value when they're intersected but the area is zero
        factor = a/min(a1,a2) if a else 1e-6
        return bbox_1 | bbox_2 if factor >= threshold else None


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
        is_horizontal_text = self.is_horizontal_text if text_direction else True
        idx = 0 if is_horizontal_text else 1

        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = bbox.bbox[idx+2]-bbox.bbox[idx]
        L = max(self.bbox[idx+2], bbox.bbox[idx+2]) - min(self.bbox[idx], bbox.bbox[idx])

        return L1+L2-L>=factor*min(L1,L2)


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
        is_horizontal_text = self.is_horizontal_text if text_direction else True
        idx = 1 if is_horizontal_text else 0
        
        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = bbox.bbox[idx+2]-bbox.bbox[idx]
        L = max(self.bbox[idx+2], bbox.bbox[idx+2]) - min(self.bbox[idx], bbox.bbox[idx])
        return L1+L2-L>=factor*min(L1,L2)


    def in_same_row(self, bbox):
        ''' Check whether in same row/line with specified BBox instance. Note text direction.

            taking horizontal text as an example:
            - yes: the bottom edge of each box is lower than the centerline of the other one;
            - otherwise, not in same row.

            Note the difference with method `horizontally_align_with`. They may not in same line, though
            aligned horizontally.
        '''
        if not bbox or self.text_direction != bbox.text_direction:
            return False

        # normal reading direction by default
        idx = 1 if self.is_horizontal_text else 0

        c1 = (self.bbox[idx] + self.bbox[idx+2]) / 2.0
        c2 = (bbox.bbox[idx] + bbox.bbox[idx+2]) / 2.0
        res = c1<=bbox.bbox[idx+2] and c2<=self.bbox[idx+2] # Note y direction under PyMuPDF context
        return res


    # ------------------------------------------------
    # others
    # ------------------------------------------------
    def compare(self, bbox, threshold=0.9):
        '''Whether has same type and bbox.'''
        if not isinstance(bbox, self.__class__):
            return False, f'Inconsistent type: {self.__class__.__name__} v.s. {bbox.__class__.__name__} (expected)'
        
        if not self.get_main_bbox(bbox, threshold):
            return False, f'Inconsistent bbox: {self.bbox} v.s. {bbox.bbox}(expected)'
        
        return True, ''


    def store(self):
        '''Store in json format.'''
        return { 'bbox': tuple([x for x in self.bbox]) }

    
    def plot(self, page, stroke:tuple=(0,0,0), width:float=0.5, fill:tuple=None, dashes:str=None):
        '''Plot bbox in PDF page.'''
        page.drawRect(self.bbox, color=stroke, fill=fill, width=width, dashes=dashes, overlay=False, fill_opacity=0.5)