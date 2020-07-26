''' local test file for developing, with pdf2docx installed by
    `python setpy.py develop`
'''

import os

from pdf2docx.converter import Converter


if __name__ == '__main__':

    script_path = os.path.abspath(__file__) # current script path
    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-table'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    cv = Converter(pdf_file, docx_file, debug=True)

    # process page by page
    for page in cv[0:1]:

        # parse layout
        cv.parse(page).make_page()
        
        # # extract tables
        # tables = cv.extract_tables(page)
        # for table in tables:
        #     print(table)

    # close pdf
    cv.close()