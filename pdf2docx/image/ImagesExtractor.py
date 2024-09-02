"""Extract images from PDF.

Both raster images and vector graphics are considered:

* Normal images like jpeg or png could be extracted with method ``page.get_text('rawdict')`` 
  and ``Page.get_images()``. Note the process for png images with alpha channel.
* Vector graphics are actually composed of a group of paths, represented by operators like
  ``re``, ``m``, ``l`` and ``c``. They're detected by finding the contours with ``opencv``.
"""

import logging
import fitz
from ..common.Collection import Collection
from ..common.share import BlockType
from ..common.algorithm import recursive_xy_cut, inner_contours, xy_project_profile


class ImagesExtractor:
    """Extract images from PDF."""

    def __init__(self, page: fitz.Page) -> None:
        """Extract images from PDF page.

        Args:
            page (fitz.Page): pdf page to extract images.
        """
        self._page = page

    def clip_page_to_pixmap(
        self, bbox: fitz.Rect = None, rm_image: bool = False, zoom: float = 3.0
    ):
        """Clip page pixmap according to ``bbox``.

        Args:
            bbox (fitz.Rect, optional): Target area to clip. Defaults to None, i.e. entire page.
                Note that ``bbox`` depends on un-rotated page CS, while clipping page is based on
                the final page.
            rm_image (bool): remove images or not.
            zoom (float, optional): Improve resolution by this rate. Defaults to 3.0.

        Returns:
            fitz.Pixmap: The extracted pixmap.
        """
        # hide text and images
        stream_dict = self._hide_page_text_and_images(
            self._page, rm_text=True, rm_image=rm_image
        )

        if bbox is None:
            clip_bbox = self._page.rect

        # transform to the final bbox when page is rotated
        elif self._page.rotation:
            clip_bbox = bbox * self._page.rotation_matrix

        else:
            clip_bbox = bbox

        clip_bbox = self._page.rect & clip_bbox

        # improve resolution
        # - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-increase-image-resolution
        # - https://github.com/pymupdf/PyMuPDF/issues/181
        matrix = fitz.Matrix(zoom, zoom)
        pix = self._page.get_pixmap(clip=clip_bbox, matrix=matrix)  # type: fitz.Pixmap

        # recovery page if hide text
        doc = self._page.parent
        for xref, stream in stream_dict.items():
            doc.update_stream(xref, stream)

        return pix

    def clip_page_to_dict(
        self,
        bbox: fitz.Rect = None,
        rm_image: bool = False,
        clip_image_res_ratio: float = 3.0,
    ):
        """Clip page pixmap (without text) according to ``bbox`` and convert to source image.

        Args:
            bbox (fitz.Rect, optional): Target area to clip. Defaults to None, i.e. entire page.
            rm_image (bool): remove images or not.
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap.
                Defaults to 3.0.

        Returns:
            list: A list of image raw dict.
        """
        pix = self.clip_page_to_pixmap(
            bbox=bbox, rm_image=rm_image, zoom=clip_image_res_ratio
        )
        return self._to_raw_dict(pix, bbox)

    def extract_images(self, clip_image_res_ratio: float = 3.0):
        """Extract normal images with ``Page.get_images()``.

        Args:
            clip_image_res_ratio (float, optional): Resolution ratio of clipped bitmap.
                Defaults to 3.0.

        Returns:
            list: A list of extracted and recovered image raw dict.

        .. note::
            ``Page.get_images()`` contains each image only once, which may less than the
            real count of images in a page.
        """
        # pdf document
        doc = self._page.parent
        rotation = self._page.rotation

        # The final view might be formed by several images with alpha channel only,
        # as shown in issue-123.
        # It's still inconvenient to extract the original alpha/mask image, as a compromise,
        # extract the equivalent image by clipping the union page region for now.
        # https://github.com/dothinking/pdf2docx/issues/123

        # step 1: collect images: [(bbox, item), ..., ]
        ic = Collection()
        for item in self._page.get_images(full=True):
            item = list(item)
            item[-1] = 0

            # find all occurrences referenced to this image
            rects = self._page.get_image_rects(item)
            unrotated_page_bbox = self._page.cropbox  # note the difference to page.rect
            for bbox in rects:
                # ignore small images
                if bbox.get_area() <= 4:
                    continue

                # ignore images outside page
                if not unrotated_page_bbox.intersects(bbox):
                    continue

                # collect images
                ic.append((bbox, item))

        # step 2: group by intersection
        fun = lambda a, b: a[0].intersects(b[0])
        groups = ic.group(fun)

        # step 3: check each group
        images = []
        for group in groups:
            # clip page with the union bbox of all intersected images
            if len(group) > 1:
                clip_bbox = fitz.Rect()
                for bbox, item in group:
                    clip_bbox |= bbox
                raw_dict = self.clip_page_to_dict(
                    clip_bbox, False, clip_image_res_ratio
                )

            else:
                bbox, item = group[0]

                # Regarding images consist of alpha values only, the turquoise color shown in
                # the PDF is not part of the image, but part of PDF background.
                # So, just to clip page pixmap according to the right bbox
                # https://github.com/pymupdf/PyMuPDF/issues/677

                # It's not safe to identify images with alpha values only,
                # - colorspace is None, for pymupdf <= 1.23.8
                # - colorspace is always Colorspace(CS_RGB), for pymupdf==1.23.9-15 -> issue
                # - colorspace is Colorspace(CS_), for pymupdf >= 1.23.16

                # So, use extracted image info directly.
                # image item: (xref, smask, width, height, bpc, colorspace, ...), e.g.,
                # (19, 0, 331, 369, 1, '', '', 'Im1', 'FlateDecode', 0)
                # (20, 24, 1265, 1303, 8, 'DeviceRGB', '', 'Im2', 'FlateDecode', 0)
                # (21, 0, 331, 369, 1, '', '', 'Im3', 'CCITTFaxDecode', 0)
                # (22, 25, 1265, 1303, 8, 'DeviceGray', '', 'Im4', 'DCTDecode', 0)
                # (23, 0, 1731, 1331, 8, 'DeviceGray', '', 'Im5', 'DCTDecode', 0)
                if item[5] == "":
                    raw_dict = self.clip_page_to_dict(bbox, False, clip_image_res_ratio)

                # normal images
                else:
                    # recover image, e.g., handle image with mask, or CMYK color space
                    pix = self._recover_pixmap(doc, item)

                    # rotate image with opencv if page is rotated
                    raw_dict = self._to_raw_dict(pix, bbox)
                    if rotation:
                        raw_dict["image"] = self._rotate_image(pix, -rotation)

            images.append(raw_dict)

        return images

    def detect_svg_contours(
        self, min_svg_gap_dx: float, min_svg_gap_dy: float, min_w: float, min_h: float
    ):
        """Find contour of potential vector graphics.

        Args:
            min_svg_gap_dx (float): Merge svg if the horizontal gap is less than this value.
            min_svg_gap_dy (float): Merge svg if the vertical gap is less than this value.
            min_w (float): Ignore contours if the bbox width is less than this value.
            min_h (float): Ignore contours if the bbox height is less than this value.

        Returns:
            list: A list of potential svg region: (external_bbox, inner_bboxes:list).
        """
        import cv2 as cv

        # clip page and convert to opencv image
        pixmap = self.clip_page_to_pixmap(rm_image=True, zoom=1.0)
        src = self._pixmap_to_cv_image(pixmap)

        # gray and binary
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        _, binary = cv.threshold(gray, 253, 255, cv.THRESH_BINARY_INV)

        # external bbox: split images with recursive xy cut
        external_bboxes = recursive_xy_cut(
            binary, min_dx=min_svg_gap_dx, min_dy=min_svg_gap_dy
        )

        # inner contours
        grouped_inner_bboxes = [
            inner_contours(binary, bbox, min_w, min_h) for bbox in external_bboxes
        ]

        # combined external and inner contours
        groups = list(zip(external_bboxes, grouped_inner_bboxes))

        # plot detected images for debug
        debug = False
        if debug:
            # plot projection profile for each sub-image
            for i, (x0, y0, x1, y1) in enumerate(external_bboxes):
                arr = xy_project_profile(src[y0:y1, x0:x1, :], binary[y0:y1, x0:x1])
                cv.imshow(f"sub-image-{i}", arr)

            for bbox, inner_bboxes in groups:
                # plot external bbox
                x0, y0, x1, y1 = bbox
                cv.rectangle(src, (x0, y0), (x1, y1), (255, 0, 0), 1)

                # plot inner bbox
                for u0, v0, u1, v1 in inner_bboxes:
                    cv.rectangle(src, (u0, v0), (u1, v1), (0, 0, 255), 1)

            cv.imshow("img", src)
            cv.waitKey(0)

        return groups

    @staticmethod
    def _to_raw_dict(image: fitz.Pixmap, bbox: fitz.Rect):
        """Store Pixmap ``image`` to raw dict.

        Args:
            image (fitz.Pixmap): Pixmap to store.
            bbox (fitz.Rect): Boundary box the pixmap.

        Returns:
            dict: Raw dict of the pixmap.
        """
        if image.colorspace.n > 3:  # must convert: we only support PNG
            image = fitz.Pixmap(fitz.csRGB, image)
        return {
            "type": BlockType.IMAGE.value,
            "bbox": tuple(bbox),
            "width": image.width,
            "height": image.height,
            "image": image.tobytes(),
        }

    @staticmethod
    def _rotate_image(pixmap: fitz.Pixmap, rotation: int):
        """Rotate image represented by image bytes.

        Args:
            pixmap (fitz.Pixmap): Image to rotate.
            rotation (int): Rotation angle.

        Return: image bytes.
        """
        import cv2 as cv
        import numpy as np

        # convert to opencv image
        img = ImagesExtractor._pixmap_to_cv_image(pixmap)
        h, w = img.shape[:2]  # get image height, width

        # calculate the center of the image
        x0, y0 = w // 2, h // 2

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
        _, im_png = cv.imencode(".png", rotated_img)
        return im_png.tobytes()

    @staticmethod
    def _hide_page_text_and_images(page: fitz.Page, rm_text: bool, rm_image: bool):
        """Hide page text and images."""
        # NOTE: text might exist in both content stream and form object stream
        # - content stream, i.e. direct page content
        # - form object, i.e. contents referenced by this page
        xref_list = [xref for (xref, name, invoker, bbox) in page.get_xobjects()]
        xref_list.extend(page.get_contents())

        # (1) hide text
        # render Tr: set the text rendering mode
        # - 3: neither fill nor stroke the text -> invisible
        # read more:
        # - https://github.com/pymupdf/PyMuPDF/issues/257
        # - https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/pdf_reference_archives/PDFReference.pdf
        def hide_text(stream):
            res = stream
            found = False
            # set 3 Tr to text block
            for k in ["BT", "Tm", "Td", "2 Tr"]:
                bk = k.encode()
                if bk in stream:
                    found = True
                    res = res.replace(bk, f"{k} 3 Tr".encode())
            return res, found

        # (2) hide image
        # https://github.com/pymupdf/PyMuPDF/issues/338
        def hide_images(stream):
            res = stream
            found = False
            # image names, e.g. [[270, 0, 261, 115, 8, 'DeviceRGB', '', 'Im1', 'DCTDecode']]
            img_names = [item[7] for item in page.get_images(full=True)]
            for k in img_names:
                bk = f"/{k} Do".encode()
                if bk in stream:
                    found = True
                    res = res.replace(bk, b"")
            return res, found

        doc = page.parent  # type: fitz.Document
        source = {}
        for xref in xref_list:
            src = doc.xref_stream(xref)

            # try to hide text
            stream, found_text = hide_text(src) if rm_text else (src, False)

            # try to hide images
            stream, found_images = hide_images(stream) if rm_image else (stream, False)

            if found_text or found_images:
                doc.update_stream(xref, stream)
                source[xref] = src  # save original stream

        return source

    @staticmethod
    def _recover_pixmap(doc: fitz.Document, item: list):
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
            mask = fitz.Pixmap(doc, s)
            if pix.alpha:
                temp = fitz.Pixmap(pix, 0)  # make temp pixmap w/o the alpha
                pix = None  # release storage
                pix = temp

            # check dimension
            if pix.width == mask.width and pix.height == mask.height:
                pix = fitz.Pixmap(pix, mask)  # now compose final pixmap
            else:
                logging.warning(
                    "Ignore image due to inconsistent size of color and mask pixmaps: %s",
                    item,
                )

        # we may need to adjust something for CMYK pixmaps here ->
        # recreate pixmap in RGB color space if necessary
        # NOTE: pix.colorspace may be None for images with alpha channel values only
        if "CMYK" in item[5].upper():
            pix = fitz.Pixmap(fitz.csRGB, pix)

        return pix

    @staticmethod
    def _pixmap_to_cv_image(pixmap: fitz.Pixmap):
        """Convert fitz Pixmap to opencv image.

        Args:
            pixmap (fitz.Pixmap): PyMuPDF Pixmap.
        """
        import cv2 as cv
        import numpy as np

        img_byte = pixmap.tobytes()
        return cv.imdecode(np.frombuffer(img_byte, np.uint8), cv.IMREAD_COLOR)
