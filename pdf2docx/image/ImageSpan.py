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
    def __init__(self, raw:dict={}):
        super(ImageSpan, self).__init__(raw)


    def store(self):
        return super(ImageSpan, self).store_image()


    def plot(self, page, color:tuple):
        '''Plot image bbox with diagonal lines.
            ---
            Args: 
              - page: fitz.Page object
        '''
        x0, y0, x1, y1 = self.bbox
        page.drawLine((x0, y0), (x1, y1), color=color, width=1)
        page.drawLine((x0, y1), (x1, y0), color=color, width=1)
        page.drawRect(self.bbox, color=color, fill=None, overlay=False)


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
        else:
            return ImageSpan()


    def make_docx(self, paragraph):
        '''Add image span to a docx paragraph.'''
        # add image
        docx.add_image(paragraph, self.image, self.bbox.x1-self.bbox.x0)