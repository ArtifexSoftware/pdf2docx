Convert PDF
=======================

We can use either the :py:class:`~pdf2docx.converter.Converter` class 
or a wrapped method :py:meth:`~pdf2docx.main.parse`. 


* Option 1

::

  from pdf2docx import Converter

  pdf_file = '/path/to/sample.pdf'
  docx_file = 'path/to/sample.docx'

  # convert pdf to docx
  cv = Converter(pdf_file)
  cv.convert(docx_file, start=0, end=None)
  cv.close()



* Option 2

::

  from pdf2docx import parse

  pdf_file = '/path/to/sample.pdf'
  docx_file = 'path/to/sample.docx'

  # convert pdf to docx
  parse(pdf_file, docx_file, start=0, end=None)


.. note::
  Refer to :py:meth:`~pdf2docx.converter.Converter.convert` for detailed description on above arguments.