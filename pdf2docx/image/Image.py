# -*- coding: utf-8 -*-

'''Image object.

Data structure defined in link https://pymupdf.readthedocs.io/en/latest/textpage.html::

    {
        'type': 1,
        'bbox': (x0,y0,x1,y1),
        'width': w,
        'height': h,
        'image': b'',

        # --- discard properties ---
        'ext': 'png',
        'colorspace': n,
        'xref': xref, 'yref': yref, 'bpc': bpc
    }
'''

import base64
from io import BytesIO
from ..common import docx
from ..common.Element import Element


class Image(Element):
    '''Base image object.'''

    def __init__(self, raw:dict=None):
        if raw is None: raw = {}        
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)

        # source image bytes
        # - image bytes passed from PyMuPDF -> use it directly
        # - base64 encoded string restored from json file -> encode to bytes and decode with base64 -> image bytes 
        image = raw.get('image', b'')
        self.image = image if isinstance(image, bytes) else base64.b64decode(image.encode())
        
        super().__init__(raw)


    @property
    def text(self):
        '''Get an image placeholder ``<image>``.'''
        return '<image>'


    def from_image(self, image):
        '''Update with image block/span.
        
        Args:
            image (Image): Target image block/span.
        '''
        self.width = image.width
        self.height = image.height
        self.image = image.image
        self.update_bbox(image.bbox)
        return self


    def store(self):
        '''Store image with base64 encode.

        * Encode image bytes with base64 -> base64 bytes
        * Decode base64 bytes -> str -> so can be serialized in json formart
        '''
        res = super().store()
        res.update({
            'width': self.width,
            'height': self.height,
            'image': base64.b64encode(self.image).decode() # serialize image with base64
        })

        return res


    def plot(self, page, color:tuple):
        '''Plot image bbox with diagonal lines (for debug purpose).
        
        Args: 
            page (fitz.Page): Plotting page.
        '''
        x0, y0, x1, y1 = self.bbox
        page.draw_line((x0, y0), (x1, y1), color=color, width=0.5)
        page.draw_line((x0, y1), (x1, y0), color=color, width=0.5)
        super().plot(page, stroke=color)


    def make_docx(self, paragraph):
        '''Add image span to a docx paragraph.'''
        # add image
        docx.add_image(paragraph, BytesIO(self.image), self.bbox.x1-self.bbox.x0, self.bbox.y1-self.bbox.y0)