# -*- coding: utf-8 -*-

'''
Char object based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---

refer to: https://pymupdf.readthedocs.io/en/latest/textpage.html

raw dict for Char
    {
        'bbox'  : (x0, y0, x1, y1), 
        'c'     : str, 
        'origin': (x,y)
    }
'''


from ..common.BBox import BBox
from ..shape.Rectangle import Rectangle


class Char(BBox):
    '''Object representing a character.'''
    def __init__(self, raw:dict={}) -> None:
        super(Char, self).__init__(raw)
        self.c = raw.get('c', '')
        self.origin = raw.get('origin', None)       


    def contained_in_rect(self, rect:Rectangle, horizontal:bool=True):
        ''' Detect whether locates in a rect, or has an intersection 
            larger than half of the char bbox.
        '''
        # char in rect?
        if self.bbox in rect.bbox:
            return True

        # intersection?
        else:
            intsec = self.bbox & rect.bbox
            if horizontal:
                return intsec.width > 0.5*self.bbox.width
            else:
                return intsec.height > 0.5*self.bbox.height


    def store(self) -> dict:
        res = super().store()
        res.update({
            'c': self.c,
            'origin': self.origin
        })

        return res