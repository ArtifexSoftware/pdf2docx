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
from pdf2docx import Converter, parse
from pdf2docx.text.TextSpan import TextSpan


script_path = os.path.abspath(__file__) # current script path

class Utility:
    '''utilities related directly to the test case'''

    @property
    def test_dir(self): return os.path.dirname(script_path)

    @property
    def layout_dir(self): return os.path.join(self.test_dir, 'layouts')

    @property
    def sample_dir(self): return os.path.join(self.test_dir, 'samples')

    @property
    def output_dir(self): return os.path.join(self.test_dir, 'outputs')

    def init_test(self, filename):
        ''' Initialize parsed layout and benchmark layout.'''
        # parsed layout: first page only
        pdf_file = os.path.join(self.sample_dir, f'{filename}.pdf')
        docx_file = os.path.join(self.output_dir, f'{filename}.docx')
        cv = Converter(pdf_file)        
        cv.convert(docx_file, pages=[0])
        self.test = cv[0] # type: Page
        cv.close()

        # restore sample layout
        cv = Converter(pdf_file)
        layout_file = os.path.join(self.layout_dir, f'{filename}.json')
        cv.deserialize(layout_file)
        self.sample = cv[0] # type: Page

        return self


    def verify_layout(self, threshold=0.95):
        ''' Check layout between benchmark and parsed one.'''
        sample_text_image_blocks = self.sample.layout.blocks.text_blocks
        test_text_image_blocks = self.test.layout.blocks.text_blocks
        
        # text blocks
        f = lambda block: block.is_text_block()
        sample_text_blocks = list(filter(f, sample_text_image_blocks))
        test_text_blocks   = list(filter(f, test_text_image_blocks))
        self._check_text_layout(sample_text_blocks, test_text_blocks, threshold)

        # inline images
        sample_inline_images = self.sample.layout.blocks.inline_image_blocks
        test_inline_images = self.test.layout.blocks.inline_image_blocks
        self._check_inline_image_layout(sample_inline_images, test_inline_images, threshold)

        # floating images
        f = lambda block: block.is_float_image_block()
        sample_float_images = list(filter(f, sample_text_image_blocks))
        test_float_images = list(filter(f, test_text_image_blocks))
        self._check_float_image_layout(sample_float_images, test_float_images, threshold)        

        # table blocks
        sample_tables = self.sample.layout.blocks.table_blocks
        test_tables = self.test.layout.blocks.table_blocks        
        self._check_table_layout(sample_tables, test_tables, threshold)


    @staticmethod
    def _check_table_layout(sample_tables, test_tables, threshold):
        '''Check table layout.
             - table contents are covered by text layout checking
             - check table structure
        '''
        # count of tables
        m, n = len(sample_tables), len(test_tables)
        assert m==n, f"\nThe count of parsed tables '{n}' is inconsistent with sample '{m}'"

        # check structures table by table
        for sample_table, test_table in zip(sample_tables, test_tables):
            for sample_row, test_row in zip(sample_table, test_table):
                for sample_cell, test_cell in zip(sample_row, test_row):
                    if not sample_cell: continue
                    matched, msg = test_cell.compare(sample_cell, threshold)
                    assert matched, f'\n{msg}'


    @staticmethod
    def _check_inline_image_layout(sample_inline_images, test_inline_images, threshold):
        '''Check image layout: bbox and vertical spacing.'''
        # count of images
        m, n = len(sample_inline_images), len(test_inline_images)
        assert m==n, f"\nThe count of image blocks {n} is inconsistent with sample {m}"

        # check each image
        for sample, test in zip(sample_inline_images, test_inline_images):
            matched, msg = test.compare(sample, threshold)
            assert matched, f'\n{msg}'
    

    @staticmethod
    def _check_float_image_layout(sample_float_images, test_float_images, threshold):
        '''Check image layout: bbox and vertical spacing.'''
        # count of images
        m, n = len(sample_float_images), len(test_float_images)
        assert m==n, f"\nThe count of image blocks {n} is inconsistent with sample {m}"

        # check each image
        for sample, test in zip(sample_float_images, test_float_images):
            matched, msg = test.compare(sample, threshold)
            assert matched, f'\n{msg}'


    @staticmethod
    def _check_text_layout(sample_text_blocks, test_text_blocks, threshold):
        ''' Compare text layout and format. 
             - text layout is determined by vertical spacing
             - text format is defined in style attribute of TextSpan
        '''
        # count of blocks
        m, n = len(sample_text_blocks), len(test_text_blocks)
        assert m==n, f"\nThe count of text blocks {n} is inconsistent with sample {m}"
        
        # check layout of each block
        for sample, test in zip(sample_text_blocks, test_text_blocks):

            # text bbox and vertical spacing
            matched, msg = test.compare(sample, threshold)
            assert matched, f'\n{msg}'

            # text style
            for sample_line, test_line in zip(sample.lines, test.lines):
                for sample_span, test_span in zip(sample_line.spans, test_line.spans):
                    if not isinstance(sample_span, TextSpan): continue
                    
                    # text
                    a, b = sample_span.text, test_span.text
                    assert a==b, f"\nApplied text '{b}' is inconsistent with sample '{a}'"

                    # style
                    m, n = len(sample_span.style), len(test_span.style)
                    assert m==n, f"\nThe count of applied text style {n} is inconsistent with sample {m}"

                    sample_span.style.sort(key=lambda item: item['type'])
                    test_span.style.sort(key=lambda item: item['type'])
                    for sample_dict, test_dict in zip(sample_span.style, test_span.style):
                        a, b = sample_dict['type'], test_dict['type']
                        assert a==b, f"\nApplied text style '{b}' is inconsistent with sample '{a}'"


class Test_Main(Utility):
    '''Main text class.'''

    def setup(self):
        # create output path if not exist
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)

    # ------------------------------------------
    # text styles
    # ------------------------------------------
    def test_blank_file(self):
        '''test blank file without any texts or images.'''
        self.init_test('demo-blank').verify_layout(threshold=0.95)

    def test_text_format(self):
        '''test text format, e.g. highlight, underline, strike-through.'''
        self.init_test('demo-text').verify_layout(threshold=0.95)

    def test_text_alignment(self):
        '''test text alignment.'''
        self.init_test('demo-text-alignment').verify_layout(threshold=0.95)
    
    def test_unnamed_fonts(self):
        '''test unnamed fonts which destroys span bbox, and accordingly line/block layout.'''
        self.init_test('demo-text-unnamed-fonts').verify_layout(threshold=0.95)

    def test_text_scaling(self):
        '''test font size. In this case, the font size is set precisely with character scaling.'''
        self.init_test('demo-text-scaling').verify_layout(threshold=0.95)

    # ------------------------------------------
    # image styles
    # ------------------------------------------
    def test_image(self):
        '''test inline-image.'''
        self.init_test('demo-image').verify_layout(threshold=0.95)

    def test_vector_graphic(self):
        '''test vector graphic.'''
        self.init_test('demo-image-vector-graphic').verify_layout(threshold=0.95)

    def test_image_cmyk(self):
        '''test image in CMYK color-space.'''
        self.init_test('demo-image-cmyk').verify_layout(threshold=0.95)

    def test_image_transparent(self):
        '''test transparent images.'''
        self.init_test('demo-image-transparent').verify_layout(threshold=0.95)

    # ------------------------------------------
    # table styles
    # ------------------------------------------
    def test_table_bottom(self):
        '''page break due to table at the end of page.'''
        self.init_test('demo-table-bottom').verify_layout(threshold=0.95)

    def test_table_format(self):
        '''test table format, e.g. 
            - border and shading style
            - vertical cell
            - merged cell
            - text format in cell
        '''
        self.init_test('demo-table').verify_layout(threshold=0.95)

    def test_stream_table(self):
        '''test stream structure and shading.'''
        self.init_test('demo-table-stream').verify_layout(threshold=0.95)

    def test_table_shading(self):
        '''test simulating shape with shading cell.'''
        self.init_test('demo-table-shading').verify_layout(threshold=0.95)
    
    def test_table_shading_highlight(self):
        '''test distinguishing table shading and highlight.'''
        self.init_test('demo-table-shading-highlight').verify_layout(threshold=0.95)

    def test_lattice_table(self):
        '''test lattice table with very close text underlines to table borders.'''
        self.init_test('demo-table-close-underline').verify_layout(threshold=0.95)

    def test_lattice_table_invoice(self):
        '''test invoice sample file with lattice table, vector graphic.'''
        self.init_test('demo-table-lattice').verify_layout(threshold=0.95)

    def test_lattice_cell(self):
        '''test generating stream borders for lattice table cell.'''
        self.init_test('demo-table-lattice-one-cell').verify_layout(threshold=0.95)

    def test_table_border_style(self):
        '''test border style, e.g. width, color.'''
        self.init_test('demo-table-border-style').verify_layout(threshold=0.95)

    def test_table_align_borders(self):
        '''aligning stream table borders to simplify table structure.'''
        self.init_test('demo-table-align-borders').verify_layout(threshold=0.95)

    def test_nested_table(self):
        '''test nested tables.'''
        self.init_test('demo-table-nested').verify_layout(threshold=0.95)

    def test_path_transformation(self):
        '''test path transformation. In this case, the (0,0) origin is out of the page.'''
        self.init_test('demo-path-transformation').verify_layout(threshold=0.95)


    # ------------------------------------------
    # table contents
    # ------------------------------------------
    def test_extracting_table(self):
        '''test extracting contents from table.'''
        filename = 'demo-table'
        pdf_file = os.path.join(self.sample_dir, f'{filename}.pdf')
        tables = Converter(pdf_file).extract_tables(end=1)
        print(tables)

        # compare the last table
        sample = [
            ['Input', None, None, None, None, None],
            ['Description A', 'mm', '30.34', '35.30', '19.30', '80.21'],
            ['Description B', '1.00', '5.95', '6.16', '16.48', '48.81'],
            ['Description C', '1.00', '0.98', '0.94', '1.03', '0.32'],
            ['Description D', 'kg', '0.84', '0.53', '0.52', '0.33'],
            ['Description E', '1.00', '0.15', None, None, None],
            ['Description F', '1.00', '0.86', '0.37', '0.78', '0.01']
        ]
        assert tables[-1]==sample

    
    # ------------------------------------------
    # command line arguments
    # ------------------------------------------
    def test_multi_pages(self):
        '''test converting pdf with multi-pages.'''
        filename = 'demo'
        pdf_file = os.path.join(self.sample_dir, f'{filename}.pdf')
        docx_file = os.path.join(self.output_dir, f'{filename}.docx')    
        parse(pdf_file, docx_file, start=1, end=5)

        # check file        
        assert os.path.isfile(docx_file)