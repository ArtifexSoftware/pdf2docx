import os
import sys

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from src.pdf2doc import Reader, Writer



if __name__ == '__main__':

    output = os.path.join(os.path.dirname(script_path), 'demo')
    pdf_file = os.path.join(output, 'demo.pdf')
    docx_file = os.path.join(output, 'demo.docx')

    pdf = Reader(pdf_file)
    docx = Writer()

    for page in pdf[0:1]:
        layout = pdf.parse(page, True)
        docx.make_page(layout)

    docx.save(docx_file)