# pdf2docx

- Parse text, table and layout from PDF file with `PyMuPDF`
- Generate docx with `python-docx`

## Features

- [x] Parse and re-create text format
	- [x] font style, e.g. font name, size, weight, italic and color
    - [x] highlight, underline, strike-through converted from docx
    - [x] highlight, underline, strike-through applied from PDF annotations
- [ ] Parse and re-create list style
- [x] Parse and re-create table
    - [x] border style, e.g. width, color
    - [x] shading style, i.e. background color
    - [x] merged cells
- [x] Rebuild page layout in docx
	- [x] paragraph layout: horizontal and vertical spacing
	- [x] in-line image

## Limitations

- Normal reading direction only
    - horizontal paragraph/line/word
    - no word transformation, e.g. rotation
- No floating images
- Full borders table only

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

## Sample

![sample_compare.png](https://s1.ax1x.com/2020/06/21/N39L6I.png)