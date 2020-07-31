# -*- coding: utf-8 -*-

'''
Image Span based on same raw data structure with image block.

@created: 2020-07-22
@author: train8808@gmail.com
'''

from ..common import docx
from ..common.BBox import BBox


class ImageSpan(BBox):
    '''Text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(ImageSpan, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.image = raw.get('image', b'')


    def from_image_block(self, image):
        '''Update with image block.
            ---
            Args:
              - image: ImageBlock, target image block
        '''
        self.ext = image.ext
        self.width = image.width
        self.height = image.height
        self.image = image.image
        self.update(image.bbox)
        return self


    def store(self) -> dict:
        res = super().store()
        res.update({
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': '<image>' # drop real content to reduce size
        })
        return res


    def plot(self, page, color:tuple):
        '''Plot image bbox with diagonal lines.
            ---
            Args: 
              - page: fitz.Page object
        '''
        x0, y0, x1, y1 = self.bbox_raw
        page.drawLine((x0, y0), (x1, y1), color=color, width=1)
        page.drawLine((x0, y1), (x1, y0), color=color, width=1)
        page.drawRect(self.bbox, color=color, fill=None, overlay=False)


    def intersect(self, rect):
        '''Create new ImageSpan object with image contained in given bbox.
            ---
            Args:
              - rect: fitz.Rect, target bbox
        '''
        # add image span directly only if fully contained in bbox
        if rect.contains(self.bbox):
            return self.copy()
        
        # otherwise, ignore image
        else:
            return ImageSpan()


    def make_docx(self, paragraph):
        '''Add image span to a docx paragraph.'''
        # add image
        docx.add_image(paragraph, self.image, self.bbox.x1-self.bbox.x0)