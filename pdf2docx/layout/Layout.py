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
    "rects" : [{...}, {...}, ...]
}
'''

import json
from .Blocks import Blocks
from ..common import utils
from ..shape.Rectangles import Rectangles


class Layout:
    ''' Object representing the whole page, e.g. margins, blocks, shapes, spacing.'''

    def __init__(self, raw: dict, rects:Rectangles) -> None:
        self.width = raw.get('width', 0.0)
        self.height = raw.get('height', 0.0)
        self.blocks = Blocks(raw.get('blocks', []))

        # introduced attributes
        self._margin = None
        self.rects = rects

    def store(self) -> dict:
        return {
            'width': self.width,
            'height': self.height,
            'margin': self._margin,
            'blocks': self.blocks.store(),
            'rects': self.rects.store(),
        }

    def serialize(self, filename:str):
        '''Write layout to specified file.'''
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.store(), indent=4))


    def plot(self, doc, title:str, key:str='layout'):
        '''Plot specified type of blocks layout with PyMuPDF.
            ---
            Args:
              - doc: fitz.Document object
        '''
        # get objects to plot
        #  - all blocks
        if key == 'layout': 
            objects = list(self.blocks)
        
        #  - explicit table block only
        elif key == 'table': 
            objects = list(filter(
                lambda block: block.is_explicit_table_block(), self.blocks
            ))
        
        #  - explicit table block only
        elif key == 'implicit_table': 
            objects = list(filter(
                lambda block: block.is_implicit_table_block(), self.blocks
            ))
        
        #  - rectangle shapes
        elif key == 'shape': 
            objects = list(self.rects)

        else:
            objects = []

        # do nothing if no objects
        if not objects: return

        # insert a new page
        page = utils.new_page_with_margin(doc, self.width, self.height, self.margin, title)

        # plot each object
        for item in objects:
            item.plot(page) 

    @property
    def margin(self):
        if self._margin is None:
            self._margin = self.page_margin()

        return self._margin

    
    def parse_vertical_spacing(self):
        ''' Calculate external and internal vertical space for paragraph blocks under page context 
            or table context. It'll used as paragraph spacing and line spacing when creating paragraph.
        '''
        # blocks in page level
        top, bottom = self.margin[-2:]
        self.blocks.parse_vertical_spacing(top, self.height-bottom)

        # blocks in table cell level
        tables = list(filter(lambda block: block.is_table_block(), self.blocks))
        for table in tables:
            for row in table.cells:
                for cell in row:
                    if not cell: continue
                    _, y0, _, y1 = cell.bbox_raw
                    w_top, _, w_bottom, _ = cell.border_width
                    cell.blocks.parse_vertical_spacing(y0+w_top/2.0, y1-w_bottom/2.0)


    def page_margin(self) -> tuple:
        '''Calculate page margin:
            - left: MIN(bbox[0])
            - right: MIN(left, width-max(bbox[2]))
            - top: MIN(bbox[1])
            - bottom: height-MAX(bbox[3])
        '''
        # return normal page margin if no blocks exist
        if not self.blocks:
            return (utils.ITP, ) * 4 # 1 Inch = 72 pt

        # check candidates for left margin:
        list_bbox = list(map(lambda x: x.bbox, self.blocks))

        # left margin 
        left = min(map(lambda x: x.x0, list_bbox))

        # right margin
        x_max = max(map(lambda x: x.x1, list_bbox))
        right = self.width-x_max-utils.DM*2.0 # consider tolerance: leave more free space
        right = min(right, left)     # symmetry margin if necessary
        right = max(right, 0.0)      # avoid negative margin

        # top/bottom margin
        top = min(map(lambda x: x.y0, list_bbox))
        bottom = self.height-max(map(lambda x: x.y1, list_bbox))
        bottom = max(bottom, 0.0)

        # reduce calculated bottom margin -> more free space left,
        # to avoid page content exceeding current page
        bottom *= 0.5

        # use normal margin if calculated margin is large enough
        return (
            min(utils.ITP, left), 
            min(utils.ITP, right), 
            min(utils.ITP, top), 
            min(utils.ITP, bottom)
            )