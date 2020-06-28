import os
import sys
import shutil
import unittest
import fitz

from utils import Utility

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from pdf2docx.reader import Reader
from pdf2docx.writer import Writer


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
        sample_pdf = Reader(sample_pdf_file)

        # convert pdf to docx, besides, 
        # convert docx back to pdf for comparison next
        comparing_pdf_file = os.path.join(self.output_dir, f'{self.PREFIX_COMPARING}-{filename}')
        layouts = self.pdf2docx(sample_pdf, comparing_pdf_file)
        self.assertIsNotNone(layouts, msg='Converting PDF to Docx failed.')

        # testing pdf
        test_pdf_file = os.path.join(self.output_dir, comparing_pdf_file)
        test_pdf = Reader(test_pdf_file)

        # set default properties
        self.TEST_FILE = filename
        self.SAMPLE_PDF = sample_pdf
        self.TEST_PDF = test_pdf

        return layouts

    def pdf2docx(self, pdf, comparing_pdf_file):
        ''' test target: converting pdf to docx'''        
        docx = Writer()
        layouts = []
        for page in pdf:
            # parse layout
            layout = pdf.parse(page)
            layouts.append(layout)
            # create docx
            docx.make_page(layout)
        
        # save docx
        docx_file = pdf.filename[0:-3] + 'docx'
        docx_file = docx_file.replace(f'{self.PREFIX_SAMPLE}-', '')
        docx.save(docx_file)

        # convert to pdf for comparison
        if self.docx2pdf(docx_file, comparing_pdf_file):
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
    def get_text_image_blocks(layout):
        ''' get text blocks from both page and table level'''
        # text block in page level
        blocks = list(filter(lambda block: block['type'] in (0, 1), layout['blocks']))

        # blocks in table cell level
        tables = list(filter(lambda block: block['type'] in (3,4), layout['blocks']))
        for table in tables:
            for row in table['cells']:
                for cell in row:
                    if not cell: continue
                    blocks.extend(cell['blocks'])
        
        return blocks

    def extract_text_style(self, layout):
        ''' extract span text and style from layout'''        
        # text or image blocks
        blocks = self.get_text_image_blocks(layout)

        # check text format from text blocks
        res = []
        for block in blocks:
            if block['type']==1: continue
            for line in block['lines']:
                for span in line['spans']:
                    if not 'text' in span: continue
                    if not 'style' in span: continue
                    res.append({
                        'text': span['text'],
                        'style': [ t['type'] for t in span['style']]
                    })
        return res

    def extract_image(self, layout):
        ''' extract image bbox from layout'''
        # text or image blocks
        blocks = self.get_text_image_blocks(layout)

        # extract images
        res = []
        for block in blocks:
            if block['type']==1:
                res.append(block['bbox'])
            else:
                for line in block['lines']:
                    for span in line['spans']:
                        if not 'image' in span: continue
                        res.append(span['bbox'])
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
            test_style = self.extract_text_style(self.TEST_PDF.parse(page))

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
            test_images = self.extract_image(self.TEST_PDF.parse(page))

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
