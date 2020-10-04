# -*- coding: utf-8 -*-

'''
Image Span based on same raw data structure with image block.

@created: 2020-07-22
@author: train8808@gmail.com
'''

from ..common import docx, utils
from .Image import Image


class ImageSpan(Image):
    '''Image span.'''

    def store(self): return super().store_image()


    def intersects(self, rect):
        '''Create new ImageSpan object with image contained in given bbox.
            ---
            Args:
              - rect: fitz.Rect, target bbox
        '''
        # add image span if most of of the image is contained in bbox
        if utils.get_main_bbox(self.bbox, rect, 0.75):
            return self.copy()
        
        # otherwise, ignore image
        return ImageSpan()


    def make_docx(self, paragraph):
        '''Add image span to a docx paragraph.'''
        # add image
        docx.add_image(paragraph, self.image, self.bbox.x1-self.bbox.x0)