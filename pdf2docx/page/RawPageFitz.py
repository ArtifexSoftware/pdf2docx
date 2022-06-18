# -*- coding: utf-8 -*-

'''
A wrapper of PyMuPDF Page as page engine.
'''

from .RawPage import RawPage
from ..image.ImagesExtractor import ImagesExtractor
from ..shape.Paths import Paths
from ..common.constants import FACTOR_A_HALF
from ..common.Element import Element
from ..common.share import (RectType, debug_plot)
from ..common.algorithm import get_area


class RawPageFitz(RawPage):
    '''A wrapper of ``fitz.Page`` to extract source contents.'''

    def extract_raw_dict(self, **settings):
        raw_dict = {}
        if not self.page_engine: return raw_dict

        # actual page size
        *_, w, h = self.page_engine.rect # always reflecting page rotation
        raw_dict.update({ 'width' : w, 'height': h })
        self.width, self.height = w, h

        # pre-processing layout elements. e.g. text, images and shapes
        text_blocks = self._preprocess_text(**settings)
        raw_dict['blocks'] = text_blocks

        image_blocks = self._preprocess_images(**settings)
        raw_dict['blocks'].extend(image_blocks)
        
        shapes, images =  self._preprocess_shapes(**settings)
        raw_dict['shapes'] = shapes
        raw_dict['blocks'].extend(images)

        hyperlinks = self._preprocess_hyperlinks()
        raw_dict['shapes'].extend(hyperlinks)        
       
        # Element is a base class processing coordinates, so set rotation matrix globally
        Element.set_rotation_matrix(self.page_engine.rotation_matrix)

        return raw_dict
    

    def _preprocess_text(self, **settings):
        '''Extract page text and identify hidden text. 
        
        NOTE: All the coordinates are relative to un-rotated page.

            https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
            https://pymupdf.readthedocs.io/en/latest/functions.html#Page.get_texttrace
            https://pymupdf.readthedocs.io/en/latest/textpage.html
        '''
        ocr = settings['ocr']
        if ocr==1: raise SystemExit("OCR feature is planned but not implemented yet.")

        # all text blocks no matter hidden or not
        raw = self.page_engine.get_text('rawdict', flags=64)
        text_blocks = raw.get('blocks', [])

        # ignore hidden text if ocr=0, while extract only hidden text if ocr=2
        if ocr==2:
            f = lambda span: span['type']!=3  # find displayed text and ignore it
        else:
            f = lambda span: span['type']==3  # find hidden text and ignore it

        spans = self.page_engine.get_texttrace()
        filtered_spans = list(filter(f, spans))
        
        def span_area(bbox):
            x0, y0, x1, y1 = bbox
            return (x1-x0) * (y1-y0)

        # filter blocks by checking span intersection: mark the entire block if 
        # any span is matched
        blocks = []
        for block in text_blocks:
            intersected = False
            for line in block['lines']:
                for span in line['spans']:
                    for filter_span in filtered_spans:
                        intersected_area = get_area(span['bbox'], filter_span['bbox'])
                        if intersected_area / span_area(span['bbox']) >= FACTOR_A_HALF \
                            and span['font']==filter_span['font']:
                            intersected = True
                            break
                    if intersected: break # skip further span check if found
                if intersected: break     # skip further line check

            # keep block if no any intersection with filtered span
            if not intersected: blocks.append(block)

        return blocks


    def _preprocess_images(self, **settings):
        '''Extract image blocks. Image block extracted by ``page.get_text('rawdict')`` doesn't 
        contain alpha channel data, so it has to get page images by ``page.get_images()`` and 
        then recover them. Note that ``Page.get_images()`` contains each image only once, i.e., 
        ignore duplicated occurrences.
        '''
        # ignore image if ocr-ed pdf: get ocr-ed text only
        if settings['ocr']==2: return []
        
        return ImagesExtractor(self.page_engine).extract_images(settings['clip_image_res_ratio'])


    def _preprocess_shapes(self, **settings):
        '''Identify iso-oriented paths and convert vector graphic paths to pixmap.'''
        paths = self._init_paths(**settings)
        return paths.to_shapes_and_images(
            settings['min_svg_gap_dx'], 
            settings['min_svg_gap_dy'], 
            settings['min_svg_w'], 
            settings['min_svg_h'], 
            settings['clip_image_res_ratio'])
    

    @debug_plot('Source Paths')
    def _init_paths(self, **settings):
        '''Initialize Paths based on drawings extracted with PyMuPDF.'''
        raw_paths = self.page_engine.get_cdrawings()
        return Paths(parent=self).restore(raw_paths)
    

    def _preprocess_hyperlinks(self):
        """Get source hyperlink dicts.

        Returns:
            list: A list of source hyperlink dict.
        """
        hyperlinks = []
        for link in self.page_engine.get_links():
            if link['kind']!=2: continue # consider internet address only
            hyperlinks.append({
                'type': RectType.HYPERLINK.value,
                'bbox': tuple(link['from']),
                'uri' : link['uri']
            })

        return hyperlinks
