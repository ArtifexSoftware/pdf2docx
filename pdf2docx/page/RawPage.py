# -*- coding: utf-8 -*-

'''A wrapper of ``fitz.Page`` to extract source contents.

The raw page content extracted with ``PyMuPDF`` API ``page.getText('rawdict')`` 
is described per link https://pymupdf.readthedocs.io/en/latest/textpage.html:: 

    {
        # raw dict
        ----------------------------
        "width" : w,
        "height": h,    
        "blocks": [{...}, {...}, ...],

        # introduced dict
        ----------------------------
        "shapes" : [{...}, {...}, ...]
    }

In addition to the raw layout dict, rectangle shapes are also included.
'''

from collections import defaultdict
from ..image.Image import ImagesExtractor
from ..shape.Paths import Paths
from ..common.Element import Element
from ..common.share import RectType, debug_plot


class RawPage:
    '''A wrapper of ``fitz.Page`` to extract source contents.'''

    def __init__(self, fitz_page=None):
        ''' Initialize page layout.
        
        Args:
            fitz_page (fitz.Page): Source pdf page.
        '''
        self.fitz_page = fitz_page
        self.width, self.height = 0, 0


    @property
    def raw_dict(self):
        '''Source data extracted from page by ``PyMuPDF``.'''
        if not self.fitz_page: return {}

        raw_layout = {'id': self.fitz_page.number}

        # source blocks
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout.update(
            self.fitz_page.getText('rawdict')
        )

        # page size: though 'width', 'height' are contained in `raw_dict`, 
        # they are based on un-rotated page. So, update page width/height 
        # to right direction in case page is rotated
        *_, w, h = self.fitz_page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })
        self.width, self.height = w, h

        # pre-processing for layout blocks and shapes based on parent page
        self._preprocess_images(raw_layout)
        self._preprocess_shapes(raw_layout)
        
        # Element is a base class processing coordinates, so set rotation matrix globally
        Element.set_rotation_matrix(self.fitz_page.rotationMatrix)

        return raw_layout


    def _preprocess_images(self, raw):
        '''Adjust image blocks. 
        
        Image block extracted by ``page.getText('rawdict')`` doesn't contain alpha channel data,
        so it needs to get page images by ``page.getImageList()`` and then recover them. However, 
        ``Page.getImageList()`` contains each image only once, while ``page.getText('rawdict')`` 
        generates image blocks for every image location, whether or not there are any duplicates. 
        See PyMuPDF doc:

        https://pymupdf.readthedocs.io/en/latest/textpage.html#dictionary-structure-of-extractdict-and-extractrawdict
            
        Above all, a compromise:

        * Get image contents with ``page.getImageList()`` -> ensure correct images
        * Get image location with ``page.getText('rawdict')`` -> ensure correct locations
        '''
        # recover image blocks
        recovered_images = ImagesExtractor.extract_images(self.fitz_page, 
                                            self.settings['clip_image_res_ratio'])

        # group original image blocks by image contents
        image_blocks_group = defaultdict(list)
        for block in raw['blocks']:
            if block['type'] != 1: continue
            block['type'] = -1 # "delete" it temporally
            image_blocks_group[hash(block['image'])].append(block)
        
        def same_images(img, img_list):
            bbox = list(map(round, img['bbox']))
            for _img in img_list:
                if list(map(round, _img['bbox']))==bbox: return True
            return False

        # An example to show complicated things here:
        # - images in `page.getImageList`: [a, b, c]
        # - images in `page.getText`     : [a1, a2, b, d]
        # (1) a -> a1, a2: an image in page maps to multi-instances in raw dict
        # (2) c: an image in page may not exist in raw dict -> so, add it
        # (3) d: an image in raw dict may not exist in page -> so, delete it
        for image in recovered_images:
            for k, image_blocks in image_blocks_group.items():
                if not same_images(image, image_blocks): continue
                for image_block in image_blocks:
                    image_block['type'] = 1 # add it back
                    image_block['image'] = image['image']
                break

            # an image outside the page is not counted in page.getText(), so let's add it here
            else:
                raw['blocks'].append(image)


    @debug_plot('Source Paths')
    def _preprocess_shapes(self, raw):
        '''Identify iso-oriented paths and convert vector graphic paths to pixmap.'''
        # extract paths ed by `page.getDrawings()`
        raw_paths = self.fitz_page.getDrawings()

        # paths to shapes or images
        paths = Paths(parent=self).restore(raw_paths)
        images, shapes = paths.to_images_and_shapes(
            self.fitz_page,
            self.settings['curve_path_ratio'], 
            self.settings['clip_image_res_ratio']
            )
        raw['blocks'].extend(images)
        raw['shapes'] = shapes

        # Hyperlink is considered as a Shape
        hyperlinks = self._preprocess_hyperlinks(self.fitz_page)
        raw['shapes'].extend(hyperlinks)

        return paths
    

    @staticmethod
    def _preprocess_hyperlinks(page):
        """Get source hyperlink dicts.

        Args:
            page (fitz.Page): pdf page.

        Returns:
            list: A list of source hyperlink dict.
        """
        hyperlinks = []
        for link in page.getLinks():
            if link['kind']!=2: continue # consider internet address only
            hyperlinks.append({
                'type': RectType.HYPERLINK.value,
                'bbox': tuple(link['from']),
                'uri' : link['uri']
            })

        return hyperlinks

