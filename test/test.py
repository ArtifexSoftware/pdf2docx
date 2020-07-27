# -*- coding: utf-8 -*-

'''
Testing the layouts between sample pdf and the converted docx:
  - convert sample pdf to docx
  - convert docx to pdf for comparison
  - compare layouts between sample pdf and comparing pdf

NOTE: pdf2docx should be installed in advance.
'''

import os
import shutil
import unittest
import fitz

from utils import Utility
from pdf2docx.converter import Converter
from pdf2docx.layout.Layout import Layout
from pdf2docx.text.ImageSpan import ImageSpan


class TestUtility(Utility, unittest.TestCase):
    '''utilities related directly to the test case'''

    PREFIX_SAMPLE = 'sample'
    PREFIX_COMPARING = 'comparing'

    TEST_FILE = ''
    SAMPLE_PDF = None
    TEST_PDF = None

    STATUS = False

    def init_test(self, filename):
        ''' Create pdf objects and set default class properties
            - create sample pdf Reader object
            - convert sample pdf to docx
            - create comparing pdf from docx
        '''
        # sample pdf
        sample_pdf_file = os.path.join(self.output_dir, f'{self.PREFIX_SAMPLE}-{filename}')
        docx_file = os.path.join(self.output_dir, f'{filename[0:-3]}docx')
        sample_pdf = Converter(sample_pdf_file, docx_file)

        # convert pdf to docx, besides, 
        # convert docx back to pdf for comparison next
        comparing_pdf_file = os.path.join(self.output_dir, f'{self.PREFIX_COMPARING}-{filename}')
        layouts = self.pdf2docx(sample_pdf, comparing_pdf_file)
        self.assertIsNotNone(layouts, msg='Converting PDF to Docx failed.')

        # testing pdf
        test_pdf_file = os.path.join(self.output_dir, comparing_pdf_file)
        test_pdf = Converter(test_pdf_file)

        # set default properties
        self.TEST_FILE = filename
        self.SAMPLE_PDF = sample_pdf
        self.TEST_PDF = test_pdf

        return layouts

    def pdf2docx(self, pdf:Converter, comparing_pdf_file:str):
        ''' test target: converting pdf to docx'''        
        layouts = [] # type: list[Layout]
        for page in pdf:
            # parse layout
            pdf.parse(page).make_page()
            layouts.append(pdf.layout)
        
        # convert to pdf for comparison
        if self.docx2pdf(pdf.filename_docx, comparing_pdf_file):
            return layouts
        else:
            return None   

    def check_bbox(self, sample_bbox, test_bbox, page, threshold):
        ''' If the intersection of two bbox-es exceeds a threshold, they're considered same,
            otherwise, mark both box-es in the associated page.

            page: pdf page where these box-es come from, used for illustration if check failed
        '''
        b1, b2 = fitz.Rect(sample_bbox), fitz.Rect(test_bbox)

        # ignore small bbox, e.g. single letter bbox
        if b1.width < 20:
            return True
            
        b = b1 & b2
        area = b.getArea()
        matched = area/b1.getArea()>=threshold and area/b2.getArea()>=threshold

        if not matched:
            # right position in sample file
            page.drawRect(sample_bbox, color=(1,1,0), overlay=False)
            # mismatched postion in red box
            page.drawRect(test_bbox, color=(1,0,0), overlay=False)
            # save file
            result_file = self.SAMPLE_PDF.filename.replace(f'{self.PREFIX_SAMPLE}-', '')
            self.SAMPLE_PDF.core.save(result_file)

        return matched

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

    def verify_layout(self, threshold=0.7):
        ''' compare layout of two pdf files:
            It's difficult to have an exactly same layout of blocks, but ensure they
            look like each other. So, with `extractWORDS()`, all words with bbox 
            information are compared.
            (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        '''
        # check count of pages
        self.assertEqual(len(self.SAMPLE_PDF), len(self.TEST_PDF), 
            msg='Page count is inconsistent with sample file.')

        # check position of each word
        for sample_page, test_page in zip(self.SAMPLE_PDF, self.TEST_PDF):
            sample_words = sample_page.getText('words')
            test_words = test_page.getText('words')

            # sort by word
            sample_words.sort(key=lambda item: (item[4], item[-3], item[-2], item[-1]))
            test_words.sort(key=lambda item: (item[4], item[-3], item[-2], item[-1]))

            # check each word and bbox
            for sample, test in zip(sample_words, test_words):
                sample_bbox, test_bbox = sample[0:4], test[0:4]

                # check bbox word by word
                matched = self.check_bbox(sample_bbox, test_bbox, sample_page, threshold)
                self.assertTrue(matched,
                    msg=f'bbox for word "{sample[4]}": {test_bbox} is inconsistent with sample {sample_bbox}.')


class MainTest(TestUtility):
    ''' convert sample pdf files to docx, then verify the layout between 
        sample pdf and docx (saved as pdf file).
    '''

    def setUp(self):
        # create output path if not exist
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        
        # copy sample pdf
        for filename in os.listdir(self.sample_dir):
            if filename.endswith('pdf'):
                shutil.copy(os.path.join(self.sample_dir, filename), 
                    os.path.join(self.output_dir, f'{self.PREFIX_SAMPLE}-{filename}'))


    def tearDown(self):
        # close pdf object
        if self.SAMPLE_PDF: self.SAMPLE_PDF.close()
        if self.TEST_PDF: self.TEST_PDF.close()

        # delete pdf files generated for comparison purpose
        for filename in os.listdir(self.output_dir):
            if filename.startswith(self.PREFIX_SAMPLE) or filename.startswith(self.PREFIX_COMPARING):
                os.remove(os.path.join(self.output_dir, filename))


    def test_text_format(self):
        '''sample file focusing on text format'''
        # init pdf
        layouts = self.init_test('demo-text.pdf')

        # check text layout
        self.verify_layout()

        # check text style page by page
        for layout, page in zip(layouts, self.TEST_PDF):
            sample_style = self.extract_text_style(layout)
            test_style = self.extract_text_style(self.TEST_PDF.parse(page).layout)

            self.assertEqual(len(sample_style), len(test_style), 
                msg=f'The count of extracted style format {len(test_style)} is inconsistent with sample file {len(sample_style)}.')

            for s, t in zip(sample_style, test_style):
                self.assertEqual(s['text'], t['text'], 
                    msg=f"Applied text {t['text']} is inconsistent with sample {s['text']}")
                self.assertEqual(s['style'], t['style'], 
                    msg=f"Applied text format {t['style']} is inconsistent with sample {s['style']}")
        

    def test_image(self):
        '''sample file focusing on image, inline-image considered'''
        # init pdf
        layouts = self.init_test('demo-image.pdf')

        # check text layout
        self.verify_layout()

        # check images page by page
        for i, (layout, page) in enumerate(zip(layouts, self.TEST_PDF)):
            sample_images = self.extract_image(layout)
            test_images = self.extract_image(self.TEST_PDF.parse(page).layout)

            self.assertEqual(len(sample_images), len(test_images), 
                msg=f'The count of images {len(test_images)} is inconsistent with sample file {len(sample_images)}.')

            for s, t in zip(sample_images, test_images):
                matched = self.check_bbox(s, t, self.SAMPLE_PDF[i], 0.7)
                self.assertTrue(matched,
                    msg=f"Applied image bbox {t} is inconsistent with sample {s}.")


    def test_table_format(self):
        '''sample file focusing on table format'''
        # init pdf
        self.init_test('demo-table.pdf')

        # check text layout
        # if table is parsed successfully, all re-created text blocks should be same with sample file.
        self.verify_layout()
