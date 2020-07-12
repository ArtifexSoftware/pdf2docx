''' local test file for developing, with pdf2docx installed by
    `python setpy.py develop`
'''

import os

from pdf2docx.reader import Reader
from pdf2docx.writer import Writer


if __name__ == '__main__':

    script_path = os.path.abspath(__file__) # current script path
    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-table'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    pdf = Reader(pdf_file, debug=True)
    docx = Writer()

    # process page by page
    for page in pdf[0:1]:

        # parse layout
        layout = pdf.parse(page)
        
        # extract tables
        tables = pdf.extract_tables(page)
        for table in tables:
            print(table)

        # create docx
        docx.make_page(layout)

    # save docx, close pdf
    docx.save(docx_file)
    pdf.close()