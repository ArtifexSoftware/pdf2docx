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
from io import BytesIO
from ..common import docx
from ..common.Element import Element
from ..common.share import BlockType


class ImagesExtractor:
    '''Extract images from PDF.'''

    @classmethod
    def to_raw_dict(cls, image:fitz.Pixmap, bbox:fitz.Rect):
        '''Store Pixmap to raw dict.'''
        return {
            'type': BlockType.IMAGE.value,
            'bbox': tuple(bbox),
            'ext': 'png',
            'width': image.width,
            'height': image.height,
            'image': image.getPNGData()
        }


    @classmethod
    def clip_page(cls, page:fitz.Page, bbox:fitz.Rect=None, zoom:float=3.0):
        '''Clip page pixmap (without text) according to `bbox` (entire page by default).
        '''
        # hide text before clip the image only
        # render Tr: set the text rendering mode
        # - 3: neither fill nor stroke the text -> invisible
        # read more:
        # - https://github.com/pymupdf/PyMuPDF/issues/257
        # - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf
        doc = page.parent
        for xref in page.get_contents():
            stream = doc.xrefStream(xref).replace(b'BT', b'BT 3 Tr') \
                                             .replace(b'Tm', b'Tm 3 Tr') \
                                             .replace(b'Td', b'Td 3 Tr')
            doc.updateStream(xref, stream)
        
        # improve resolution
        # - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-increase-image-resolution
        # - https://github.com/pymupdf/PyMuPDF/issues/181
        bbox = page.rect if bbox is None else bbox & page.rect
        image = page.getPixmap(clip=bbox, matrix=fitz.Matrix(zoom, zoom)) # type: fitz.Pixmap
        return cls.to_raw_dict(image, bbox)


    @classmethod
    def extract_images(cls, 
                page:fitz.Page,
                clip_image_res_ratio:float=3.0 # resolution ratio of cliiped bitmap
            ):
        ''' Get images dict based on image contents from `Page.getImageList()`.

            NOTE: Page.getImageList() contains each image only once, which may less than the real
            count if images in a page.
        '''
        # pdf document
        doc = page.parent

        # check each image item:
        # (xref, smask, width, height, bpc, colorspace, ...)
        images = []
        for item in page.getImageList(full=True):
            # should always wrap getImageBbox in a try-except clause, per
            # https://github.com/pymupdf/PyMuPDF/issues/487
            try:
                item = list(item)
                item[-1] = 0
                bbox = page.getImageBbox(item) # item[7]: name entry of such an item
            except ValueError:
                continue

            # ignore images outside page
            if not bbox.intersects(page.rect): continue

            pix = ImagesExtractor.recover_pixmap(doc, item)

            # regarding images consist of alpha values only, i.e. colorspace is None,
            # the turquoise color shown in the PDF is not part of the image, but part of PDF background.
            # So, just to clip page pixmap according to the right bbox
            # https://github.com/pymupdf/PyMuPDF/issues/677
            if not pix.colorspace:
                raw_dict = cls.clip_page(page, bbox, zoom=clip_image_res_ratio)
            else:
                raw_dict = cls.to_raw_dict(pix, bbox)
            images.append(raw_dict)
        return images


    @staticmethod
    def recover_pixmap(doc:fitz.Document, item:list):
        '''Restore pixmap with soft mask considered.
            ---
            - doc: fitz document
            - item: an image item got from page.getImageList()

            Read more:
            - https://pymupdf.readthedocs.io/en/latest/document.html#Document.getPageImageList        
            - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-handle-stencil-masks
            - https://github.com/pymupdf/PyMuPDF/issues/670
        '''
        # data structure of `item`:
        # (xref, smask, width, height, bpc, colorspace, ...)
        x = item[0]  # xref of PDF image
        s = item[1]  # xref of its /SMask

        # base image
        pix = fitz.Pixmap(doc, x)

        # reconstruct the alpha channel with the smask if exists
        if s > 0:        
            # copy of base image, with an alpha channel added
            pix = fitz.Pixmap(pix, 1)  
            
            # create pixmap of the /SMask entry
            ba = bytearray(fitz.Pixmap(doc, s).samples)
            for i in range(len(ba)):
                if ba[i] > 0: ba[i] = 255
            pix.setAlpha(ba)

        # we may need to adjust something for CMYK pixmaps here -> 
        # recreate pixmap in RGB color space if necessary
        # NOTE: pix.colorspace may be None for images with alpha channel values only
        if pix.colorspace and not pix.colorspace.name in (fitz.csGRAY.name, fitz.csRGB.name):
            pix = fitz.Pixmap(fitz.csRGB, pix)

        return pix


class Image(Element):
    '''Base image object.'''

    def __init__(self, raw:dict=None):
        if raw is None: raw = {}        
        self.ext = raw.get('ext', 'png')
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
        self.update_bbox(image.bbox)
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
        page.drawLine((x0, y0), (x1, y1), color=color, width=0.5)
        page.drawLine((x0, y1), (x1, y0), color=color, width=0.5)
        super().plot(page, stroke=color)


    def make_docx(self, paragraph):
        '''Add image span to a docx paragraph.'''
        # add image
        docx.add_image(paragraph, BytesIO(self.image), self.bbox.x1-self.bbox.x0)