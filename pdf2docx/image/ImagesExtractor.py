# -*- coding: utf-8 -*-

'''Extract images from PDF.

Both raster images and vector graphics are considered:

* Normal images like jpeg or png could be extracted with method ``page.get_text('rawdict')`` 
  and ``Page.get_images()``. Note the process for png images with alpha channel.
* Vector graphics are actually composed of a group of paths, represented by operators like
  ``re``, ``m``, ``l`` and ``c``. They're detected by finding the contours with ``opencv``.
'''

import fitz
from ..common.share import BlockType
from ..common.algorithm import (recursive_xy_cut, inner_contours, xy_project_profile)


class ImagesExtractor:
    def __init__(self, page:fitz.Page) -> None:
        '''Extract images from PDF page.
        
        Args:
            page (fitz.Page): pdf page to extract images.
        '''
        self._page = page


    def extract_images(self, clip_image_res_ratio:float=3.0):
        '''Extract normal images with ``Page.get_images()``.

        Args:
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            list: A list of extracted and recovered image raw dict.
        
        .. note::
            ``Page.get_images()`` contains each image only once, which may less than the real count of images in a page.
        '''
        # pdf document
        doc = self._page.parent
        rotation = self._page.rotation

        # check each image item:
        # (xref, smask, width, height, bpc, colorspace, ...)
        images = []
        for item in self._page.get_images(full=True):
            item = list(item)
            item[-1] = 0

            # recover image
            pix = self._recover_pixmap(doc, item)
            
            # find all occurrences referenced to this image            
            rects = self._page.get_image_rects(item)

            # ignore images outside page
            for bbox in rects:
                if not self._page.rect.intersects(bbox): continue

                # regarding images consist of alpha values only, i.e. colorspace is None,
                # the turquoise color shown in the PDF is not part of the image, but part of PDF background.
                # So, just to clip page pixmap according to the right bbox
                # https://github.com/pymupdf/PyMuPDF/issues/677
                if not pix.colorspace:
                    pix = self._clip_page(bbox, zoom=clip_image_res_ratio)

                raw_dict = self._to_raw_dict(pix, bbox)

                # rotate image with opencv if page is rotated
                if rotation: 
                    raw_dict['image'] = self._rotate_image(raw_dict['image'], -rotation)

                images.append(raw_dict)

        return images
    

    def extract_image(self, bbox:fitz.Rect=None, clip_image_res_ratio:float=3.0):
        '''Clip page pixmap (without text) according to ``bbox`` and convert to source image.

        Args:
            bbox (fitz.Rect, optional): Target area to clip. Defaults to None, i.e. entire page.
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap. Defaults to 3.0.

        Returns:
            list: A list of image raw dict.
        '''
        pix = self._page.get_pixmap(clip=bbox, matrix=fitz.Matrix(clip_image_res_ratio, clip_image_res_ratio))
        return self._to_raw_dict(pix, bbox)


    def detect_svg_contours(self, min_svg_gap_dx:float, min_svg_gap_dy:float, min_w:float, min_h:float):
        '''Find contour of potential vector graphics.

        Args:
            min_svg_gap_dx (float): Merge svg if the horizontal gap is less than this value.
            min_svg_gap_dy (float): Merge svg if the vertical gap is less than this value.
            min_w (float): Ignore contours if the bbox width is less than this value.
            min_h (float): Ignore contours if the bbox height is less than this value.

        Returns:
            list: A list of potential svg region: (external_bbox, inner_bboxes:list).
        '''
        import cv2 as cv
        import numpy as np

        # clip page and convert to opencv image
        img_byte = self._clip_page(zoom=1.0).tobytes()
        src = cv.imdecode(np.frombuffer(img_byte, np.uint8), cv.IMREAD_COLOR)

        # gray and binary
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        _, binary = cv.threshold(gray, 253, 255, cv.THRESH_BINARY_INV)
        
        # external bbox: split images with recursive xy cut
        external_bboxes = recursive_xy_cut(binary, min_dx=min_svg_gap_dx, min_dy=min_svg_gap_dy)        
        
        # inner contours
        grouped_inner_bboxes = [inner_contours(binary, bbox, min_w, min_h) for bbox in external_bboxes]

        # combined external and inner contours
        groups = list(zip(external_bboxes, grouped_inner_bboxes))
            
        
        # plot detected images for debug
        debug = False
        if debug:
            # plot projection profile for each sub-image
            for i, (x0, y0, x1, y1) in enumerate(external_bboxes):
                arr = xy_project_profile(src[y0:y1, x0:x1, :], binary[y0:y1, x0:x1])
                cv.imshow(f'sub-image-{i}', arr)

            for bbox, inner_bboxes in groups:
                # plot external bbox
                x0, y0, x1, y1 = bbox
                cv.rectangle(src, (x0, y0), (x1, y1), (255,0,0), 1)

                # plot inner bbox
                for u0, v0, u1, v1 in inner_bboxes:
                    cv.rectangle(src, (u0, v0), (u1, v1), (0,0,255), 1)

            cv.imshow("img", src)
            cv.waitKey(0)

        return groups


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
            'width': image.width,
            'height': image.height,
            'image': image.tobytes()
        }


    @staticmethod
    def _rotate_image(image_bytes, rotation:int):
        '''Rotate image represented by image bytes.

        Args:
            image_bytes (bytes): Image to rotate.
            rotation (int): Rotation angle.
        '''
        import cv2 as cv
        import numpy as np

        # convert to opencv image
        img = cv.imdecode(np.frombuffer(image_bytes, np.uint8), cv.IMREAD_COLOR)        
        h, w = img.shape[:2] # get image height, width

        # calculate the center of the image
        x0, y0 = w//2, h//2

        # default scale value for now -> might be extracted from PDF page property    
        scale = 1.0

        # rotation matrix
        matrix = cv.getRotationMatrix2D((x0, y0), rotation, scale)

        # calculate the final dimension
        cos = np.abs(matrix[0, 0])
        sin = np.abs(matrix[0, 1])
    
        # compute the new bounding dimensions of the image
        W = int((h * sin) + (w * cos))
        H = int((h * cos) + (w * sin))
    
        # adjust the rotation matrix to take into account translation
        matrix[0, 2] += (W / 2) - x0
        matrix[1, 2] += (H / 2) - y0
        
        # perform the rotation holding at the center        
        rotated_img = cv.warpAffine(img, matrix, (W, H))

        # convert back to bytes
        _, im_png = cv.imencode('.png', rotated_img)
        return im_png.tobytes()


    def _hide_page_text(self):
        '''Hide page text before clipping page.'''
        # NOTE: text might exist in both content stream and form object stream
        # - content stream, i.e. direct page content
        # - form object, i.e. contents referenced by this page
        xref_list = [xref for (xref, name, invoker, bbox) in self._page.get_xobjects()]
        xref_list.extend(self._page.get_contents())        

        # render Tr: set the text rendering mode
        # - 3: neither fill nor stroke the text -> invisible
        # read more:
        # - https://github.com/pymupdf/PyMuPDF/issues/257
        # - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf
        doc = self._page.parent # type: fitz.Document
        for xref in xref_list:
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
        return self._page.get_pixmap(clip=bbox, matrix=fitz.Matrix(zoom, zoom)) # type: fitz.Pixmap

   
    @staticmethod
    def _recover_pixmap(doc:fitz.Document, item:list):
        """Restore pixmap with soft mask considered.
        
        References:

            * https://pymupdf.readthedocs.io/en/latest/document.html#Document.getPageImageList        
            * https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-handle-stencil-masks
            * https://github.com/pymupdf/PyMuPDF/issues/670

        Args:
            doc (fitz.Document): pdf document.
            item (list): image instance of ``page.get_images()``.

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
            pix.set_alpha(ba)

        # we may need to adjust something for CMYK pixmaps here -> 
        # recreate pixmap in RGB color space if necessary
        # NOTE: pix.colorspace may be None for images with alpha channel values only
        if pix.colorspace and not pix.colorspace.name in (fitz.csGRAY.name, fitz.csRGB.name):
            pix = fitz.Pixmap(fitz.csRGB, pix)

        return pix