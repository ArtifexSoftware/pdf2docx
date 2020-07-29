# -*- coding: utf-8 -*-

'''
Testing the layouts between sample pdf and the converted docx.

NOTE: pdf2docx should be installed in advance.

The docx is created from parsed layout, so an equivalent but efficient way is to 
compare parsed layout with banchmark one.

The benchmark layout is also created from parsed layout, but proved to be able to
create docx with good enough quality.

Obsoleted method (real-time testing method):
  - convert sample pdf to docx with this module
  - convert docx back to pdf (`OfficeToPDF` or online `pylovepdf`, see more link)
  - compare layouts between sample pdf and comparing pdf

more link:
  - https://github.com/cognidox/OfficeToPDF/releases
  - https://github.com/AndyCyberSec/pylovepdf
'''

import os
import unittest
import json

from pdf2docx.converter import Converter
from pdf2docx.layout.Layout import Layout
from pdf2docx.text.ImageSpan import ImageSpan


script_path = os.path.abspath(__file__) # current script path

class TestUtility(unittest.TestCase):
    '''utilities related directly to the test case'''

    @property
    def test_dir(self):
        return os.path.dirname(script_path)

    @property
    def layout_dir(self):
        return os.path.join(self.test_dir, 'layouts')

    @property
    def sample_dir(self):
        return os.path.join(self.test_dir, 'samples')

    def init_test(self, filename):
        ''' Initialize parsed layout and benchmark layout.'''
        # restore sample layout
        layout_file = os.path.join(self.layout_dir, f'{filename}.json')
        with open(layout_file, 'r') as f:
            raw_dict = json.load(f)
        self.sample = Layout(raw_dict)

        # parsed layout: first page only
        pdf_file = os.path.join(self.sample_dir, f'{filename}.pdf')
        cv = Converter(pdf_file)        
        self.test = cv.parse(cv[0]).layout # type: Layout
        cv.close()

    @staticmethod
    def get_text_image_blocks(layout:Layout):
        ''' get text blocks from both page and table level'''
        # text block in page level
        blocks = list(filter(
            lambda block: block.is_text_block() or block.is_image_block(), 
            layout.blocks))

        # blocks in table cell level
        tables = list(filter(
            lambda block: block.is_table_block(), 
            layout.blocks))
        for table in tables:
            for row in table.cells:
                for cell in row:
                    if not cell: continue
                    blocks.extend(list(cell.blocks))

        return blocks

    def extract_text_style(self, layout:Layout):
        '''Extract span text and style from layout.'''
        # text or image blocks
        blocks = self.get_text_image_blocks(layout)

        # check text format from text blocks
        res = []
        for block in blocks:
            if block.is_image_block(): continue
            for line in block.lines:
                for span in line.spans:
                    if not span.style: continue
                    res.append({
                        'text': span.text,
                        'style': [ t['type'] for t in span.style]
                    })
        return res

    def extract_image(self, layout):
        ''' extract image bbox from layout'''
        # text or image blocks
        blocks = self.get_text_image_blocks(layout)

        # extract images
        res = []
        for block in blocks:
            if block.is_image_block():
                res.append(block.bbox_raw)
            elif block.is_text_block():
                for line in block.lines:
                    for span in line.spans:
                        if isinstance(span, ImageSpan):
                            res.append(span.bbox_raw)
        return res

    def verify_layout(self, threshold=0.9):
        ''' Compare layouts. 
            The most important attributes affecting layout of generated docx is vertical spacing.
        '''
        for sample, test in zip(self.sample.blocks, self.test.blocks):
            matched, msg = sample.compare(test, threshold)
            self.assertTrue(matched, msg=msg)


class MainTest(TestUtility):
    ''' convert sample pdf files to docx, then verify the layout between 
        sample pdf and docx (saved as pdf file).
    '''

    def test_text_format(self):
        '''sample file focusing on text format'''
        # init pdf
        self.init_test('demo-text')

        # check text layout
        self.verify_layout()

        # check text style page by page
        pass

    def test_image(self):
        '''sample file focusing on image, inline-image considered'''
        # init pdf
        self.init_test('demo-image')

        # check text layout
        self.verify_layout()

        # check images page by page
        pass

    def test_table_format(self):
        '''sample file focusing on table format'''
        # init pdf
        self.init_test('demo-table')

        # check text layout
        # if table is parsed successfully, all re-created text blocks should be same with sample file.
        self.verify_layout()
