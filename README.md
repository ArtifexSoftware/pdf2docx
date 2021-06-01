# pdf2docx 

![python-version](https://img.shields.io/badge/python->=3.6-green.svg)
[![codecov](https://codecov.io/gh/dothinking/pdf2docx/branch/master/graph/badge.svg)](https://codecov.io/gh/dothinking/pdf2docx)
[![pypi-version](https://img.shields.io/pypi/v/pdf2docx.svg)](https://pypi.python.org/pypi/pdf2docx/)
![license](https://img.shields.io/pypi/l/pdf2docx.svg)
![pypi-downloads](https://img.shields.io/pypi/dm/pdf2docx)

- Extract data from PDF with `PyMuPDF`, e.g. text, images and drawings 
- Parse layout with rule, e.g. sections, paragraphs, images and tables
- Generate docx with `python-docx`

## Features

- [x] Parse and re-create page layout
    - [x] page margin
    - [x] section and column (1 or 2 columns only)
    - [ ] page header and footer

- [x] Parse and re-create paragraph
    - [x] text in horizontal/vertical direction: from left to right, from bottom to top
    - [x] font style, e.g. font name, size, weight, italic and color
    - [x] text format, e.g. highlight, underline, strike-through
    - [x] external hyper link
    - [x] paragraph horizontal alignment (left/right/center/justify) and vertical spacing
    - [ ] list style
    
- [x] Parse and re-create image
	- [x] in-line image
    - [x] image in Gray/RGB/CMYK mode
    - [x] transparent image
    - [x] floating image, i.e. picture behind text

- [x] Parse and re-create table
    - [x] border style, e.g. width, color
    - [x] shading style, i.e. background color
    - [x] merged cells
    - [x] vertical direction cell
    - [x] table with partly hidden borders
    - [x] nested tables

- [x] Parsing pages with multi-processing

*It can also be used as a tool to extract table contents since both table content and format/style is parsed.*

## Limitations

- Text-based PDF file
- Left to right language
- Normal reading direction, no word transformation / rotation
- Rule-based method can't 100% convert the PDF layout


## Documentation

- [Installation](https://dothinking.github.io/pdf2docx/installation.html)
- [Quickstart](https://dothinking.github.io/pdf2docx/quickstart.html)
    - [Convert PDF](https://dothinking.github.io/pdf2docx/quickstart.convert.html)
    - [Extract table](https://dothinking.github.io/pdf2docx/quickstart.table.html)
    - [Command Line Interface](https://dothinking.github.io/pdf2docx/quickstart.cli.html)
    - [Graphic User Interface](https://dothinking.github.io/pdf2docx/quickstart.gui.html)
- [Technical Documentation (In Chinese)](https://dothinking.github.io/pdf2docx/techdoc.html)
- [API Documentation](https://dothinking.github.io/pdf2docx/modules.html)

## Sample

![sample_compare.png](https://s1.ax1x.com/2020/08/04/aDryx1.png)