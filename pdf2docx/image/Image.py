# -*- coding: utf-8 -*-

'''
Extract images from PDF and define the Image object.

Image properties could be extracted with PyMuPDF method `page.getText('rawdict')`:

```
# data structure defined in link: 
# https://pymupdf.readthedocs.io/en/latest/textpage.html

{
    'type': 1,
    'bbox': (x0,y0,x1,y1),
    'ext': 'png',
    'width': w,
    'height': h,
    'image': b'',

    # --- discard properties ---
    'colorspace': n,
    'xref': xref, 'yref': yref, 'bpc': bpc
}
```

But, the extracted image bytes may be different from the source images in PDF, especially
png images with alpha channel. So, images are extracted separately, and stored in a similar
structure.
'''

import base64
import fitz
from ..common.BBox import BBox
from ..common.pdf import recover_pixmap
from ..common.base import BlockType


class ImagesExtractor:
    '''Extract images from PDF.'''
    
    @staticmethod
    def extract_images(page:fitz.Page):
        '''Get images from current page.'''
        # pdf document
        doc = page.parent

        # check each image item:
        # (xref, smask, width, height, bpc, colorspace, ...)
        images = []
        for item in page.getImageList(full=True): 
            w, h = item[2:4]
            bbox = page.getImageBbox(item[7]) # item[7]: name entry of such an item
            pix = recover_pixmap(doc, item)

            # create an image block with a similar structure with `page.getText('rawdict')`
            images.append({
                'type': BlockType.IMAGE.value,
                'bbox': tuple(bbox),
                'ext': 'png',
                'width': w,
                'height': h,
                'image': pix.getPNGData()
            })
        return images


class Image(BBox):
    '''Base image object.'''
    def __init__(self, raw:dict={}):
        super().__init__(raw)
        self.ext = raw.get('ext', 'png')
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)

        # source image bytes
        # - image bytes passed from PyMuPDF -> use it directly
        # - base64 encoded string restored from json file -> encode to bytes and decode with base64 -> image bytes 
        image = raw.get('image', b'')
        self.image = image if isinstance(image, bytes) else base64.b64decode(image.encode())


    @property
    def text(self):
        '''Return an image placeholder: "<image>".'''
        return '<image>'


    def from_image(self, image):
        '''Update with image block.
            ---
            Args:
              - image: Image, target image block
        '''
        self.ext = image.ext
        self.width = image.width
        self.height = image.height
        self.image = image.image
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
            'image': base64.b64encode(self.image).decode() # serialize image with base64
        })

        return res


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