import os
import sys
import unittest
import fitz

from utils import Utility

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from src.pdf2doc import Reader, Writer


class TestUtility(Utility, unittest.TestCase):
    '''utilities related directly to the test case'''

    def pdf2docx(self, pdf):
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
        docx_file = self.get_docx_path(pdf.filename)
        docx.save(docx_file)

        # convert to pdf for comparison
        if self.docx2pdf(docx_file):
            return layouts
        else:
            return None   

    @staticmethod
    def check_bbox(b1, b2, threshold=0.9):
        ''' if the intersection of two bbox-es exceeds a threshold, they're considered same'''
        b1, b2 = fitz.Rect(b1), fitz.Rect(b2)
        b = b1 & b2
        area = b.getArea()
        print(area/b1.getArea(), area/b2.getArea())
        return area/b1.getArea()>=threshold and area/b2.getArea()>=threshold    

    @staticmethod
    def extract_text_style(layout):
        ''' extract span text and style from layout'''
        res = []
        for block in layout['blocks']:
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

    @staticmethod
    def extract_image(layout):
        ''' extract image information from layout'''
        res = []
        for block in layout['blocks']:
            if block['type']==1:
                res.append(block['bbox'])
            else:
                for line in block['lines']:
                    for span in line['spans']:
                        if not 'image' in span: continue
                        res.append(span['bbox'])
        return res

    def verify_layout(self, sample_pdf, test_pdf, threshold=0.9):
        ''' compare layout of two pdf files:
            It's difficult to have an exactly same layout of blocks, but ensure they
            look like each other. So, with `extractWORDS()`, all words with bbox 
            information are compared.
            (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        '''
        for sample_page, test_page in zip(sample_pdf, test_pdf):
            sample_words = sample_page.getText('words')
            test_words = test_page.getText('words')

            # sort by word
            sample_words.sort(key=lambda item: (item[4], item[0], item[1]))
            test_words.sort(key=lambda item: (item[4], item[0], item[1]))

            # check each word and bbox
            for sample, test in zip(sample_words, test_words):
                sample_bbox, test_bbox = sample[0:4], test[0:4]
                sample_word, test_word = sample[4], test[4]
                self.assertEqual(sample_word, test_word)
                self.assertTrue(self.check_bbox(sample_bbox, test_bbox, threshold),
                    msg=f'bbox for word "{sample_word}": {test_bbox} is inconsistent with sample {sample_bbox}.')


class MainTest(TestUtility):
    ''' convert sample pdf files to docx, then verify the layout between 
        sample pdf and docx (saved as pdf file).
    '''

    def setUp(self):
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)    

    def test_text_format(self):
        '''sample file focusing on text format'''
        # sample pdf
        filename = 'demo-text.pdf'
        sample_pdf_file = os.path.join(self.sample_dir, filename)
        sample_pdf = Reader(sample_pdf_file)

        # convert pdf to docx, besides, 
        # convert docx agagin to pdf for comparison next
        layouts = self.pdf2docx(sample_pdf)
        self.assertIsNotNone(layouts, msg='Converting PDF to Docx failed.')

        # converted pdf
        test_pdf_file = os.path.join(self.output_dir, filename)
        test_pdf = Reader(test_pdf_file)

        # check count of pages
        self.assertEqual(len(layouts), len(test_pdf), 
            msg='Page count is inconsistent with sample file.')

        # check text layout
        # self.verify_layout(sample_pdf, test_pdf)

        # check text style page by page
        for layout, page in zip(layouts, test_pdf):
            sample_style = self.extract_text_style(layout)
            test_style = self.extract_text_style(test_pdf.parse(page))

            self.assertEqual(len(sample_style), len(test_style), 
                msg=f'The extracted style format {len(test_style)} is inconsistent with sample file {len(sample_style)}.')

            for s, t in zip(sample_style, test_style):
                self.assertEqual(s['text'], t['text'], 
                    msg=f"Applied text {t['text']} is inconsistent with sample {s['text']}")
                self.assertEqual(s['style'], t['style'], 
                    msg=f"Applied text format {t['style']} is inconsistent with sample {s['style']}")


    @unittest.skip("a bit update on the layout is planed, skipping temporarily.")
    def test_image(self):
        '''sample file focusing on image, inline-image considered'''
        # sample pdf
        filename = 'demo-image.pdf'
        sample_pdf_file = os.path.join(self.sample_dir, filename)
        sample_pdf = Reader(sample_pdf_file)

        # convert pdf to docx, besides, 
        # convert docx agagin to pdf for comparison next
        layouts = self.pdf2docx(sample_pdf)
        self.assertIsNotNone(layouts, msg='Converting PDF to Docx failed.')

        # converted pdf
        test_pdf_file = os.path.join(self.output_dir, filename)
        test_pdf = Reader(test_pdf_file)

        # check count of pages
        self.assertEqual(len(layouts), len(test_pdf), 
            msg='Page count is inconsistent with sample file.')

        # check text layout
        self.verify_layout(sample_pdf, test_pdf)

        # check text style page by page
        for layout, page in zip(layouts, test_pdf):
            sample_images = self.extract_image(layout)
            target_images = self.extract_image(test_pdf.parse(page))            
            for s, t in zip(sample_images, target_images):
                self.assertTrue(self.check_bbox(s, t, 0.8),
                msg=f"Applied image bbox {t} is inconsistent with sample {s}")