# pdf2docx 

![pdf2docx-test](https://github.com/dothinking/pdf2docx/workflows/pdf2docx-test/badge.svg)
![pdf2docx-publish](https://github.com/dothinking/pdf2docx/workflows/pdf2docx-publish/badge.svg)

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

### Limitations

- text-based PDF file only
- Normal reading direction only
    - horizontal paragraph/line/word
    - no word transformation, e.g. rotation
- No floating images
- Full borders table only


## Installation

### From Pypi

```
$ pip install pdf2docx
```

### From source code

Clone or download this project, and navigate to the root directory:

```
$ python setup.py install
```

Or install it in developing mode:

```
$ python setup.py develop
```

### Uninstall

```
$ pip uninstall pdf2docx
```

## Usage

### By range of pages

```
$ pdf2docx test.pdf test.docx --start=5 --end=10
```

### By page numbers

```
$ pdf2docx test.pdf test.docx --pages=5,7,9
```

```
$ pdf2docx --help

NAME
    pdf2docx - Run the pdf2docx parser

SYNOPSIS
    pdf2docx PDF_FILE DOCX_FILE <flags>

DESCRIPTION
    Run the pdf2docx parser

POSITIONAL ARGUMENTS
    PDF_FILE
        PDF filename to read from
    DOCX_FILE
        DOCX filename to write to

FLAGS
    --start=START
        first page to process, starting from zero
    --end=END
        last page to process, starting from zero
    --pages=PAGES
        range of pages

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

### As a source package

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

![sample_compare.png](https://s1.ax1x.com/2020/06/29/NWSJzT.png)

## License

- [GPL-3.0 License](./LICENSE)
- [AGPL-3.0 License](./LICENSE_AGPL)