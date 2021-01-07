Convert PDF
=======================

We can use either the ``Converter`` class or a wrapped method ``parse()``.

* Converter class

::

  from pdf2docx import Converter

  pdf_file = '/path/to/sample.pdf'
  docx_file = 'path/to/sample.docx'

  # convert pdf to docx
  cv = Converter(pdf_file)
  cv.convert(docx_file, start=0, end=None)
  cv.close()



* parse() method

::

  from pdf2docx import parse

  pdf_file = '/path/to/sample.pdf'
  docx_file = 'path/to/sample.docx'

  # convert pdf to docx
  parse(pdf_file, docx_file, start=0, end=None)
