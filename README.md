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

- Normal reading direction only
    - horizontal paragraph/line/word
    - no word transformation, e.g. rotation
- No floating images

## Usage

```python
import os
from pdf2docx.reader import Reader
from pdf2docx.writer import Writer

dir_output = '/path/to/output/dir/'
filename = 'demo-text'
pdf_file = os.path.join(dir_output, f'{filename}.pdf')
docx_file = os.path.join(dir_output, f'{filename}.docx')

pdf = Reader(pdf_file, debug=True)  # debug mode to plot layout in new PDF file
docx = Writer()

for page in pdf[0:1]:
    # parse raw layout
    layout = pdf.parse(page)
    # re-create docx page
    docx.make_page(layout)

docx.save(docx_file)
pdf.close()
```