# -*- coding: utf-8 -*-

'''
Layout objects based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---

The raw page content extracted with PyMuPDF, `page.getText('rawdict')` is described per link:
https://pymupdf.readthedocs.io/en/latest/textpage.html

In addition to the raw layout dict, some new features are also included, e.g.
    - page margin
    - rectangle shapes, for text format, annotations and table border/shading
    - new block in table type

{
    # raw dict
    ----------------------------
    "width" : w,
    "height": h,    
    "blocks": [{...}, {...}, ...],

    # introduced dict
    ----------------------------
    "margin": [left, right, top, bottom],
    "shapes" : [{...}, {...}, ...]
}
'''



import json
from docx.shared import Pt
from docx.enum.section import WD_SECTION
from .Blocks import Blocks
from ..shape.Shapes import Shapes
from ..table.TablesConstructor import TablesConstructor
from ..common.BBox import BBox
from ..common.utils import debug_plot
from ..common import constants


class Layout:
    ''' Object representing the whole page, e.g. margins, blocks, shapes, spacing.'''

    def __init__(self, raw:dict, rotation_matrix=None):
        ''' Initialize page layout.
            ---
            Args:
            - raw: raw dict representing page blocks, shape
            - rotation_matrix: fitz.Matrix representing page rotation
        '''
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)

        # BBox is a base class processing coordinates, so set rotation matrix globally
        BBox.set_rotation_matrix(rotation_matrix)

        # initialize blocks
        self.blocks = Blocks(parent=self).from_dicts(raw.get('blocks', []))

        # initialize shapes: to add rectangles later
        self.shapes = Shapes(parent=self).from_dicts(raw.get('paths', []))

        # table parser
        self._tables_constructor = TablesConstructor(parent=self)

        # page margin: 
        # - dict from PyMuPDF: to calculate after cleaning blocks
        # - restored from json: get margin directly
        self._margin = raw.get('margin', None)


    @property
    def margin(self): return self._margin

    
    @property
    def bbox(self):
        if self._margin is None:
            return (0, 0, self.width, self.height)
        else:
            left, right, top, bottom = self.margin
            return (left, top, self.width-right, self.height-bottom)


    def store(self):
        return {
            'width': self.width,
            'height': self.height,
            'margin': self._margin,
            'blocks': self.blocks.store(),
            'paths': self.shapes.store(),
        }


    def serialize(self, filename:str):
        '''Write layout to specified file.'''
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.store(), indent=4))

    
    def parse(self, **kwargs):
        ''' Parse page layout.
            ---
            Args:
              - kwargs: dict for layout plotting
                    kwargs = {
                        'debug': bool,
                        'doc': fitz.Document object or None,
                        'filename': str
                    }
        '''

        # preprocessing, e.g. change block order, clean negative block
        self.clean_up_shapes(**kwargs)
        self.clean_up_blocks(**kwargs)
    
        # parse table blocks: 
        #  - table structure/format recognized from rectangles
        self.parse_lattice_tables(**kwargs)
        
        #  - cell contents extracted from text blocks
        self.parse_stream_tables(**kwargs)

        # parse text format, e.g. highlight, underline
        self.parse_text_format(**kwargs)
        
        # paragraph / line spacing        
        self.parse_spacing()

        # combine inline and floating objects
        self.blocks.combine_floating_objects()

        return self


    def extract_tables(self):
        '''Extract content from lattice tables.'''
        # preprocessing, e.g. change block order, clean negative block
        self.clean_up_shapes()
        self.clean_up_blocks()

        # parsing lattice tables only
        self.parse_lattice_tables()

        # check table
        tables = [] # type: list[ list[list[str]] ]
        for table_block in self.blocks.table_blocks:
            tables.append(table_block.text)

        return tables


    def make_page(self, doc):
        ''' Create page based on layout data. 
            ---
            Args:
            - doc: python-docx.Document object

            To avoid incorrect page break from original document, a new page section
            is created for each page.

            The vertical postion of paragraph/table is defined by space_before or 
            space_after property of a paragraph.
        '''
        # new page section
        # a default section is created when initialize the document,
        # so we do not have to add section for the first time.
        if not doc.paragraphs:
            section = doc.sections[0]
        else:
            section = doc.add_section(WD_SECTION.NEW_PAGE)

        section.page_width  = Pt(self.width)
        section.page_height = Pt(self.height)

        # set page margin
        left,right,top,bottom = self.margin
        section.left_margin = Pt(left)
        section.right_margin = Pt(right)
        section.top_margin = Pt(top)
        section.bottom_margin = Pt(bottom)

        # add paragraph or table according to parsed block
        self.blocks.make_page(doc)


    @debug_plot('Source Text Blocks')
    def plot(self, **kwargs):
        '''Plot initial blocks. It's generally called once Layout is initialized.'''
        return self.blocks


    @debug_plot('Cleaned Shapes')
    def clean_up_shapes(self, **kwargs):
        '''Clean up shapes and detect semantic types.'''
        # clean up shapes, e.g. remove negative or duplicated instances
        self.shapes.clean_up()

        # detect semantic type based on the positions to text blocks, 
        # e.g. table border v.s. text underline, table shading v.s. text highlight.
        # NOTE:
        # stroke shapes are grouped on connectivity to each other, but in some cases, 
        # the gap between borders and underlines/strikes are very close, which leads
        # to an incorrect table structure. So, it's required to distinguish them in
        # advance, though we needn't to ensure 100% accuracy.
        self.shapes.detect_initial_categories()

        return self.shapes


    @debug_plot('Cleaned Blocks')
    def clean_up_blocks(self, **kwargs):
        '''Clean up blocks and calculate page margin accordingly.'''
        # clean up bad blocks, e.g. overlapping, out of page
        # NOTE: this step should come after clean up shapes since the initial layout of blocks are used
        self.blocks.clean_up()
        
        # calculate page margin based on cleaned layout
        self._margin = self.page_margin()

        return self.blocks


    @debug_plot('Lattice Table Structure')
    def parse_lattice_tables(self, **kwargs):
        '''Parse table structure based on explicit stroke shapes.'''
        return self._tables_constructor.lattice_tables()


    @debug_plot('Stream Table Structure')
    def parse_stream_tables(self, **kwargs):
        '''Parse table structure based on layout of blocks.'''
        return self._tables_constructor.stream_tables()


    @debug_plot('Final Layout')
    def parse_text_format(self, **kwargs):
        '''Parse text format in both page and table context.'''
        text_shapes = list(self.shapes.text_underlines_strikes) + list(self.shapes.text_highlights)
        self.blocks.parse_text_format(text_shapes)
        return self.blocks
 

    def page_margin(self):
        '''Calculate page margin.            
            ---
            Args:
            - width: page width
            - height: page height

            Calculation method:
            - left: MIN(bbox[0])
            - right: MIN(left, width-max(bbox[2]))
            - top: MIN(bbox[1])
            - bottom: height-MAX(bbox[3])
        '''
        # return normal page margin if no blocks exist
        if not self.blocks and not self.shapes:
            return (constants.ITP, ) * 4                 # 1 Inch = 72 pt

        # consider both blocks and shapes for page margin
        list_bbox = list(map(lambda x: x.bbox, self.blocks))
        list_bbox.extend(list(map(lambda x: x.bbox, self.shapes))) 

        # left margin 
        left = min(map(lambda x: x.x0, list_bbox))
        left = max(left, 0)

        # right margin
        x_max = max(map(lambda x: x.x1, list_bbox))
        right = self.width - x_max - constants.DM_PAGE  # consider tolerance: leave more free space
        right = min(right, left)                        # symmetry margin if necessary
        right = max(right, 0.0)                         # avoid negative margin

        # top margin
        top = min(map(lambda x: x.y0, list_bbox))
        top = max(top, 0)

        # bottom margin
        bottom = self.height-max(map(lambda x: x.y1, list_bbox))
        bottom = max(bottom, 0.0)

        # reduce calculated top/bottom margin to left some free space
        top *= constants.FACTOR_PAGE_MARGIN
        bottom *= constants.FACTOR_PAGE_MARGIN

        # use normal margin if calculated margin is large enough
        return (
            min(constants.ITP, left), 
            min(constants.ITP, right), 
            min(constants.ITP, top), 
            min(constants.ITP, bottom)
            )
 

    def parse_spacing(self):
        ''' Calculate external and internal vertical space for paragraph blocks under page context 
            or table context. It'll used as paragraph spacing and line spacing when creating paragraph.
        '''
        self.blocks.parse_spacing()
