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
from ..common.base import PlotControl
from ..common.utils import debug_plot
from ..common.constants import DM, ITP
from ..common.pdf import new_page_with_margin



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
        self._tables_constructor = TablesConstructor(self.blocks, self.shapes)

        # page margin: 
        # - dict from PyMuPDF: to calculate after cleaning blocks
        # - restored from json: get margin directly
        self._margin = raw.get('margin', None)

    @property
    def margin(self): return self._margin

    
    @property
    def bbox(self):
        if self._margin is None:
            return (0,) * 4
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
        self.clean(**kwargs)        
    
        # parse table blocks: 
        #  - table structure/format recognized from rectangles
        self.parse_lattice_tables(**kwargs)
        
        #  - cell contents extracted from text blocks
        self.parse_stream_tables(**kwargs)

        # parse text format, e.g. highlight, underline
        self.parse_text_format(**kwargs)
        
        # paragraph / line spacing        
        self.parse_spacing()

        return self


    def extract_tables(self):
        '''Extract content from lattice tables.'''
        # parsing tables
        self.clean().parse_lattice_tables()

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


    @debug_plot('Cleaned Blocks and Shapes', plot=True, category=PlotControl.LAYOUT)
    def clean(self, **kwargs):
        '''Clean blocks and rectangles, e.g. remove negative blocks, duplicated shapes.'''
        clean_blocks = self.blocks.clean()
        clean_shapes  = self.shapes.clean()
        
        # calculate page margin based on clean layout
        self._margin = self.page_margin()

        return clean_blocks or clean_shapes


    @debug_plot('Lattice Table Structure', plot=True, category=PlotControl.TABLE)
    def parse_lattice_tables(self, **kwargs):
        '''parse table structure from rectangle shapes'''
        tables = self._tables_constructor.lattice_tables()
        return bool(tables)


    @debug_plot('Stream Table Structure', plot=True, category=PlotControl.STREAM_TABLE)
    def parse_stream_tables(self, **kwargs):
        ''' Parse table structure from blocks layout.'''
        tables = self._tables_constructor.stream_tables()
        return bool(tables)


    @debug_plot('Final Layout', plot=True, category=PlotControl.BLOCK)
    def parse_text_format(self, **kwargs):
        '''Parse text format in both page and table context.'''
        return self.blocks.parse_text_format(self.shapes)
 

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
            return (ITP, ) * 4                 # 1 Inch = 72 pt

        # consider both blocks and shapes for page margin
        list_bbox = list(map(lambda x: x.bbox, self.blocks))
        list_bbox.extend(list(map(lambda x: x.bbox, self.shapes))) 

        # left margin 
        left = min(map(lambda x: x.x0, list_bbox))
        left = max(left, 0)

        # right margin
        x_max = max(map(lambda x: x.x1, list_bbox))
        right = self.width - x_max - DM*5.0  # consider tolerance: leave more free space
        right = min(right, left)              # symmetry margin if necessary
        right = max(right, 0.0)               # avoid negative margin

        # top margin
        top = min(map(lambda x: x.y0, list_bbox))
        top = max(top, 0)

        # bottom margin
        bottom = self.height-max(map(lambda x: x.y1, list_bbox))
        bottom = max(bottom, 0.0)

        # reduce calculated top/bottom margin to left some free space
        top *= 0.5
        bottom *= 0.5

        # use normal margin if calculated margin is large enough
        return (
            min(ITP, left), 
            min(ITP, right), 
            min(ITP, top), 
            min(ITP, bottom)
            )
 

    def parse_spacing(self):
        ''' Calculate external and internal vertical space for paragraph blocks under page context 
            or table context. It'll used as paragraph spacing and line spacing when creating paragraph.
        '''
        self.blocks.parse_spacing()
    

    def plot(self, doc, title:str, key:PlotControl=PlotControl.BLOCK):
        '''Plot specified type of blocks layout with PyMuPDF.
            ---
            Args:
              - doc: fitz.Document object
        '''
        # get objects to plot
        #  - blocks + shapes
        if key == PlotControl.LAYOUT: 
            objects = list(self.blocks) + list(self.shapes)
        
        # - all blocks
        elif key == PlotControl.BLOCK: 
            objects = self.blocks
        
        #  - lattice table structure only
        elif key == PlotControl.TABLE: 
            objects = self.blocks.lattice_table_blocks
        
        #  - stream table structure only
        elif key == PlotControl.STREAM_TABLE: 
            objects = self.blocks.stream_table_blocks
        
        #  - rectangle shapes
        elif key == PlotControl.SHAPE: 
            objects = self.shapes

        else:
            objects = []

        # do nothing if no objects
        if not objects: return

        # insert a new page
        page = new_page_with_margin(doc, self.width, self.height, self.margin, title)

        # plot styled table but no text blocks in cell
        if key==PlotControl.TABLE: 
            for item in objects:
                item.plot(page, content=False, style=True)
        
        # plot non-styled table and no text blocks in cell
        elif key==PlotControl.STREAM_TABLE: 
            for item in objects:
                item.plot(page, content=False, style=False)
        
        else:
            for item in objects:
                 item.plot(page) # default args for TableBlock.plot

