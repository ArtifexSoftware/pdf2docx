# -*- coding: utf-8 -*-

'''
Text block objects based on PDF raw dict extracted with PyMuPDF.

@created: 2020-07-22
@author: train8808@gmail.com
---
https://pymupdf.readthedocs.io/en/latest/textpage.html

    {
        # raw dict
        # --------------------------------
        'type': 0,
        'bbox': (x0,y0,x1,y1),
        'lines': [ lines ]

        # introduced dict
        # --------------------------------
        'before_space': bs,
        'after_space': as,
        'line_space': ls
    }
'''

from .Line import Line
from .Lines import Lines
from .ImageSpan import ImageSpan
from .ImageBlock import ImageBlock
from ..common.base import Spacing
from ..common.Block import Block
from ..common import utils


class TextBlock(Block, Spacing):
    '''Text block.'''
    def __init__(self, raw:dict={}) -> None:
        super(TextBlock, self).__init__(raw)
        self.lines = Lines(raw.get('lines', []), self)

        # set type
        self.set_text_block()

    @property
    def text(self) -> str:
        '''Get text content in block, joning each line with `\n`.'''
        lines = [line.spans.text for line in self.lines]
        return '\n'.join(lines)


    @property
    def sub_bboxes(self) -> list:
        '''bbox of sub-region, i.e. Line.'''
        return [line.bbox for line in self.lines]


    def store(self) -> dict:
        res = super().store()
        res.update({
            'lines': self.lines.store()
        })
        return res


    def add(self, line:Line):
        '''Add line to TextBlock.'''
        if isinstance(line, Line):
            self.lines.append(line)


    def plot(self, page):
        '''Plot block/line/span area, in PDF page.
           ---
            Args: 
              - page: fitz.Page object
        '''
        # block border in blue
        blue = utils.RGB_component_from_name('blue')   
        page.drawRect(self.bbox, color=blue, fill=None, overlay=False)

        # lines and spans
        for line in self.lines:
            # line border in red
            red = utils.RGB_component_from_name('red')
            line.plot(page, red)

            # span regions in random color
            for span in line.spans:
                c = utils.RGB_component_from_name('')                
                span.plot(page, c)


    def contains_discrete_lines(self, distance:float=25, threshold:int=3) -> bool:
        ''' Check whether lines in block are discrete: 
            the count of lines with a distance larger than `distance` is greater then `threshold`.
        '''
        num = len(self.lines)
        if num==1: return False

        # check the count of discrete lines
        cnt = 1
        for i in range(num-1):
            bbox = self.lines[i].bbox
            next_bbox = self.lines[i+1].bbox

            if utils.is_horizontal_aligned(bbox, next_bbox):
                # horizontally aligned but not in a same row -> discrete block
                if not utils.in_same_row(bbox, next_bbox):
                    return True
                
                # otherwise, check the distance only
                else:
                    if abs(bbox.x1-next_bbox.x0) > distance:
                        cnt += 1

        return cnt >= threshold

    
    def merge_image(self, image:ImageBlock):
        '''Insert inline image to associated text block as a span'''
        # get the inserting position
        for i,line in enumerate(self.lines):
            if image.bbox.x0 < line.bbox.x0:
                break
        else:
            i = 0

        # Step 1: insert image as a line in block
        # image span
        span = ImageSpan()
        span.from_image_block(image)

        # add span to line
        line = Line()
        line.add(span)
        self.lines.insert(i, line)

        # Step 2: merge image into span in line, especially overlap exists
        self.lines.merge()