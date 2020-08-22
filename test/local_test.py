# -*- coding: utf-8 -*-

''' local test file for developing, with pdf2docx installed by
    `python setpy.py develop`
'''

import os
from pdf2docx.converter import Converter
from pdf2docx.common.utils import compare_layput

if __name__ == '__main__':

    script_path = os.path.abspath(__file__) # current script path
    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-path-transformation'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    cv = Converter(pdf_file, docx_file, debug=True)

    # process page by page
    for page in cv[0:10]:

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
        cv.parse(page).make_page()
        
        # # extract tables
        # tables = cv.extract_tables(page)
        # for table in tables:
        #     print(table)
    
    cv.close() # close pdf

    # convert the docx file back to pdf manually, e.g. docx2pdf.pdf,
    # and compare results by checking bbox of each word.
    # The comparison result is stored in pdf file, e.g. comparison.pdf
    docx_pdf_file = os.path.join(output, f'docx2pdf.pdf')
    output_file = os.path.join(output, f'comparison.pdf')
    if compare_layput(pdf_file, docx_pdf_file, output_file, threshold=0.7):
        print('Fully matched.')