# -*- coding: utf-8 -*-

'''A wrapper of ``fitz.Page`` to do the following work:

* extract source contents
* clean up blocks/shapes, e.g. elements out of page
* calculate page margin
* parse page structure roughly, i.e. section and column

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
from .BasePage import BasePage
from ..layout.Layout import Layout
from ..layout.Section import Section
from ..layout.Column import Column
from ..shape.Shape import Hyperlink, Shape
from ..shape.Shapes import Shapes
from ..image.ImagesExtractor import ImagesExtractor
from ..shape.Paths import Paths
from ..font.Fonts import Font, Fonts
from ..text.TextSpan import TextSpan
from ..common.Element import Element
from ..common.Block import Block
from ..common.share import RectType, debug_plot
from ..common import constants
from ..common.Collection import Collection


class RawPage(BasePage, Layout):
    '''A wrapper of ``fitz.Page`` to extract source contents.'''

    def __init__(self, fitz_page=None):
        ''' Initialize page layout.
        
        Args:
            fitz_page (fitz.Page): Source pdf page.
        '''
        BasePage.__init__(self)
        Layout.__init__(self)

        self.fitz_page = fitz_page


    @debug_plot('Source Text Blocks')
    def restore(self, settings:dict):
        '''Initialize layout extracted with ``PyMuPDF``.'''
        raw_dict = self.extract_raw_dict(settings)
        super().restore(raw_dict)
        return self.blocks

    
    @debug_plot('Cleaned Shapes')
    def clean_up(self, settings:dict):
        '''Clean up raw blocks and shapes, e.g. 
        
        * remove negative or duplicated instances,
        * merge text blocks horizontally (preparing for layout parsing)
        * detect semantic type of shapes
        '''
        # clean up blocks first
        self.blocks.clean_up(
            settings['delete_end_line_hyphen'],
            settings['float_image_ignorable_gap'])

        # clean up shapes        
        self.shapes.clean_up(
            settings['max_border_width'], 
            settings['shape_merging_threshold'],
            settings['shape_min_dimension'])
        
        # check shape semantic type
        self.shapes.detect_initial_categories()
        
        return self.shapes


    def process_font(self, fonts:Fonts, default_font:Font):      
        '''Update font properties, e.g. font name, font line height ratio, of ``TextSpan``.
        
        Args:
            fonts (Fonts): Fonts used in current document.
        '''
        # get all text span
        spans = []
        for block in self.blocks:
            for line in block.lines:
                spans.extend([span for span in line.spans if isinstance(span, TextSpan)])

        # check and update font name, line height
        for span in spans:
            font = fonts.get(span.font, default_font)
            span.font = font.name
            span.line_height = font.line_height * span.size


    def calculate_margin(self, settings:dict):
        """Calculate page margin.

        .. note::
            Ensure this method is run right after cleaning up the layout, so the page margin is 
            calculated based on valid layout, and stay constant.
        """
        # Exclude hyperlink from shapes because hyperlink might exist out of page unreasonablely, 
        # while it should always within page since attached to text.
        shapes = Shapes([shape for shape in self.shapes if not isinstance(shape, Hyperlink)])

        # return default margin if no blocks exist
        if not self.blocks and not shapes: return (constants.ITP, ) * 4

        x0, y0, x1, y1 = self.bbox
        u0, v0, u1, v1 = self.blocks.bbox | shapes.bbox

        # margin
        left = max(u0-x0, 0.0)
        right = max(x1-u1-constants.MINOR_DIST, 0.0)
        top = max(v0-y0, 0.0)
        bottom = max(y1-v1, 0.0)

        # reduce calculated top/bottom margin to leave some free space
        top *= settings['page_margin_factor_top']
        bottom *= settings['page_margin_factor_bottom']

        # use normal margin if calculated margin is large enough
        return (
            min(constants.ITP, round(left, 1)), 
            min(constants.ITP, round(right, 1)), 
            min(constants.ITP, round(top, 1)), 
            min(constants.ITP, round(bottom, 1)))


    def parse_section(self, settings:dict):
        '''Detect and create page sections.

        .. note::
            - Only two-columns Sections are considered for now.
            - Page margin must be parsed before this step.
        '''
        # bbox
        X0, Y0, X1, _ = self.working_bbox        
    
        # collect all blocks and shapes
        elements = Collection()
        elements.extend(self.blocks)
        elements.extend(self.shapes)
        
        # check section row by row
        pre_section = Collection()
        pre_num_col = 1
        y_ref = Y0 # to calculate v-distance between sections
        sections = []
        for row in elements.group_by_rows():
            # check column col by col
            cols = row.group_by_columns()
            current_num_col = len(cols)

            # consider 2-cols only
            if current_num_col>2: current_num_col = 1 

            # process exception
            x0, y0, x1, y1 = pre_section.bbox
            if pre_num_col==2 and current_num_col==1:
                # current row belongs to left column?
                cols = pre_section.group_by_columns()
                if row.bbox[2] <= cols[0].bbox[2]:
                    current_num_col = 2
                
                # further check 2-cols -> the height
                elif y1-y0<settings['min_section_height']:
                    pre_num_col = 1                

            elif pre_num_col==2 and current_num_col==2:
                # current 2-cols not align with pre-section ?
                combine = Collection(pre_section)
                combine.extend(row)
                if len(combine.group_by_columns())==1:
                    current_num_col = 1

            # finalize pre-section if different to current section
            if current_num_col!=pre_num_col:
                # create pre-section
                section = self._create_section(pre_num_col, pre_section, (X0, X1), y_ref)
                if section:
                    sections.append(section)
                    y_ref = section[-1].bbox[3]

                # start new section                
                pre_section = Collection(row)
                pre_num_col = current_num_col

            # otherwise, append to pre-section
            else:
                pre_section.extend(row)

        # the final section
        section = self._create_section(current_num_col, pre_section, (X0, X1), y_ref)
        sections.append(section)

        return sections


    def extract_raw_dict(self, settings:dict):
        '''Extract source data from page by ``PyMuPDF``.'''
        if not self.fitz_page: return {}

        # source blocks
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout = self.fitz_page.getText('rawdict')

        # page size: though 'width', 'height' are contained in `raw_dict`, 
        # they are based on un-rotated page. So, update page width/height 
        # to right direction in case page is rotated
        *_, w, h = self.fitz_page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })
        self.width, self.height = w, h

        # pre-processing for layout blocks and shapes based on parent page
        self._preprocess_images(raw_layout, settings)
        self._preprocess_shapes(raw_layout, settings)
       
        # Element is a base class processing coordinates, so set rotation matrix globally
        Element.set_rotation_matrix(self.fitz_page.rotationMatrix)

        return raw_layout


    def _preprocess_images(self, raw, settings:dict):
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
        recovered_images = ImagesExtractor(self.fitz_page). \
                                extract_images(settings['clip_image_res_ratio'])

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
    def _preprocess_shapes(self, raw, settings:dict):
        '''Identify iso-oriented paths and convert vector graphic paths to pixmap.'''
        # extract paths ed by `page.getDrawings()`
        raw_paths = self.fitz_page.getDrawings()

        # iso-oriented paths to shapes
        paths = Paths(parent=self).restore(raw_paths)
        shapes, iso_areas, exist_svg = paths.to_shapes(settings['curve_path_ratio'])
        raw['shapes'] = shapes

        # vector graphics (curved paths in general) to images
        if exist_svg:
            excluding_areas = iso_areas
            excluding_areas.extend([block['bbox'] for block in raw['blocks'] if block['type']==1]) # normal images
            images = ImagesExtractor(self.fitz_page) \
                .extract_vector_graphics(excluding_areas, settings['clip_image_res_ratio'])
            raw['blocks'].extend(images)

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
    

    @staticmethod
    def _create_column(bbox, elements:Collection):
        '''Create column based on bbox and candidate elements: blocks and shapes.'''
        if not bbox: return None
        column = Column().update_bbox(bbox)
        blocks = [e for e in elements if isinstance(e, Block)]
        shapes = [e for e in elements if isinstance(e, Shape)]
        column.assign_blocks(blocks)
        column.assign_shapes(shapes)
        return column


    @staticmethod
    def _create_section(num_col:int, elements:Collection, h_range:tuple, y_ref:float):
        '''Create section based on column count, candidate elements and horizontal boundary.'''
        if not elements: return
        X0, X1 = h_range

        if num_col==1:
            x0, y0, x1, y1 = elements.bbox
            column = RawPage._create_column((X0, y0, X1, y1), elements)
            section = Section(space=0, columns=[column])
            before_space = y0 - y_ref
        else:
            cols = elements.group_by_columns()
            u0, v0, u1, v1 = cols[0].bbox
            m0, n0, m1, n1 = cols[1].bbox
            u = (u1+m0)/2.0
            column_1 = RawPage._create_column((X0, v0, u, v1), elements)
            column_2 = RawPage._create_column((u, n0, X1, n1), elements)
            section = Section(space=0, columns=[column_1, column_2])
            before_space = v0 - y_ref

        section.before_space = round(before_space, 1)
        return section
                

