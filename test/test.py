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

from pdf2docx import Converter, Layout
from pdf2docx.text.TextSpan import TextSpan


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

    @property
    def output_dir(self):
        return os.path.join(self.test_dir, 'outputs')

    def init_test(self, filename):
        ''' Initialize parsed layout and benchmark layout.'''
        # restore sample layout
        layout_file = os.path.join(self.layout_dir, f'{filename}.json')
        with open(layout_file, 'r') as f:
            raw_dict = json.load(f)
        self.sample = Layout(raw_dict)

        # parsed layout: first page only
        pdf_file = os.path.join(self.sample_dir, f'{filename}.pdf')
        docx_file = os.path.join(self.output_dir, f'{filename}.docx')
        cv = Converter(pdf_file, docx_file)        
        cv.make_page(cv[0], debug=False)
        self.test = cv.layout # type: Layout
        cv.close()

        return self


    def verify_layout(self, threshold=0.95):
        ''' Check layout between benchmark and parsed one.'''
        self._check_text_layout(threshold)
        self._check_image_layout(threshold)
        self._check_table_layout(threshold)


    def _check_table_layout(self, threshold):
        '''Check table layout.
             - table contents are covered by text layout checking
             - check table structure
        '''
        sample_tables = self.sample.blocks.table_blocks
        test_tables = self.test.blocks.table_blocks

        # count of tables
        m, n = len(sample_tables), len(test_tables)
        self.assertEqual(m, n, msg=f"\nThe count of parsed tables '{n}' is inconsistent with sample '{m}'")

        # check structures table by table
        for sample_table, test_table in zip(sample_tables, test_tables):
            for sample_row, test_row in zip(sample_table, test_table):
                for sample_cell, test_cell in zip(sample_row, test_row):
                    if not sample_cell: continue
                    matched, msg = sample_cell.compare(test_cell, threshold)
                    self.assertTrue(matched, msg=f'\n{msg}')


    def _check_image_layout(self, threshold):
        '''Check image layout: bbox and vertical spacing.'''
        sample_image_spans = self.sample.blocks.image_spans(level=1)
        test_image_spans = self.test.blocks.image_spans(level=1)

        # count of images
        m, n = len(sample_image_spans), len(test_image_spans)
        self.assertEqual(m, n, msg=f"\nThe count of image blocks {n} is inconsistent with sample {m}")

        # check each image
        for sample, test in zip(sample_image_spans, test_image_spans):
            matched, msg = sample.compare(test, threshold)
            self.assertTrue(matched, msg=f'\n{msg}')


    def _check_text_layout(self, threshold):
        ''' Compare text layout and format. 
             - text layout is determined by vertical spacing
             - text format is defined in style attribute of TextSpan
        '''
        sample_text_blocks = self.sample.blocks.text_blocks(level=1)
        test_text_blocks = self.test.blocks.text_blocks(level=1)

        # count of blocks
        m, n = len(sample_text_blocks), len(test_text_blocks)
        self.assertEqual(m, n, msg=f"\nThe count of text blocks {n} is inconsistent with sample {m}")
        
        # check layout of each block
        for sample, test in zip(sample_text_blocks, test_text_blocks):

            # text bbox and vertical spacing
            matched, msg = sample.compare(test, threshold)
            self.assertTrue(matched, msg=f'\n{msg}')

            # text style
            for sample_line, test_line in zip(sample.lines, test.lines):
                for sample_span, test_span in zip(sample_line.spans, test_line.spans):
                    if not isinstance(sample_span, TextSpan): continue
                    
                    # text
                    a, b = sample_span.text, test_span.text
                    self.assertEqual(a, b, msg=f"\nApplied text '{b}' is inconsistent with sample '{a}'")

                    # style
                    m, n = len(sample_span.style), len(test_span.style)
                    self.assertEqual(m, n, msg=f"\nThe count of applied text style {n} is inconsistent with sample {m}")

                    for sample_dict, test_dict in zip(sample_span.style, test_span.style):
                        a, b = sample_dict['type'], test_dict['type']
                        self.assertEqual(a, b, msg=f"\nApplied text style '{b}' is inconsistent with sample '{a}'")


class MainTest(TestUtility):
    '''Main text class.'''

    def setUp(self):
        # create output path if not exist
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)

    def test_text_format(self):
        '''sample file focusing on text format, e.g. highlight, underline, strike-through.'''
        self.init_test('demo-text').verify_layout(threshold=0.95)

    def test_image(self):
        '''sample file focusing on inline-image.'''
        self.init_test('demo-image').verify_layout(threshold=0.95)

    def test_table_bottom(self):
        '''sample file focusing on page break due to table at the end of page.'''
        self.init_test('demo-table-bottom').verify_layout(threshold=0.95)

    def test_table_format(self):
        '''sample file focusing on table format, e.g. 
            - border and shading style
            - vertical cell
            - merged cell
            - text format in cell
        '''
        self.init_test('demo-table').verify_layout(threshold=0.95)

    def test_table_shading(self):
        '''sample file focusing on simulating shape with shading cell.'''
        self.init_test('demo-table-shading').verify_layout(threshold=0.95)

    def test_table_border_style(self):
        '''sample file focusing on border style, e.g. width, color.'''
        self.init_test('demo-table-border-style').verify_layout(threshold=0.95)

    def test_table_align_borders(self):
        '''sample file focusing on aligning stream table borders to simplify table structure.'''
        self.init_test('demo-table-align-borders').verify_layout(threshold=0.95)

    def test_nested_table(self):
        '''sample file focusing on nested tables.'''
        self.init_test('demo-table-nested').verify_layout(threshold=0.95)

    def test_text_scaling(self):
        '''sample file focusing on font size.
            In this case, the font size is set precisely with character scaling.
        '''
        self.init_test('demo-text-scaling').verify_layout(threshold=0.95)

    def test_path_transformation(self):
        '''sample file focusing on path transformation.
            In this case, the (0,0) origin is out of the page.
        '''
        self.init_test('demo-path-transformation').verify_layout(threshold=0.95)

    
    def test_unnamed_fonts(self):
        '''Unnamed fonts destroy span bbox, and accordingly line/block layout.
        '''
        self.init_test('demo-unnamed-fonts').verify_layout(threshold=0.95)