# -*- coding: utf-8 -*-

'''A wrapper of ``fitz.Page`` to do the following work:

* extract source contents
* clean up blocks/shapes, e.g. elements out of page
* calculate page margin
* parse page structure roughly, i.e. section and column

The raw page content extracted with ``PyMuPDF`` API ``page.get_text('rawdict')`` 
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

from .BasePage import BasePage
from ..layout.Layout import Layout
from ..layout.Section import Section
from ..layout.Column import Column
from ..shape.Shape import Hyperlink
from ..shape.Shapes import Shapes
from ..image.ImagesExtractor import ImagesExtractor
from ..shape.Paths import Paths
from ..font.Fonts import Fonts
from ..text.TextSpan import TextSpan
from ..common.Element import Element
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

    
    @property
    def text(self):
        '''All extracted text in this page, with images considered as ``<image>``. 
        Should be run after ``restore()`` data.'''
        return '\n'.join([block.text for block in self.blocks])

    @property
    def raw_text(self):
        '''Extracted raw text in current page. Should be run after ``restore()`` data.'''
        return '\n'.join([block.raw_text for block in self.blocks])


    @debug_plot('Source Text Blocks')
    def restore(self, **settings):
        '''Initialize layout extracted with ``PyMuPDF``.'''
        raw_dict = self.extract_raw_dict(**settings)
        super().restore(raw_dict)
        return self.blocks

    
    @debug_plot('Cleaned Shapes')
    def clean_up(self, **settings):
        '''Clean up raw blocks and shapes, e.g. 
        
        * remove negative or duplicated instances,
        * detect semantic type of shapes
        '''
        # clean up blocks first
        self.blocks.clean_up(
            settings['float_image_ignorable_gap'],
            settings['line_overlap_threshold'])

        # clean up shapes        
        self.shapes.clean_up(
            settings['max_border_width'],
            settings['shape_min_dimension'])
        
        return self.shapes


    def process_font(self, fonts:Fonts):      
        '''Update font properties, e.g. font name, font line height ratio, of ``TextSpan``.
        
        Args:
            fonts (Fonts): Fonts parsed by ``fonttools``.
        '''
        # get all text span
        spans = []
        for line in self.blocks:
            spans.extend([span for span in line.spans if isinstance(span, TextSpan)])

        # check and update font name, line height
        for span in spans:
            font = fonts.get(span.font)
            if not font: continue

            # update font properties with font parsed by fonttools
            span.font = font.name
            if font.line_height:
                span.line_height = font.line_height * span.size


    def calculate_margin(self, **settings):
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


    def parse_section(self, **settings):
        '''Detect and create page sections.

        .. note::
            - Only two-columns Sections are considered for now.
            - Page margin must be parsed before this step.
        '''
        # bbox
        X0, Y0, X1, _ = self.working_bbox
    
        # collect all blocks (line level) and shapes
        elements = Collection()
        elements.extend(self.blocks)
        elements.extend(self.shapes)
        if not elements: return

        # to create section with collected lines        
        lines = Collection()        
        sections = []
        def close_section(num_col, elements, y_ref):
            # append to last section if both single column
            if sections and sections[-1].num_cols==num_col==1:
                column = sections[-1][0] # type: Column
                column.union_bbox(elements)
                column.add_elements(elements)
            # otherwise, create new section
            else:
                section = self._create_section(num_col, elements, (X0, X1), y_ref)
                if section: 
                    sections.append(section)


        # check section row by row
        pre_num_col = 1
        y_ref = Y0 # to calculate v-distance between sections
        for row in elements.group_by_rows():
            # check column col by col
            cols = row.group_by_columns()
            current_num_col = len(cols)

            # column check:
            # consider 2-cols only
            if current_num_col>2:
                current_num_col = 1
            
            # the width of two columns shouldn't have significant difference
            elif current_num_col==2:
                u0, v0, u1, v1 = cols[0].bbox
                m0, n0, m1, n1 = cols[1].bbox
                x0 = (u1+m0)/2.0
                c1, c2 = x0-X0, X1-x0 # column width
                w1, w2 = u1-u0, m1-m0 # line width
                f = 2.0
                if not 1/f<=c1/c2<=f or w1/c1<0.33 or w2/c2<0.33: 
                    current_num_col = 1

            # process exceptions
            if pre_num_col==2 and current_num_col==1:
                # though current row has one single column, it might have another virtual 
                # and empty column. If so, it should be counted as 2-cols
                cols = lines.group_by_columns()
                pos = cols[0].bbox[2]
                if row.bbox[2]<=pos or row.bbox[0]>pos:
                    current_num_col = 2
                
                # pre_num_col!=current_num_col => to close section with collected lines,
                # before that, further check the height of collected lines
                else:
                    x0, y0, x1, y1 = lines.bbox
                    if y1-y0<settings['min_section_height']:
                        pre_num_col = 1
                

            elif pre_num_col==2 and current_num_col==2:
                # though both 2-cols, they don't align with each other
                combine = Collection(lines)
                combine.extend(row)
                if len(combine.group_by_columns(sorted=False))==1: current_num_col = 1


            # finalize pre-section if different from the column count of previous section
            if current_num_col!=pre_num_col:
                # process pre-section
                close_section(pre_num_col, lines, y_ref)
                if sections: 
                    y_ref = sections[-1][-1].bbox[3]

                # start potential new section                
                lines = Collection(row)
                pre_num_col = current_num_col

            # otherwise, collect current lines for further processing
            else:
                lines.extend(row)

        # don't forget the final section
        close_section(current_num_col, lines, y_ref)

        return sections


    def extract_raw_dict(self, **settings):
        '''Extract source data from page by ``PyMuPDF``.'''
        if not self.fitz_page: return {}

        # source blocks
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        # https://pymupdf.readthedocs.io/en/latest/textpage.html#dictionary-structure-of-extractdict-and-extractrawdict
        raw_layout = self.fitz_page.get_text('rawdict')

        # page size: though 'width', 'height' are contained in `raw_dict`, 
        # they are based on un-rotated page. So, update page width/height 
        # to right direction in case page is rotated
        *_, w, h = self.fitz_page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })
        self.width, self.height = w, h

        # pre-processing for layout blocks and shapes based on parent page
        self._preprocess_images(raw_layout, **settings)
        self._preprocess_shapes(raw_layout, **settings)
       
        # Element is a base class processing coordinates, so set rotation matrix globally
        Element.set_rotation_matrix(self.fitz_page.rotationMatrix)

        return raw_layout


    def _preprocess_images(self, raw, **settings):
        '''Adjust image blocks. Image block extracted by ``page.get_text('rawdict')`` doesn't 
        contain alpha channel data, so it has to get page images by ``page.get_images()`` and 
        then recover them. Note that ``Page.get_images()`` contains each image only once, i.e., 
        ignore duplicated occurrences.
        '''
        # delete images blocks detected by get_text('rawdict)
        for block in raw['blocks']:
            if block['type'] == 1: block['type'] = -1 # "delete" it
        
        # recover image blocks
        recovered_images = ImagesExtractor(self.fitz_page). \
                                extract_images(settings['clip_image_res_ratio'])
        raw['blocks'].extend(recovered_images)


    @debug_plot('Source Paths')
    def _preprocess_shapes(self, raw, **settings):
        '''Identify iso-oriented paths and convert vector graphic paths to pixmap.'''
        # extract paths by `page.get_drawings()`
        raw_paths = self.fitz_page.get_cdrawings()

        # extract iso-oriented paths, while clip image for curved paths
        paths = Paths(parent=self).restore(raw_paths)
        shapes, images =  paths.to_shapes_and_images(
            settings['min_svg_gap_dx'], 
            settings['min_svg_gap_dy'], 
            settings['min_svg_w'], 
            settings['min_svg_h'], 
            settings['clip_image_res_ratio'])
        raw['shapes'] = shapes
        raw['blocks'].extend(images)

        # Hyperlink is considered as a Shape as well
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
        for link in page.get_links():
            if link['kind']!=2: continue # consider internet address only
            hyperlinks.append({
                'type': RectType.HYPERLINK.value,
                'bbox': tuple(link['from']),
                'uri' : link['uri']
            })

        return hyperlinks


    @staticmethod
    def _create_section(num_col:int, elements:Collection, h_range:tuple, y_ref:float):
        '''Create section based on column count, candidate elements and horizontal boundary.'''
        if not elements: return
        X0, X1 = h_range

        if num_col==1:
            x0, y0, x1, y1 = elements.bbox
            column = Column().update_bbox((X0, y0, X1, y1))
            column.add_elements(elements)
            section = Section(space=0, columns=[column])
            before_space = y0 - y_ref
        else:
            cols = elements.group_by_columns()
            u0, v0, u1, v1 = cols[0].bbox
            m0, n0, m1, n1 = cols[1].bbox
            u = (u1+m0)/2.0

            column_1 = Column().update_bbox((X0, v0, u, v1))
            column_1.add_elements(elements)

            column_2 = Column().update_bbox((u, n0, X1, n1))
            column_2.add_elements(elements)

            section = Section(space=0, columns=[column_1, column_2])
            before_space = v0 - y_ref

        section.before_space = round(before_space, 1)
        return section
                

