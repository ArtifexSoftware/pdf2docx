# -*- coding: utf-8 -*-

'''Extract images from PDF.

Both raster images and vector graphics are considered:

* Normal images like jpeg or png could be extracted with method ``page.getText('rawdict')`` 
  and ``Page.getImageList()``. Note the process for png images with alpha channel.
* Vector graphics are actually composed of a group of paths, represented by operators like
  ``re``, ``m``, ``l`` and ``c``. They're detected by finding the contours with ``opencv``.
'''

import fitz
from ..common.share import BlockType
from ..common.Collection import Collection
from ..common.Element import Element


class ImagesExtractor:
    def __init__(self, page:fitz.Page) -> None:
        '''Extract images from PDF page.
        
        Args:
            page (fitz.Page): pdf page to extract images.
        '''
        self._page = page


    def extract_images(self, clip_image_res_ratio:float=3.0):
        '''Extract normal images with ``Page.getImageList()``.

        Args:
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            list: A list of extracted and recovered image raw dict.
        
        .. note::
            ``Page.getImageList()`` contains each image only once, which may less than the real count of images in a page.
        '''
        # pdf document
        doc = self._page.parent

        # check each image item:
        # (xref, smask, width, height, bpc, colorspace, ...)
        images = []
        for item in self._page.getImageList(full=True):
            # should always wrap getImageBbox in a try-except clause, per
            # https://github.com/pymupdf/PyMuPDF/issues/487
            try:
                item = list(item)
                item[-1] = 0
                bbox = self._page.getImageBbox(item) # item[7]: name entry of such an item
            except ValueError:
                continue

            # ignore images outside page
            if not bbox.intersects(self._page.rect): continue

            # recover image
            pix = self._recover_pixmap(doc, item)

            # regarding images consist of alpha values only, i.e. colorspace is None,
            # the turquoise color shown in the PDF is not part of the image, but part of PDF background.
            # So, just to clip page pixmap according to the right bbox
            # https://github.com/pymupdf/PyMuPDF/issues/677
            if not pix.colorspace:
                pix = self._clip_page(bbox, zoom=clip_image_res_ratio)

            raw_dict = self._to_raw_dict(pix, bbox)
            images.append(raw_dict)
        return images
    

    def extract_vector_graphics(self, exclude_areas:list, clip_image_res_ratio:float=3.0):
        '''Detect and extract vector graphics by clipping associated page area.

        Args:
            exclude_areas (list): A list of bbox-like ``(x0, y0, x1, y1)`` area to exclude, 
                e.g. raster image area, table area.
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            list: A list of extracted and recovered image raw dict.
        
        .. note::
            Contours for vector graphics are detected first with ``opencv-python``.
        '''
        # find contours
        contours = self._detect_svg_contours(exclude_areas)

        # filter contours
        fun = lambda a,b: a.bbox & b.bbox
        groups = contours.group(fun)

        # clip images
        images = []
        for i,group in enumerate(groups):
            bbox = group.bbox
            pix = self._page.getPixmap(clip=bbox, matrix=fitz.Matrix(clip_image_res_ratio, clip_image_res_ratio))
            # pix.save(f'{i}.png')
            raw_dict = self._to_raw_dict(pix, bbox)
            images.append(raw_dict)
        
        return images


    def _detect_svg_contours(self, exclude_areas:list):
        '''Find contour of potential vector graphics.'''
        import cv2 as cv
        import numpy as np

        # clip page and convert to opencv image
        img_byte = self._clip_page(zoom=1.0).getPNGData()
        src = cv.imdecode(np.frombuffer(img_byte, np.uint8), cv.IMREAD_COLOR)        

        # gray and exclude areas      
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        for bbox in exclude_areas:
            x0, y0, x1, y1 = map(int, bbox)
            gray[y0-2:y1+2, x0-2:x1+2] = 255
            # cv.rectangle(src, (x0,y0), (x1,y1), (0,255,0), 1) # plot excluded areas

        # Gauss blur and binary        
        gauss = cv.GaussianBlur(gray, (9,9), 0)
        _, binary = cv.threshold(gauss, 250, 255, cv.THRESH_BINARY_INV)        
        
        # detect contour with opencv
        rows, cols = binary.shape[0:2]
        kernel = cv.getStructuringElement(cv.MORPH_RECT, (cols//50, rows//50))
        dst = cv.morphologyEx(binary, cv.MORPH_CLOSE, kernel) # close
        contours, hierarchy = cv.findContours(dst,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE)
        
        collection = Collection()
        for contour in contours:  
            x, y, w, h = cv.boundingRect(contour)
            e = Element().update_bbox((x,y,x+w,y+h))
            collection.append(e)
            # cv.rectangle(src, (x,y), (x+w,y+h), (255,0,0), 1)  # detected svg bbox
        
        # plot detected images for debug
        # cv.imshow("img", src)
        # cv.waitKey(0)

        return collection


    @staticmethod
    def _to_raw_dict(image:fitz.Pixmap, bbox:fitz.Rect):
        '''Store Pixmap ``image`` to raw dict.

        Args:
            image (fitz.Pixmap): Pixmap to store.
            bbox (fitz.Rect): Boundary box the pixmap.

        Returns:
            dict: Raw dict of the pixmap.
        '''
        return {
            'type': BlockType.IMAGE.value,
            'bbox': tuple(bbox),
            'ext': 'png',
            'width': image.width,
            'height': image.height,
            'image': image.getPNGData()
        }


    def _hide_page_text(self):
        '''Hide page text before clipping page.'''
        # render Tr: set the text rendering mode
        # - 3: neither fill nor stroke the text -> invisible
        # read more:
        # - https://github.com/pymupdf/PyMuPDF/issues/257
        # - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf
        doc = self._page.parent # type: fitz.Document

        # NOTE: contents referenced in this page
        for (xref, name, invoker, bbox) in self._page.get_xobjects():
            stream = doc.xref_stream(xref).replace(b'BT', b'BT 3 Tr') \
                                             .replace(b'Tm', b'Tm 3 Tr') \
                                             .replace(b'Td', b'Td 3 Tr')
            doc.update_stream(xref, stream)

        # direct page content
        for xref in self._page.get_contents():
            stream = doc.xref_stream(xref).replace(b'BT', b'BT 3 Tr') \
                                             .replace(b'Tm', b'Tm 3 Tr') \
                                             .replace(b'Td', b'Td 3 Tr')
            doc.update_stream(xref, stream)


    def _clip_page(self, bbox:fitz.Rect=None, zoom:float=3.0):
        '''Clip page pixmap (without text) according to ``bbox``.

        Args:
            page (fitz.Page): pdf page to extract.
            bbox (fitz.Rect, optional): Target area to clip. Defaults to None, i.e. entire page.
            zoom (float, optional): Improve resolution by this rate. Defaults to 3.0.

        Returns:
            fitz.Pixmap: The extracted pixmap.
        '''        
        # hide text 
        self._hide_page_text()
        
        # improve resolution
        # - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-increase-image-resolution
        # - https://github.com/pymupdf/PyMuPDF/issues/181
        bbox = self._page.rect if bbox is None else bbox & self._page.rect
        return self._page.getPixmap(clip=bbox, matrix=fitz.Matrix(zoom, zoom)) # type: fitz.Pixmap

   
    @staticmethod
    def _recover_pixmap(doc:fitz.Document, item:list):
        """Restore pixmap with soft mask considered.
        
        References:

            * https://pymupdf.readthedocs.io/en/latest/document.html#Document.getPageImageList        
            * https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-handle-stencil-masks
            * https://github.com/pymupdf/PyMuPDF/issues/670

        Args:
            doc (fitz.Document): pdf document.
            item (list): image instance of ``page.getImageList()``.

        Returns:
            fitz.Pixmap: Recovered pixmap with soft mask considered.
        """
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