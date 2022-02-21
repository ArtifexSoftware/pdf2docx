# -*- coding: utf-8 -*-

'''
To test the pdf conversion and converting quality, the idea is to convert generated docx to pdf,
then check the image similarity between source pdf page and converted pdf page. Considering the 
converting quality from docx to pdf, a Windows-based command line tool `OfficeToPDF` is used, in
addition, an installation of Microsoft Word is required.

To leverage the benefit of Github Action, the testing process is divided into three parts:
  1. Convert sample pdf to docx with this module.
  2. Convert generated docx to pdf for comparing. 
  3. Convert page to image and compare similarity with python-opencv.

Test scripts on Part One and Three are applied with two test class respectively in this module,
so they could be run seperately with pytest command, e.g.

- pytest -v test.py::TestConversion for Part One
- pytest -v test.py::TestQuality for Part Three

Links on MS Word to PDF conversion:
  - https://github.com/cognidox/OfficeToPDF/releases
  - https://github.com/AndyCyberSec/pylovepdf
  - https://www.e-iceblue.com/Tutorials/Java/Spire.Doc-for-Java/Program-Guide/Conversion/Convert-Word-to-PDF-in-Java.html
'''

import os
import numpy as np
import cv2 as cv
import fitz
from pdf2docx import Converter, parse


script_path = os.path.abspath(__file__) # current script path
test_dir = os.path.dirname(script_path)
sample_path = os.path.join(test_dir, 'samples')
output_path = os.path.join(test_dir, 'outputs')


def get_page_similarity(page_a, page_b, diff_img_filename='diff.png'):
    '''Calculate page similarity index: [0, 1].'''
    # page to opencv image
    image_a = get_page_image(page_a)
    image_b = get_page_image(page_b)

    # resize if different shape
    if image_a.shape != image_b.shape:
        rows, cols = image_a.shape[:2]
        image_b = cv.resize(image_b, (cols, rows))
    
    # write different image
    if diff_img_filename:
        diff = cv.subtract(image_a, image_b)
        cv.imwrite(diff_img_filename, diff)
    
    return get_mssism(image_a, image_b)


def get_page_image(pdf_page):
    '''Convert fitz page to opencv image.'''
    img_byte = pdf_page.get_pixmap(clip=pdf_page.rect).tobytes()
    img = np.frombuffer(img_byte, np.uint8)
    return cv.imdecode(img, cv.IMREAD_COLOR)


def get_mssism(i1, i2, kernel=(15,15)):
    '''Calculate mean Structural Similarity Index (SSIM).
    https://docs.opencv.org/4.x/d5/dc4/tutorial_video_input_psnr_ssim.html
    '''
    C1 = 6.5025
    C2 = 58.5225
    # INITS
    I1 = np.float32(i1) # cannot calculate on one byte large values
    I2 = np.float32(i2)
    I2_2 = I2 * I2 # I2^2
    I1_2 = I1 * I1 # I1^2
    I1_I2 = I1 * I2 # I1 * I2
    # END INITS
    # PRELIMINARY COMPUTING
    mu1 = cv.GaussianBlur(I1, kernel, 1.5)
    mu2 = cv.GaussianBlur(I2, kernel, 1.5)
    mu1_2 = mu1 * mu1
    mu2_2 = mu2 * mu2
    mu1_mu2 = mu1 * mu2
    sigma1_2 = cv.GaussianBlur(I1_2, kernel, 1.5)
    sigma1_2 -= mu1_2
    sigma2_2 = cv.GaussianBlur(I2_2, kernel, 1.5)
    sigma2_2 -= mu2_2
    sigma12 = cv.GaussianBlur(I1_I2, kernel, 1.5)
    sigma12 -= mu1_mu2
    t1 = 2 * mu1_mu2 + C1
    t2 = 2 * sigma12 + C2
    t3 = t1 * t2                    # t3 = ((2*mu1_mu2 + C1).*(2*sigma12 + C2))
    t1 = mu1_2 + mu2_2 + C1
    t2 = sigma1_2 + sigma2_2 + C2
    t1 = t1 * t2                    # t1 =((mu1_2 + mu2_2 + C1).*(sigma1_2 + sigma2_2 + C2))
    ssim_map = cv.divide(t3, t1)    # ssim_map =  t3./t1;
    mssim = cv.mean(ssim_map)       # mssim = average of ssim map
    return np.mean(mssim[0:3])



class TestConversion:
    '''Test the converting process.'''

    def setup(self):
        '''create output path if not exist.'''
        if not os.path.exists(output_path): os.mkdir(output_path)
    

    def convert(self, filename):
        '''Convert PDF file from sample path to output path.'''
        source_pdf_file = os.path.join(sample_path, f'{filename}.pdf')
        docx_file = os.path.join(output_path, f'{filename}.docx')
        cv = Converter(source_pdf_file)        
        cv.convert(docx_file)
        cv.close()    

    # ------------------------------------------
    # layout: section
    # ------------------------------------------
    def test_section(self):
        '''test page layout: section and column.'''
        self.convert('demo-section')    

    def test_section_spacing(self):
        '''test page layout: section vertical position.'''
        self.convert('demo-section-spacing')

    # ------------------------------------------
    # text styles
    # ------------------------------------------
    def test_blank_file(self):
        '''test blank file without any texts or images.'''
        self.convert('demo-blank')

    def test_text_format(self):
        '''test text format, e.g. highlight, underline, strike-through.'''
        self.convert('demo-text')

    def test_text_alignment(self):
        '''test text alignment.'''
        self.convert('demo-text-alignment')    
    
    def test_unnamed_fonts(self):
        '''test unnamed fonts which destroys span bbox, and accordingly line/block layout.'''
        self.convert('demo-text-unnamed-fonts')

    def test_text_scaling(self):
        '''test font size. In this case, the font size is set precisely with character scaling.'''
        self.convert('demo-text-scaling')

    # ------------------------------------------
    # image styles
    # ------------------------------------------
    def test_image(self):
        '''test inline-image.'''
        self.convert('demo-image')

    def test_vector_graphic(self):
        '''test vector graphic.'''
        self.convert('demo-image-vector-graphic')

    def test_image_cmyk(self):
        '''test image in CMYK color-space.'''
        self.convert('demo-image-cmyk')

    def test_image_transparent(self):
        '''test transparent images.'''
        self.convert('demo-image-transparent')
    
    def test_image_rotation(self):
        '''test rotating image due to pdf page rotation.'''
        self.convert('demo-image-rotation')

    def test_image_overlap(self):
        '''test images with both intersection and page rotation.'''
        self.convert('demo-image-overlap')


    # ------------------------------------------
    # table styles
    # ------------------------------------------
    def test_table_bottom(self):
        '''page break due to table at the end of page.'''
        self.convert('demo-table-bottom')

    def test_table_format(self):
        '''test table format, e.g. 
            - border and shading style
            - vertical cell
            - merged cell
            - text format in cell
        '''
        self.convert('demo-table')

    def test_stream_table(self):
        '''test stream structure and shading.'''
        self.convert('demo-table-stream')

    def test_table_shading(self):
        '''test simulating shape with shading cell.'''
        self.convert('demo-table-shading')
    
    def test_table_shading_highlight(self):
        '''test distinguishing table shading and highlight.'''
        self.convert('demo-table-shading-highlight')

    def test_lattice_table(self):
        '''test lattice table with very close text underlines to table borders.'''
        self.convert('demo-table-close-underline')

    def test_lattice_table_invoice(self):
        '''test invoice sample file with lattice table, vector graphic.'''
        self.convert('demo-table-lattice')

    def test_lattice_cell(self):
        '''test generating stream borders for lattice table cell.'''
        self.convert('demo-table-lattice-one-cell')

    def test_table_border_style(self):
        '''test border style, e.g. width, color.'''
        self.convert('demo-table-border-style')

    def test_table_align_borders(self):
        '''aligning stream table borders to simplify table structure.'''
        self.convert('demo-table-align-borders')

    def test_nested_table(self):
        '''test nested tables.'''
        self.convert('demo-table-nested')

    def test_path_transformation(self):
        '''test path transformation. In this case, the (0,0) origin is out of the page.'''
        self.convert('demo-path-transformation')


    # ------------------------------------------
    # table contents
    # ------------------------------------------
    def test_extracting_table(self):
        '''test extracting contents from table.'''
        filename = 'demo-table'
        pdf_file = os.path.join(sample_path, f'{filename}.pdf')
        tables = Converter(pdf_file).extract_tables(end=1)
        print(tables)

        # compare the last table
        table = [[col.strip() if col else col for col in row] for row in tables[-1]]
        sample = [
            ['Input', None, None, None, None, None],
            ['Description A', 'mm', '30.34', '35.30', '19.30', '80.21'],
            ['Description B', '1.00', '5.95', '6.16', '16.48', '48.81'],
            ['Description C', '1.00', '0.98', '0.94', '1.03', '0.32'],
            ['Description D', 'kg', '0.84', '0.53', '0.52', '0.33'],
            ['Description E', '1.00', '0.15', None, None, None],
            ['Description F', '1.00', '0.86', '0.37', '0.78', '0.01']
        ]
        assert table==sample

    
    # ------------------------------------------
    # command line arguments
    # ------------------------------------------
    def test_multi_pages(self):
        '''test converting pdf with multi-pages.'''
        filename = 'demo'
        pdf_file = os.path.join(sample_path, f'{filename}.pdf')
        docx_file = os.path.join(output_path, f'{filename}.docx')    
        parse(pdf_file, docx_file, start=1, end=5)

        # check file        
        assert os.path.isfile(docx_file)
    


class TestQuality:
    '''Check the quality of converted docx. 
    Note the docx files must be converted to PDF files in advance.
    '''

    INDEX_MAP = {
        'demo-blank.pdf': 1.0,
        'demo-image-cmyk.pdf': 0.90,
        'demo-image-transparent.pdf': 0.90,
        'demo-image-vector-graphic.pdf': 0.89,
        'demo-image.pdf': 0.90,
        'demo-image-rotation.pdf': 0.90,
        'demo-image-overlap.pdf': 0.90,
        'demo-path-transformation.pdf': 0.90,
        'demo-section-spacing.pdf': 0.90,
        'demo-section.pdf': 0.70,
        'demo-table-align-borders.pdf': 0.49,
        'demo-table-border-style.pdf': 0.90,
        'demo-table-bottom.pdf': 0.90,
        'demo-table-close-underline.pdf': 0.58,
        'demo-table-lattice-one-cell.pdf': 0.79,
        'demo-table-lattice.pdf': 0.75,
        'demo-table-nested.pdf': 0.84,
        'demo-table-shading-highlight.pdf': 0.55,
        'demo-table-shading.pdf': 0.80,
        'demo-table-stream.pdf': 0.60,
        'demo-table.pdf': 0.90,
        'demo-text-alignment.pdf': 0.90,
        'demo-text-scaling.pdf': 0.80,
        'demo-text-unnamed-fonts.pdf': 0.80,
        'demo-text.pdf': 0.80
    }

    def setup(self):
        '''create output path if not exist.'''
        if not os.path.exists(output_path): os.mkdir(output_path)


    def test_quality(self):
        '''Convert page to image and compare similarity.'''
        for filename in os.listdir(output_path):
            if not filename.endswith('pdf'): continue

            source_pdf_file = os.path.join(sample_path, filename)
            target_pdf_file = os.path.join(output_path, filename)

            # open pdf    
            source_pdf = fitz.open(source_pdf_file)
            target_pdf = fitz.open(target_pdf_file)

            # compare page count
            if len(source_pdf)>1: continue # one page sample only
            assert len(target_pdf)==1, f"\nThe page count of {filename} is incorrect."

            # compare the first page
            diff_png = os.path.join(output_path, f'{filename[:-4]}.png')
            sidx = get_page_similarity(target_pdf[0], source_pdf[0], diff_png)
            threshold = TestQuality.INDEX_MAP.get(filename, 0.10)
            print(f'Checking {filename}: {sidx} v.s. {threshold}')
            assert sidx>=threshold, 'Significant difference might exist since similarity index is lower than threshold.'
