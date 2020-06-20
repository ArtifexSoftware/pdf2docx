import os
import sys

script_path = os.path.abspath(__file__) # current script path
project_path = os.path.dirname(os.path.dirname(script_path))
sys.path.append(project_path)

from pdf2docx.reader import Reader
from pdf2docx.writer import Writer

import json


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
        
        # # create docx
        docx.make_page(layout)

        # print raw dict in json format
        # remove image content for json searializing
        for block in layout['blocks']:
            # image block
            if block['type']==1: 
                block['image'] = '<image>'
            # table block
            elif block['type'] in (3, 4):
                for row in block['cells']:
                    for cell in row:
                        if not cell: continue
                        for _block in cell['blocks']:
                            if _block['type']==1:
                                _block['image'] = '<image>'
                            else:
                                for line in _block['lines']:
                                    for span in line['spans']:
                                        if 'image' in span: span['image'] = '<image>'
            # text block
            else:
                for line in block['lines']:
                    for span in line['spans']:
                        if 'image' in span: span['image'] = '<image>'

        with open(os.path.join(output, 'raw.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(layout))

    docx.save(docx_file)
    pdf.close()
