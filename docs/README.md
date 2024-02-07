# pdf2docx documentation

Welcome to the **pdf2docx** documentation. This documentation relies on [Sphinx](https://www.sphinx-doc.org/en/master/) to publish HTML docs from markdown files written with [restructured text](https://en.wikipedia.org/wiki/ReStructuredText) (RST).


## Sphinx version

This README assumes you have [Sphinx v5.0.2 installed](https://www.sphinx-doc.org/en/master/usage/installation.html) on your system.


## Updating the documentation

Within `docs` update the associated restructured text (`.rst`) files. These files represent the corresponding document pages. 


## Building HTML documentation

- Ensure you have the `furo` theme installed:

`pip install furo`

Furo theme, Copyright (c) 2020 Pradyun Gedam <mail@pradyunsg.me>, thank you to:

https://github.com/pradyunsg/furo/blob/main/LICENSE

- From the "docs" location run:

`sphinx-build -b html . build/html`

This then creates the HTML documentation within `build/html`. 

> Use: `sphinx-build -a -b html . build/html` to build all, including the assets in `_static` (important if you have updated CSS).

For full details see: [Using Sphinx](https://www.sphinx-doc.org/en/master/usage/index.html)
