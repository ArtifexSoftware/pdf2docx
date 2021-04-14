# -*- coding: utf-8 -*-

'''Image span based on same raw data structure with Image block.
'''

from ..common import constants
from .Image import Image


class ImageSpan(Image):
    '''Image span.'''

    def intersects(self, rect):
        '''Create new ImageSpan object with image contained in given bbox.
        
        Args:
            rect (fitz.Rect): Target bbox.
        
        Returns:
            ImageSpan: A copy of itself if intersects with target; otherwise empty ImageSpan. 
        '''
        # add image span if most of of the image is contained in bbox
        if self.get_main_bbox(rect, constants.FACTOR_MAJOR):
            return self.copy()
        
        # otherwise, ignore image
        return ImageSpan()