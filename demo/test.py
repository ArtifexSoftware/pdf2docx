import os
import sys

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from src.pdf2doc import Reader, Writer

import json


if __name__ == '__main__':

    output = os.path.join(os.path.dirname(script_path), 'samples')
    filename = 'demo-image'
    pdf_file = os.path.join(output, f'{filename}.pdf')
    docx_file = os.path.join(output, f'{filename}.docx')

    pdf = Reader(pdf_file)
    docx = Writer()

    for page in pdf[0:1]:

        # parse layout
        layout = pdf.parse(page, True, os.path.join(output, 'illustration.pdf'))       
        
        # create docx
        docx.make_page(layout)

        # print raw dict in json format
        # remove image content for json searializing
        for block in layout['blocks']:
            if 'image' in block: 
                block.pop('image')
            else:
                for line in block['lines']:
                    for span in line['spans']:
                        if 'image' in span: span.pop('image')

        with open(os.path.join(output, 'raw.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(layout))

    docx.save(docx_file)