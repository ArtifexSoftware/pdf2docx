# -*- coding: utf-8 -*-

''' local test file for developing, with pdf2docx installed by
    `python setup.py develop`
'''

import os
import sys
import shutil
import fitz

from pdf2docx import Converter
from pdf2docx.common.Element import Element

script_path = os.path.abspath(__file__) # current script path
output = os.path.dirname(script_path)


def compare_layput(filename_source, filename_target, filename_output, threshold=0.7):
    ''' Compare layout of two pdf files:
        It's difficult to have an exactly same layout of blocks, but ensure they
        look like each other. So, with `extractWORDS()`, all words with bbox 
        information are compared.

        ```
        (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        ```
    '''
    # fitz document
    source = fitz.open(filename_source) # type: fitz.Document
    target = fitz.open(filename_target) # type: fitz.Document

    # check count of pages
    # --------------------------
    if len(source) != len(target):
        msg='Page count is inconsistent with source file.'
        print(msg)
        return False
    
    flag = True
    errs = []
    for source_page, target_page in zip(source, target):

        # check position of each word
        # ---------------------------
        source_words = source_page.getText('words')
        target_words = target_page.getText('words')

        # sort by word
        source_words.sort(key=lambda item: (item[4], round(item[1],1), round(item[0],1)))
        target_words.sort(key=lambda item: (item[4], round(item[1],1), round(item[0],1)))

        if len(source_words) != len(target_words):
            msg='Words count is inconsistent with source file.'
            print(msg)

        # check each word and bbox
        for sample, test in zip(source_words, target_words):
            source_rect, target_rect = fitz.Rect(sample[0:4]), fitz.Rect(test[0:4])

            # draw bbox based on source layout
            source_page.drawRect(source_rect, color=(1,1,0), overlay=True) # source position
            source_page.drawRect(target_rect, color=(1,0,0), overlay=True) # current position

            # check bbox word by word: ignore small bbox, e.g. single letter bbox
            if not Element().update_bbox(source_rect).get_main_bbox(target_rect, threshold):
                flag = False
                errs.append((f'{sample[4]} ===> {test[4]}', target_rect, source_rect))
        
    # save and close
    source.save(filename_output)
    target.close()
    source.close()

    # outputs
    for word, target_rect, source_rect in errs:
        print(f'Word "{word}": \nsample bbox: {source_rect}\ncurrent bbox: {target_rect}\n')

    return flag


def docx2pdf(docx_file, pdf_file):
    '''Windows local test only. convert docx to pdf with `OfficeToPDF`'''    
    # Windows: add OfficeToPDF to Path env. variable
    if not sys.platform.upper().startswith('WIN'):
        return False

    # convert pdf with command line
    cmd = f'OfficeToPDF "{docx_file}" "{pdf_file}"'
    res = os.system(cmd)
    return res==0


def check_result(pdf_file, docx_file, compare_file_name, make_test_case):
    ''' Convert the docx file back to pdf manually, and compare results 
        by checking bbox of each word. The comparison result is stored 
        in pdf file.
    '''
    _, filename = os.path.split(pdf_file)
    docx_pdf_file = os.path.join(output, f'docx2pdf.pdf')
    output_file = os.path.join(output, compare_file_name)

    print(f'{filename}...\n{"-"*50}')

    print('Converting docx to pdf...')
    if docx2pdf(docx_file, docx_pdf_file):

        print('Comparing with sample pdf...')
        if compare_layput(pdf_file, docx_pdf_file, output_file, threshold=0.7):
            print(f'* fully matched.')
        
        if make_test_case:
            layout_file = filename.replace('.pdf', '.json')
            print(f'Copy to {layout_file}...')
            shutil.move(os.path.join(os.path.dirname(pdf_file), 'layout.json'), os.path.join(output, 'layouts', layout_file))

        print()

    else:
        print(f'Please convert {docx_file} to {docx_pdf_file} in advance.')


def local_test(sub_path, filename, compare=False, make_test_case=False):
    pdf_file = os.path.join(output, sub_path, f'{filename}.pdf')
    docx_file = os.path.join(output, sub_path, f'{filename}.docx')

    page_index = 0
    cv = Converter(pdf_file)
    page = cv.fitz_doc[page_index]

    # print(page.rotation, page.rotationMatrix)
    # print(page.transformationMatrix)
    # print(page.rect, page.MediaBox, page.CropBox)

    # print(page.xref)
    # print(page.getContents())
    # print(cv.doc_pdf.xrefObject(page.xref))
    # page.cleanContents()
    # c = page.readContents().decode(encoding="ISO-8859-1")
    # with open('c.txt', 'w') as f:
    #     f.write(c)
    
    # print(cv.doc_pdf.xrefObject(6))
    # print(cv.doc_pdf._getXrefString(7))


    # with open('x.svg', 'w') as f:
    #     f.write(page.getSVGimage(text_as_path=False))
    
    # parse layout
    cv.debug_page(page_index, docx_file)
    
    # # extract tables
    # tables = cv.extract_tables([page_index])
    # for table in tables:
    #     print(table)
    
    cv.close() # close pdf


    # check results
    if compare:
        check_result(pdf_file, docx_file, 'comparison.pdf', make_test_case)


if __name__ == '__main__':

    filenames = [
        'demo-blank',
        'demo-image', 
        'demo-image-cmyk', 
        'demo-image-transparent',
        'demo-image-vector-graphic',
        'demo-text', 
        'demo-text-scaling', 
        'demo-text-alignment',
        'demo-text-unnamed-fonts', 
        'demo-path-transformation', 
        'demo-table', 
        'demo-table-bottom', 
        'demo-table-nested', 
        'demo-table-shading', 
        'demo-table-shading-highlight',
        'demo-table-border-style', 
        'demo-table-align-borders',
        'demo-table-close-underline',
        'demo-table-lattice',
        'demo-table-lattice-one-cell',
        'demo-table-stream'
    ]

    # single sample
    sub_path, filename = sys.argv[1:]
    # local_test(sub_path, filename, compare=True, make_test_case=True)

    # batch mode
    for filename in filenames: local_test(sub_path, filename, compare=True, make_test_case=True)