# -*- coding: utf-8 -*-

'''
Image object.
'''


import base64
import fitz
from ..common.BBox import BBox


class Image(BBox):
    '''Base image object.'''
    def __init__(self, raw:dict={}) -> None:
        super(Image, self).__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)

        # source image bytes
        # - image bytes passed from PyMuPDF -> use it directly
        # - base64 encoded string restored from json file -> encode to bytes and decode with base64 -> image bytes 
        image = raw.get('image', b'')
        self._image = image if isinstance(image, bytes) else base64.b64decode(image.encode())


    @property
    def text(self):
        '''Return an image placeholder: "<image>".'''
        return '<image>'

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
        # store image with base64 encode:
        # - encode image bytes with base64 -> base64 bytes
        # - decode base64 bytes -> str -> so can be serialized in json formart
        res.update({
            'ext': self.ext,
            'width': self.width,
            'height': self.height,
            'image': base64.b64encode(self._image).decode() # serialize image with base64
        })

        return res