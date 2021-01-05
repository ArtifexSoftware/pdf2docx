quickstart
===========

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

`pdf2docx` can be used as either CLI or a library.

### Command Line Interface

```
$ pdf2docx --help

NAME
    pdf2docx - Command line interface for pdf2docx.

SYNOPSIS
    pdf2docx COMMAND | -

DESCRIPTION
    Command line interface for pdf2docx.

COMMANDS
    COMMAND is one of the following:

     convert
       Convert pdf file to docx file.

     debug
       Convert one PDF page and plot layout information for debugging.

     table
       Extract table content from pdf pages.
```

- By range of pages

Specify pages range by `--start` (from the first page if omitted) and `--end` (to the last page if omitted). Note the page index is zero-based by default, but can turn it off by `--zero_based_index=False`, i.e. the first page index starts from 1.


```bash
$ pdf2docx convert test.pdf test.docx # all pages

$ pdf2docx convert test.pdf test.docx --start=1 # from the second page to the end

$ pdf2docx convert test.pdf test.docx --end=3 # from the first page to the third (index=2)

$ pdf2docx convert test.pdf test.docx --start=1 --end=3 # the second and third pages

$ pdf2docx convert test.pdf test.docx --start=1 --end=3 --zero_based_index=False # the first and second pages

```

- By page numbers

```bash
$ pdf2docx convert test.pdf test.docx --pages=0,2,4 # the first, third and 5th pages
```

- Multi-Processing

```bash
$ pdf2docx convert test.pdf test.docx --multi_processing=True # default count of CPU

$ pdf2docx convert test.pdf test.docx --multi_processing=True --cpu_count=4
```


### Python Library

We can use either the `Converter` class or a wrapped method `parse()`.

- `Converter`

```python
from pdf2docx import Converter

pdf_file = '/path/to/sample.pdf'
docx_file = 'path/to/sample.docx'

# convert pdf to docx
cv = Converter(pdf_file)
cv.convert(docx_file, start=0, end=None)
cv.close()
```


- Wrapped method `parse()`

```python
from pdf2docx import parse

pdf_file = '/path/to/sample.pdf'
docx_file = 'path/to/sample.docx'

# convert pdf to docx
parse(pdf_file, docx_file, start=0, end=None)
```

Or just to extract tables,

```python
from pdf2docx import Converter

pdf_file = '/path/to/sample.pdf'

cv = Converter(pdf_file)
tables = cv.extract_tables(start=0, end=1)
cv.close()

for table in tables:
    print(table)

# outputs
...
[['Input ', None, None, None, None, None], 
['Description A ', 'mm ', '30.34 ', '35.30 ', '19.30 ', '80.21 '],
['Description B ', '1.00 ', '5.95 ', '6.16 ', '16.48 ', '48.81 '],
['Description C ', '1.00 ', '0.98 ', '0.94 ', '1.03 ', '0.32 '],
['Description D ', 'kg ', '0.84 ', '0.53 ', '0.52 ', '0.33 '],
['Description E ', '1.00 ', '0.15 ', None, None, None],
['Description F ', '1.00 ', '0.86 ', '0.37 ', '0.78 ', '0.01 ']]
```