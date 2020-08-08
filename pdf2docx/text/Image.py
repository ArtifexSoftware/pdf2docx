# -*- coding: utf-8 -*-

'''
Image object.
'''

import fitz
from ..common.BBox import BBox


class Image(BBox):
    '''Base image object.'''
    def __init__(self, raw:dict={}) -> None:
        super(Image, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self._image = raw.get('image', b'')    # source image bytes

    
    @property
    def image(self):
        '''Get the image bytes converted by PyMuPDF.

            The image bytes are existed already in the raw dict, but there is risk facing
            `docx.image.exceptions.UnrecognizedImageError` when recreate image with python-docx.
            As explained in link below:

            https://stackoverflow.com/questions/56405003/unrecognizedimageerror-image-insertion-error-python-docx

            The solution is to convert to bitmap with PyMuPDF in advance.
        '''
        return fitz.Pixmap(self._image).getImageData(output="png") # convert to png image


    def from_image(self, image):
        '''Update with image block.
            ---
            Args:
              - image: Image, target image block
        '''
        self.ext = image.ext
        self.width = image.width
        self.height = image.height
        self._image = image._image
        self.update(image.bbox)
        return self


    def store_image(self):
        res = super().store()
        res.update({
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': '<image>' # drop real content to reduce size
        })

        return res