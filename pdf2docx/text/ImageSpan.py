# -*- coding: utf-8 -*-

'''
Image Span based on same raw data structure with image block.

@created: 2020-07-22
@author: train8808@gmail.com
'''


from ..common.BBox import BBox


class ImageSpan(BBox):
    '''Text block.'''
    def __init__(self, raw: dict) -> None:
        super(ImageSpan, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.image = raw.get('image', b'')

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
