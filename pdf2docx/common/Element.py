'''Object with a bounding box, e.g. Block, Line, Span.

Based on ``PyMuPDF``, the coordinates (e.g. bbox of ``page.get_text('rawdict')``) are generally
provided relative to the un-rotated page; while this ``pdf2docx`` library works under real page
coordinate system, i.e. with rotation considered. So, any instances created by this Class are
always applied a rotation matrix automatically.

Therefore, the bbox parameter used to create ``Element`` instance MUST be relative to un-rotated
CS. If final coordinates are provided, should update it after creating an empty object::

    Element().update_bbox(final_bbox)

.. note::
    An exception is ``page.get_drawings()``, the coordinates are converted to real page CS already.
'''

import copy
import fitz
from .share import IText
from . import constants


class Element(IText):
    '''Boundary box with attribute in fitz.Rect type.'''

    # all coordinates are related to un-rotated page in PyMuPDF
    # e.g. Matrix(0.0, 1.0, -1.0, 0.0, 842.0, 0.0)
    ROTATION_MATRIX = fitz.Matrix(0.0) # rotation angle = 0 degree by default


    @classmethod
    def set_rotation_matrix(cls, rotation_matrix):
        """Set global rotation matrix.

        Args:
            Rotation_matrix (fitz.Matrix): target matrix
        """
        if rotation_matrix and isinstance(rotation_matrix, fitz.Matrix):
            cls.ROTATION_MATRIX = rotation_matrix


    @classmethod
    def pure_rotation_matrix(cls):
        '''Pure rotation matrix used for calculating text direction after rotation.'''
        a,b,c,d,e,f = cls.ROTATION_MATRIX
        return fitz.Matrix(a,b,c,d,0,0)


    def __init__(self, raw:dict=None, parent=None):
        ''' Initialize Element and convert to the real (rotation considered) page CS.'''
        self.bbox = fitz.Rect()  # type: fitz.Rect
        self._parent = parent # type: Element

        # NOTE: Any coordinates provided in raw is in original page CS 
        # (without considering page rotation).
        if 'bbox' in (raw or {}):
            rect = fitz.Rect(raw['bbox']) * Element.ROTATION_MATRIX
            self.update_bbox(rect)


    def __bool__(self):
        '''Real object when bbox is defined.'''
        # NOTE inconsistent results of fitz.Rect for different version of pymupdf, e.g.,
        # a = fitz.Rect(3,3,2,2)
        #                   bool(a)      a.get_area()       a.is_empty
        # pymupdf 1.23.5      True            1.0              True
        # pymupdf 1.23.8      True            0.0              True
        # bool(fitz.Rect())==False
        # NOTE: do not use `return not self.bbox.is_empty` here
        return bool(self.bbox)


    def __repr__(self): return f'{self.__class__.__name__}({tuple(self.bbox)})'


    # ------------------------------------------------
    # parent element
    # ------------------------------------------------
    @property
    def parent(self): return self._parent

    @parent.setter
    def parent(self, parent): self._parent = parent


    # ------------------------------------------------
    # bbox operations
    # ------------------------------------------------
    def copy(self):
        '''make a deep copy.'''
        # NOTE: can't serialize data because parent is an Object,
        # so set it None in advance.
        parent, self.parent = self._parent, None
        obj = copy.deepcopy(self)
        self._parent = parent # set back parent
        return obj


    def get_expand_bbox(self, dt:float):
        """Get expanded bbox with margin in both x- and y- direction.

        Args:
            dt (float): Expanding margin.

        Returns:
            fitz.Rect: Expanded bbox.

        .. note::
            This method creates a new bbox, rather than changing the bbox of itself.
        """
        return self.bbox + (-dt, -dt, dt, dt)


    def update_bbox(self, rect):
        '''Update current bbox to specified ``rect``.

        Args:
            rect (fitz.Rect or list): bbox-like ``(x0, y0, x1, y1)``,
                in real page CS (with rotation considered).
        '''
        self.bbox = fitz.Rect([round(x,1) for x in rect])
        return self


    def union_bbox(self, e):
        """Update current bbox to the union with specified Element.

        Args:
            e (Element): The target to get union

        Returns:
            Element: self
        """
        return self.update_bbox(self.bbox | e.bbox)


    # --------------------------------------------
    # location relationship to other Element instance
    # --------------------------------------------
    def contains(self, e:'Element', threshold:float=1.0):
        """Whether given element is contained in this instance, with margin considered.

        Args:
            e (Element): Target element
            threshold (float, optional): Intersection rate.
                Defaults to 1.0. The larger, the stricter.

        Returns:
            bool: [description]
        """
        S = e.bbox.get_area()
        if not S: return False

        # it's not practical to set a general threshold to consider the margin, so two steps:
        # - set a coarse but acceptable area threshold,
        # - check the length in main direction strictly
        # A contains B => A & B = B
        intersection = self.bbox & e.bbox
        factor = round(intersection.get_area()/S, 2)
        if factor<threshold: return False

        # check length
        if self.bbox.width >= self.bbox.height:
            return self.bbox.width+constants.MINOR_DIST >= e.bbox.width
        return self.bbox.height+constants.MINOR_DIST >= e.bbox.height


    def get_main_bbox(self, e, threshold:float=0.95):
        """If the intersection with ``e`` exceeds the threshold, return the union of
        these two elements; else return None.

        Args:
            e (Element): Target element.
            threshold (float, optional): Intersection rate. Defaults to 0.95.

        Returns:
            fitz.Rect: Union bbox or None.
        """
        bbox_1 = self.bbox
        bbox_2 = e.bbox if hasattr(e, 'bbox') else fitz.Rect(e)

        # areas
        b = bbox_1 & bbox_2
        if b.is_empty: return None # no intersection

        # Note: if bbox_1 and bbox_2 intersects with only an edge, b is not empty but b.get_area()=0
        # so give a small value when they're intersected but the area is zero
        a1, a2, a = bbox_1.get_area(), bbox_2.get_area(), b.get_area()
        factor = a/min(a1,a2) if a else 1e-6
        return bbox_1 | bbox_2 if factor >= threshold else None


    def vertically_align_with(self, e, factor:float=0.0, text_direction:bool=True):
        '''Check whether two Element instances have enough intersection in vertical direction,
        i.e. perpendicular to reading direction.

        Args:
            e (Element): Object to check with
            factor (float, optional): Threshold of overlap ratio, the larger it is, the higher
                probability the two bbox-es are aligned.
            text_direction (bool, optional): Consider text direction or not. True by default.

        Returns:
            bool: [description]

        Examples::

            +--------------+
            |              |
            +--------------+
                    L1
                    +-------------------+
                    |                   |
                    +-------------------+
                            L2

        An enough intersection is defined based on the minimum width of two boxes::

            L1+L2-L>factor*min(L1,L2)
        '''
        if not e or not bool(self): return False

        # text direction
        idx = 1 if text_direction and self.is_vertical_text else 0

        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = e.bbox[idx+2]-e.bbox[idx]
        L = max(self.bbox[idx+2], e.bbox[idx+2]) - min(self.bbox[idx], e.bbox[idx])

        eps = 1e-3 # tolerant
        return L1+L2-L+eps >= factor*min(L1,L2)


    def horizontally_align_with(self, e, factor:float=0.0, text_direction:bool=True):
        '''Check whether two Element instances have enough intersection in horizontal direction,
        i.e. along the reading direction.

        Args:
            e (Element): Element to check with
            factor (float, optional): threshold of overlap ratio, the larger it is, the higher
                probability the two bbox-es are aligned.
            text_direction (bool, optional): consider text direction or not. True by default.

        Examples::

            +--------------+
            |              | L1  +--------------------+
            +--------------+     |                    | L2
                                 +--------------------+

        An enough intersection is defined based on the minimum width of two boxes::

            L1+L2-L>factor*min(L1,L2)
        '''
        if not e or not bool(self): return False

        # text direction
        idx = 0 if text_direction and self.is_vertical_text else 1

        L1 = self.bbox[idx+2]-self.bbox[idx]
        L2 = e.bbox[idx+2]-e.bbox[idx]
        L = max(self.bbox[idx+2], e.bbox[idx+2]) - min(self.bbox[idx], e.bbox[idx])

        eps = 1e-3 # tolerant
        return L1+L2-L+eps >= factor*min(L1,L2)


    def in_same_row(self, e):
        """Check whether in same row/line with specified Element instance.
        With text direction considered.

           Taking horizontal text as an example:

           * yes: the bottom edge of each box is lower than the centerline of the other one;
           * otherwise, not in same row.

        Args:
            e (Element): Target object.

        .. note::
            The difference to method ``horizontally_align_with``: they may not in same line, though
            aligned horizontally.
        """
        if not e or self.is_horizontal_text != e.is_horizontal_text:
            return False

        # normal reading direction by default
        idx = 1 if self.is_horizontal_text else 0

        c1 = (self.bbox[idx] + self.bbox[idx+2]) / 2.0
        c2 = (e.bbox[idx] + e.bbox[idx+2]) / 2.0
        res = c1<=e.bbox[idx+2] and c2<=self.bbox[idx+2] # Note y direction under PyMuPDF context
        return res


    # ------------------------------------------------
    # others
    # ------------------------------------------------
    def store(self):
        '''Store properties in raw dict.'''
        return { 'bbox': tuple(x for x in self.bbox) }


    def plot(self, page, stroke:tuple=(0,0,0), width:float=0.5, fill:tuple=None, dashes:str=None):
        '''Plot bbox in PDF page for debug purpose.'''
        page.draw_rect(self.bbox,
                       color=stroke,
                       fill=fill,
                       width=width,
                       dashes=dashes,
                       overlay=False,
                       fill_opacity=0.5)
