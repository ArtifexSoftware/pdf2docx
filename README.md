# pdf2docx

- Parse layout/text format from PDF file with `PyMuPDF`
- Generate docx with `python-docx`

## Features

- [x] Rebuild page layout in docx
	- [x] paragraph and line spacing
	- [x] in-line image
- [x] Parse and re-create text format
	- [x] font style, e.g. font name, size, weight, italic and color
    - [x] highlight, underline, strike-through converted from docx
    - [x] highlight, underline, strike-through applied from PDF annotations
- [ ] Parse and re-create list style
- [ ] Parse and re-create table

## Limitations

- Support only normal reading direction - from left to right, from top to bottom.
- No word transformation, e.g. rotation is considered.
- Floating images is not supported.

## Usage

```python
import os
from pdf2docx import Reader, Writer

dir_output = '/path/to/output/dir/'
filename = 'demo-text'
pdf_file = os.path.join(dir_output, f'{filename}.pdf')
docx_file = os.path.join(dir_output, f'{filename}.docx')

pdf = Reader(pdf_file)
docx = Writer()

for page in pdf[0:1]:
    # debug mode: plot layout in new PDF file with PyMuPDF
    layout = pdf.parse(page, 
        debug=True, 
        filename=os.path.join(dir_output, 'illustration.pdf'))

    # re-create docx page
    docx.make_page(layout)

docx.save(docx_file)
```