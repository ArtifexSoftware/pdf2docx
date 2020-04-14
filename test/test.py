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


        layout = pdf.parse(page, True, os.path.join(output, 'illustration.pdf'))
        
        with open(os.path.join(output, 'xxx.txt'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(layout))

        # xref = page._getContents()[0]
        # cont = pdf._doc._getXrefStream(xref).decode()
        # with open(os.path.join(output, 'xxx.txt'), 'w', encoding='utf-8') as f:
        #     for line in cont.split():
        #         f.write(line+'\n')

        # docx.make_page(layout)

    # docx.save(docx_file)