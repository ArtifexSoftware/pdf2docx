import os
import sys

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from pdf2docx.reader import Reader
from pdf2docx.writer import Writer



if __name__ == '__main__':

    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-table'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    pdf = Reader(pdf_file, debug=True) # debug mode to plot layout
    docx = Writer()

    for page in pdf[0:1]:

        # parse layout
        layout = pdf.parse(page)
        
        # extract tables
        tables = pdf.extract_tables(page)
        for table in tables:
            print(table)
            print()
        
        # create docx
        docx.make_page(layout)


    docx.save(docx_file)
    pdf.close()
