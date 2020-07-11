''' local test file for developing, with pdf2docx installed by
    `python setpy.py develop`
'''

import os
from pdf2docx.main import parse, extract_tables


if __name__ == '__main__':

    script_path = os.path.abspath(__file__) # current script path
    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-table'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    # convert pdf to docx
    parse(pdf_file, docx_file, start=0, end=1)

    # extract tables
    tables = extract_tables(pdf_file, start=0, end=1)
    for table in tables:
        print(table)