# pdf2docx 

![pdf2docx-test](https://github.com/dothinking/pdf2docx/workflows/pdf2docx-test/badge.svg)
[![codecov](https://codecov.io/gh/dothinking/pdf2docx/branch/master/graph/badge.svg)](https://codecov.io/gh/dothinking/pdf2docx)
![pdf2docx-publish](https://github.com/dothinking/pdf2docx/workflows/pdf2docx-publish/badge.svg)
![GitHub](https://img.shields.io/github/license/dothinking/pdf2docx)

- Parse layout (text, image and table) from PDF file with `PyMuPDF`
- Generate docx with `python-docx`

## Features

- [x] Parse and re-create paragraph
    - [x] text in horizontal/vertical direction: from left to right, from bottom to top
    - [x] font style, e.g. font name, size, weight, italic and color
    - [x] text format, e.g. highlight, underline, strike-through
    - [x] text alignment, e.g. left/right/center/justify
    - [x] external hyper link
    - [x] paragraph layout: horizontal alignment and vertical spacing
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

- Text-based PDF file only
- Normal reading direction only
    - horizontal/vertical paragraph/line/word
    - no word transformation, e.g. rotation


## Documentation

- [Installation](https://dothinking.github.io/pdf2docx/installation.html)
- [Quickstart](https://dothinking.github.io/pdf2docx/quickstart.html)
    - [Convert PDF](https://dothinking.github.io/pdf2docx/quickstart.convert.html)
    - [Extract table content](https://dothinking.github.io/pdf2docx/quickstart.table.html)
    - [Command Line Interface](https://dothinking.github.io/pdf2docx/quickstart.cli.html)
- [API Documentation](https://dothinking.github.io/pdf2docx/modules.html)

## Sample

![sample_compare.png](https://s1.ax1x.com/2020/08/04/aDryx1.png)