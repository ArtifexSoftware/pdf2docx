# -*- coding: utf-8 -*-

'''Page object parsed with PDF raw dict.

In addition to base structure described in :py:class:`~pdf2docx.page.RawPage`, 
some new features are also included, e.g.

* page margin
* parsed table block and nested layout

::

    {
        # raw dict
        ----------------------------
        "width" : w,
        "height": h,    
        "blocks": [{...}, {...}, ...],

        # introduced dict
        ----------------------------
        "id": 0, # page index
        "margin": [left, right, top, bottom],
        "shapes" : [{...}, {...}, ...]
    }

'''

from docx.shared import Pt
from docx.enum.section import WD_SECTION
from ..common.share import debug_plot
from ..common import constants
from .RawPage import RawPage
from .Layout import Layout


class Page(RawPage):
    '''Object representing the whole page, e.g. margins, blocks, shapes, spacing.'''

    def __init__(self, fitz_page=None):
        ''' Initialize page layout.
        
        Args:
            fitz_page (fitz.Page): Source pdf page.
        '''
        super().__init__(fitz_page)
        self.id = -1
        self._margin = (0,) * 4
        self.settings = self.init_settings()        
        self.layout = Layout(parent=self)
        self._finalized = False


    @property
    def finalized(self): return self._finalized


    @staticmethod
    def init_settings(settings:dict=None):
        '''Initialize and update parameters.'''
        default = {
            'debug': False, # plot layout if True
            'connected_border_tolerance'     : 0.5, # two borders are intersected if the gap lower than this value
            'max_border_width'               : 6.0, # max border width
            'min_border_clearance'           : 2.0, # the minimum allowable clearance of two borders
            'float_image_ignorable_gap'      : 5.0, # float image if the intersection exceeds this value
            'float_layout_tolerance'         : 0.1, # [0,1] the larger of this value, the more tolerable of float layout
            'page_margin_factor_top'         : 0.5, # [0,1] reduce top margin by factor
            'page_margin_factor_bottom'      : 0.5, # [0,1] reduce bottom margin by factor
            'shape_merging_threshold'        : 0.5, # [0,1] merge shape if the intersection exceeds this value
            'shape_min_dimension'            : 2.0, # ignore shape if both width and height is lower than this value
            'line_overlap_threshold'         : 0.9, # [0,1] delete line if the intersection to other lines exceeds this value
            'line_free_space_ratio_threshold': 0.1, # break line if the ratio of free space to entire line exceeds this value
            'line_merging_threshold'         : 2.0, # combine two lines if the x-distance is lower than this value
            'line_separate_threshold'        : 5.0, # two separate lines if the x-distance exceeds this value
            'lines_left_aligned_threshold'   : 1.0, # left aligned if delta left edge of two lines is lower than this value
            'lines_right_aligned_threshold'  : 1.0, # right aligned if delta right edge of two lines is lower than this value
            'lines_center_aligned_threshold' : 2.0, # center aligned if delta center of two lines is lower than this value
            'clip_image_res_ratio'           : 3.0, # resolution ratio (to 72dpi) when cliping page image
            'curve_path_ratio'               : 0.2, # clip page bitmap if the component of curve paths exceeds this ratio
            'extract_stream_table'           : False, # don't consider stream table when extracting tables
        }

        # update user defined parameters
        if settings: default.update(settings)
        return default


    @property
    def bbox(self): return (0.0, 0.0, self.width, self.height)


    @property
    def margin(self):
        """Get page margin.

        Returns:
            tuple: ``(left, right, top, bottom)``.
        """        
        return self._margin


    @property
    def working_bbox(self):
        '''bbox with margin considered.'''
        x0, y0, x1, y1 = self.bbox
        L, R, T, B = self.margin
        return (x0+L, y0+T, x1-R, y1-B)
    

    def store(self):
        '''Store parsed layout in dict format.'''
        res = {
            'id'    : self.id,
            'width' : self.width,
            'height': self.height,
            'margin': self.margin
        }
        res.update(self.layout.store())
        return res


    def restore(self, data:dict):
        '''Restore Layout from parsed results.'''
        # page id
        self.id = data.get('id', -1)

        # page width/height
        self.width = data.get('width', 0.0)
        self.height = data.get('height', 0.0)
        self._margin = data.get('margin', (0,) * 4)
        
        # initialize layout  blocks and shapes
        self.layout.restore(data)

        # Suppose layout is finalized when restored; otherwise, set False explicitly
        # out of this method.
        self._finalized = True

        return self


    def parse(self, settings:dict=None):
        '''Parse page layout.'''
        # update parameters
        self.settings = self.init_settings(settings)

        # initialize layout based on source pdf page
        self._load_source()

        # parse layout
        self._parse_layout()

        self._finalized = True

        return self


    def extract_tables(self):
        '''Extract content from tables (top layout only).
        
        .. note::
            Before running this method, the page layout must be either parsed from source 
            page or restored from parsed data.
        '''
        # check table
        tables = [] # type: list[ list[list[str]] ]
        if self.settings['extract_stream_table']:
            collections = self.layout.blocks.table_blocks
        else:
            collections = self.layout.blocks.lattice_table_blocks
        
        for table_block in collections:
            tables.append(table_block.text)

        return tables


    def make_docx(self, doc):
        '''Create page based on layout data. 

        .. note::
            Before running this method, the page layout must be either parsed from source 
            page or restored from parsed data.
        
        Args:
            doc (Document): ``python-docx`` document object
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
        self.layout.blocks.make_docx(doc)

    
    @debug_plot('Source Text Blocks')
    def _load_source(self):
        '''Initialize layout extracted with ``PyMuPDF``.'''
        self.restore(self.raw_dict)
        self._finalized = False  # just restored from raw dict, not parsed yet
        return self.layout.blocks
    

    @debug_plot('Cleaned Shapes')
    def _clean_up_layout(self):
        '''Clean shapes and blocks, e.g. change block order, clean negative block, 
        and set page margin accordingly. 
        '''
        self.layout.clean_up(self.settings)

        # set page margin based on cleaned layout
        self._margin = self._cal_margin()
        
        return self.layout.shapes


    @debug_plot('Final Layout')
    def _parse_layout(self):
        '''A wrapper of parsing layout for debug plot purpose.'''
        # clean up
        self._clean_up_layout()

        # parse layout
        self.layout.parse(self.settings)

        return self.layout.blocks


    def _cal_margin(self):
        """Calculate and set page margin.

        .. note::
            Ensure this method is run right after cleaning up the layout, so the page margin is 
            calculated based on valid layout, and stay constant.
        """
        # return default margin if no blocks exist
        if not self.layout.blocks and not self.layout.shapes: return (constants.ITP, ) * 4

        x0, y0, x1, y1 = self.bbox
        u0, v0, u1, v1 = self.layout.blocks.bbox | self.layout.shapes.bbox

        # margin
        left = max(u0-x0, 0.0)
        right = max(x1-u1-constants.MINOR_DIST, 0.0)
        top = max(v0-y0, 0.0)
        bottom = max(y1-v1, 0.0)

        # reduce calculated top/bottom margin to leave some free space
        top *= self.settings['page_margin_factor_top']
        bottom *= self.settings['page_margin_factor_bottom']

        # use normal margin if calculated margin is large enough
        return (
            min(constants.ITP, round(left, 1)), 
            min(constants.ITP, round(right, 1)), 
            min(constants.ITP, round(top, 1)), 
            min(constants.ITP, round(bottom, 1)))
