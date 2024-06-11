'''
The test framework: pytest, pytest-cov.

We have a set of PDF files as test inputs.

For a test file foo.pdf, we convert it into a file foo.pdf.docx using pdf2docx.

To check whether this has worked as expected, we use Python package docx2pdf
(which uses Word) on Windows, or Libreoffice command line on other platforms,
to convert foo.pdf.docx into foo.pdf.docx.pdf.

We then compare foo.pdf.docx.pdf with the original foo.pdf file using opencv,
generating a similarity value.

So on Windows we require Word is installed, and on other platforms we require
that Libreoffice is installed.

If docx2pdf fails with `Object reference not set to an instance of an
object. Did not convert`, it might be necessary to follow the instructions at:

    https://stackoverflow.com/questions/24860351/object-reference-not-set-to-an-instance-of-an-object-did-not-convert

    In a Cmd window run:
        DCOMCNFG
    Then:
        Console Root > Component Services > Computers > My Computer > DCOM Config > Microsoft Word 97 - 2003 Document
    Then: Right click then properties then Identity tab and set a username and
    password.
'''

import glob
import os
import io
import numpy as np
import cv2 as cv
import fitz
from pdf2docx import Converter, parse
import subprocess
import time
import shutil
import platform
import pytest


root_path = os.path.abspath(f'{__file__}/../..')
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


def run(command):
   print(f'Running: {command}')
   subprocess.run(command, shell=1, check=1)


def document_to(in_, out):
    if platform.system() == 'Windows':
        return word_to(in_, out)
    else:
        return libreoffice_to(in_, out)


_g_word_to_docx2pdf = False

def word_to(in_, out):
    global _g_word_to_docx2pdf
    if not _g_word_to_docx2pdf:
        run('pip install docx2pdf')
        import docx2pdf
        _g_word_to_docx2pdf = True
    assert os.path.isfile(in_), f'Not a file: {in_=}'
    run(f'docx2pdf {in_} {out}')
    return
    import docx2pdf
    try:
        docx2pdf.convert(in_, out)
    except Exception as e:
        print(f'docx2pdf.convert() raised exception: {e}')
        raise
    


def libreoffice_to(in_, out):
    '''Converts file to pdf using libreoffice. Returns generated path
    f'{in_}.pdf'.'''
    # Libreoffice does not allow direct specification of the output path and
    # goes wrong wtih paths with multiple '.' characters, so we work on a
    # temporary. Also it does not return non-zero if it fails so we check
    # mtime.
    #print(f'{in_=} {out=}')
    assert os.path.isfile(in_)
    in_root, in_ext = os.path.splitext(in_)
    _, out_ext = os.path.splitext(out)
    out_dir = os.path.dirname(out)
    temp = f'{out_dir}/_temp_libreoffice_to'
    in2 = f'{temp}{in_ext}'
    out2 = f'{temp}{out_ext}'
    shutil.copy2(in_, in2)
    try:
        t = time.time()
        #print(f'{in_=} {in2=} {in_ext=}')
        run(f'libreoffice --convert-to {out_ext[1:]} --outdir {out_dir} {in2}')
        os.rename(out2, out)
        t_out = os.path.getmtime(out)
        assert t_out >= t, f'libreoffice failed to update/create {out=}'
    finally:
        os.remove(in2)
        if os.path.isfile(out2):
            os.remove(out2)


def compare_pdf(pdf1, pdf2, num_pages=None):
    #print(f'Comparing {pdf1=} {pdf2=}')
    with fitz.Document(pdf1) as doc1, fitz.Document(pdf2) as doc2:
        if num_pages:
            n1 = num_pages
        else:
            n1 = len(doc1)
            n2 = len(doc2)
            if n1 != n2:
                print(f'Differing numbers of pages: {n1=} {n2=}.')
                return -1
        sidx = 0
        # Find average similarity.
        for n in range(n1):
            diff_png = f'{pdf2}.diff.{n}.png'
            sidx_n = get_page_similarity(doc1[n], doc2[n], diff_png)
            #print(f'Page {n}: {diff_png} {sidx_n=}.')
            sidx += sidx_n
        sidx /= n1
        #print(f'{sidx=}')
        return sidx


class TestConversion:
    '''Test the converting process.'''

    def setup_method(self):
        '''create output path if not exist.'''
        if not os.path.exists(output_path): os.mkdir(output_path)


    def convert(self, filename):
        '''Convert PDF file from sample path to output path.'''
        source_pdf_file = os.path.join(sample_path, f'{filename}.pdf')
        docx_file = os.path.join(output_path, f'{filename}.docx')
        c = Converter(source_pdf_file)
        c.convert(docx_file)
        c.close()

    def convert_by_io_stream(self, filename):
        '''Convert PDF file from sample path to output path.'''
        source_pdf_file = os.path.join(sample_path, f'{filename}.pdf')
        with open(source_pdf_file, 'rb') as f: in_stream = f.read()

        c = Converter(stream=in_stream)
        out_stream = io.BytesIO()
        c.convert(out_stream)
        c.close()

        docx_file = os.path.join(output_path, f'{filename}.docx')
        with open(docx_file, 'wb') as f: f.write(out_stream.getvalue())


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


# We make a separate pytest test for each sample file.

def _find_paths():
    ret = list()
    for path in glob.glob(f'{sample_path}/*.docx') + glob.glob(f'{sample_path}/*.pdf'):
        path_leaf = os.path.basename(path)
        if path_leaf.count('.') > 1:
            continue
        if path_leaf == 'demo-whisper_2_3.pdf':
            # Known to fail.
            continue
        ret.append(os.path.relpath(path, root_path))
    return ret

g_paths = _find_paths()

# We create a separate pytest for each sample file, paramaterised using the
# path of the sample file relative to the pdf2docx directory.
#
# So one can run a specific test with:
#
# pytest pdf2docx/test/test.py::test_one[test/samples/demo-whisper_2_3.pdf]

@pytest.mark.parametrize('path', g_paths)
def test_one(path):
    '''Check the quality of converted docx.
    '''
    
    # Where there are two values, they are (sidx_required_word,
    # sidx_required_libreoffice).
    #
    docx_to_sidx_required = {
        'demo-blank.pdf': 1.0,
        'demo-image-cmyk.pdf': 0.90,
        'demo-image-transparent.pdf': 0.90,
        'demo-image-vector-graphic.pdf': (0.89, 0.68),
        'demo-image.pdf': 0.90,
        'demo-image-rotation.pdf': (0.90, 0.82),
        'demo-image-overlap.pdf': (0.90, 0.70),
        'demo-path-transformation.pdf': (0.89, 0.60),
        'demo-section-spacing.pdf': (0.90, 0.86),
        'demo-section.pdf': (0.70, 0.45),
        'demo-table-align-borders.pdf': 0.49,
        'demo-table-border-style.pdf': (0.90, 0.89),
        'demo-table-bottom.pdf': 0.90,
        'demo-table-close-underline.pdf': (0.57, 0.49),
        'demo-table-lattice-one-cell.pdf': (0.79, 0.75),
        'demo-table-lattice.pdf': (0.75, 0.59),
        'demo-table-nested.pdf': 0.84,
        'demo-table-shading-highlight.pdf': (0.55, 0.45),
        'demo-table-shading.pdf': (0.80, 0.60),
        'demo-table-stream.pdf': 0.55,
        'demo-table.pdf': (0.90, 0.75),
        'demo-text-alignment.pdf': (0.90, 0.86),
        'demo-text-scaling.pdf': (0.80, 0.65),
        'demo-text-unnamed-fonts.pdf': (0.80, 0.77),
        'demo-text-hidden.pdf': 0.90,
        'demo-text.pdf': 0.80,
        'pdf2docx-lists-bullets3.docx': (0.98, 0.99),
    }

    print(f'# Looking at: {path}')
    path = f'{root_path}/{path}'
    path_leaf = os.path.basename(path)
    _, ext = os.path.splitext(path)
    if ext == '.docx':
        pdf = f'{path}.pdf'
        document_to(path, pdf)
    else:
        pdf = path
    docx2 = f'{pdf}.docx'
    pages = None
    if os.path.basename(path) == 'demo-whisper_2_3.pdf':
        pages = [25, 26, 27]
    else:
        with fitz.Document(pdf) as doc:
            if len(doc) > 1:
                print(f'Not testing because more than one page: {path}')
                return
    #print(f'Calling parse() {pdf=} {docx2=}')
    parse(pdf, docx2, pages=pages, raw_exceptions=True)
    assert os.path.isfile(docx2)
    pdf2 = f'{docx2}.pdf'
    document_to(docx2, pdf2)
    sidx = compare_pdf(pdf, pdf2, num_pages=1)

    sidx_required = docx_to_sidx_required.get(path_leaf)
    if sidx_required:
        if isinstance(sidx_required, tuple):
            sr_word, sr_libreoffice = sidx_required
            sidx_required = sr_word if platform.system() == 'Windows' else sr_libreoffice

        #print(f'{path=}: {sidx_required=} {sidx=}.')
        if sidx < sidx_required:
            print(f'{sidx=} too low - should be >= {sidx_required=}')
            print(f'    {pdf}')
            print(f'    {pdf2}')
            assert 0
    else:
        print(f'# No sidx_required available for {path_leaf=}.')
