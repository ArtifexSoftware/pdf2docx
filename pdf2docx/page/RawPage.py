# -*- coding: utf-8 -*-

'''A wrapper of pdf page engine (e.g. PyMuPDF, pdfminer) to do the following work:

* extract source contents
* clean up blocks/shapes, e.g. elements out of page
* calculate page margin
* parse page structure roughly, i.e. section and column
'''

from .BasePage import BasePage
from ..layout.Layout import Layout
from ..layout.Section import Section
from ..layout.Column import Column
from ..shape.Shape import Hyperlink
from ..shape.Shapes import Shapes
from ..font.Fonts import Fonts
from ..text.TextSpan import TextSpan
from ..common.share import debug_plot
from ..common import constants
from ..common.Collection import Collection


class RawPage(BasePage, Layout):
    '''A wrapper of page engine.'''

    def __init__(self, page_engine=None):
        ''' Initialize page layout.
        
        Args:
            page_engine (Object): Source pdf page.
        '''
        BasePage.__init__(self)
        Layout.__init__(self)
        self.page_engine = page_engine
    

    def extract_raw_dict(self, **settings):
        '''Extract source data with page engine. Return a dict with the following structure:
        ```
            {
                "width" : w,
                "height": h,    
                "blocks": [{...}, {...}, ...],
                "shapes" : [{...}, {...}, ...]
            }
        ```
        '''
        raise NotImplementedError
    
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