# -*- coding: utf-8 -*-

''' local test file for developing, with pdf2docx installed by
    `python setpy.py develop`
'''

import os, sys
from pdf2docx import Converter
from pdf2docx.common.utils import compare_layput


def docx2pdf(docx_file, pdf_file):
    '''Windows local test only. convert docx to pdf with `OfficeToPDF`'''    
    # Windows: add OfficeToPDF to Path env. variable
    if not sys.platform.upper().startswith('WIN'):
        return False

    # convert pdf with command line
    cmd = f'OfficeToPDF "{docx_file}" "{pdf_file}"'
    try:
        os.system(cmd)
    except:
        return False
    else:
        return True


def check_result(pdf_file, docx_file, compare_file_name):
    ''' Convert the docx file back to pdf manually, and compare results 
        by checking bbox of each word. The comparison result is stored 
        in pdf file.
    '''
    output = os.path.dirname(docx_file)
    docx_pdf_file = os.path.join(output, f'docx2pdf.pdf')
    output_file = os.path.join(output, compare_file_name)

    print('Converting docx to pdf...')
    if docx2pdf(docx_file, docx_pdf_file):
        print('Comparing with sample pdf...')
        if compare_layput(pdf_file, docx_pdf_file, output_file, threshold=0.7):
            print('Fully matched.')
    else:
        print(f'Please convert {docx_file} to {docx_pdf_file} in advance.')


if __name__ == '__main__':

    script_path = os.path.abspath(__file__) # current script path
    output = os.path.dirname(script_path)
    filename = 'test'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    cv = Converter(pdf_file, docx_file)

    # process page by page
    for page in cv[0:1]:

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
        
        # print(cv.doc_pdf.xrefObject(94))

        # with open('x.svg', 'w') as f:
        #     f.write(page.getSVGimage(text_as_path=False))
        
        # parse layout
        cv.make_page(page)
        
        # # extract tables
        # tables = cv.extract_tables(page)
        # for table in tables:
        #     print(table)
    
    cv.close() # close pdf


    # check results
    # check_result(pdf_file, docx_file, 'comparison.pdf')