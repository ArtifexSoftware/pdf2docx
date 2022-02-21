# -*- coding: utf-8 -*-

'''Char object based on PDF raw dict extracted with ``PyMuPDF``.

Data structure refer to this `link <https://pymupdf.readthedocs.io/en/latest/textpage.html>`_::

    {
        'bbox'  : (x0, y0, x1, y1), 
        'c'     : str, 
        'origin': (x,y)
    }
'''


from ..common.constants import INVALID_CHARS
from ..common.Element import Element
from ..shape.Shape import Shape


class Char(Element):
    '''Object representing a character.'''
    def __init__(self, raw:dict=None):
        if raw is None: raw = {}

        # Note to filter control character avoiding error when makeing docx, #126
        c = raw.get('c', '')
        if c in INVALID_CHARS: c = ''
        self.c = c
        self.origin = raw.get('origin', None)

        super().__init__(raw) # NOTE: ignore parent element for Char instance


    def contained_in_rect(self, rect:Shape, horizontal:bool=True):
        """Detect whether it locates in a rect.

        Args:
            rect (Shape): Target rect to check.
            horizontal (bool, optional): Text direction is horizontal if True. Defaults to True.

        Returns:
            bool: Whether a Char locates in target rect.
        
        .. note::
            It's considered as contained in the target rect if the intersection is larger than 
            half of the char bbox.
        """ 
        # char in rect?
        if self.bbox in rect.bbox:
            return True

        # intersection? 
        else:
            intsec = self.bbox & rect.bbox # width=0 if invalid intersection
            if horizontal:
                return intsec.width > 0.5*self.bbox.width
            else:
                return intsec.height > 0.5*self.bbox.height


    def store(self):
        res = super().store()
        res.update({
            'c': self.c,
            'origin': self.origin
        })

        return res