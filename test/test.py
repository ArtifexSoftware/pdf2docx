import os
import sys

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from src.pdf2doc import Reader, Writer

import json

if __name__ == '__main__':

    output = os.path.join(os.path.dirname(script_path), 'demo')
    filename = 'demo-text'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    pdf = Reader(pdf_file)
    docx = Writer()

    for page in pdf[0:1]:
        with open(os.path.join(output, 'xxx.txt'), 'w', encoding='utf-8') as f:
            res = page.getText('dict')
            f.write(json.dumps(res))
        layout = pdf.parse(page, True)
        docx.make_page(layout)

    docx.save(docx_file)