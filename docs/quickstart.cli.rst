.. include:: header.rst

Command Line Interface
===========================

::

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


By range of pages
-----------------------

Specify pages range by ``--start`` (from the first page if omitted) and 
``--end`` (to the last page if omitted). 

.. note:: 
  The page index is zero-based by default, but can turn it off by 
  ``--zero_based_index=False``, i.e. the first page index starts from 1.

Convert all pages::

  $ pdf2docx convert test.pdf test.docx

Convert pages from the second to the end::

  $ pdf2docx convert test.pdf test.docx --start=1


Convert pages from the first to the third (index=2)::

  $ pdf2docx convert test.pdf test.docx --end=3


Convert second and third pages::

  $ pdf2docx convert test.pdf test.docx --start=1 --end=3

Convert the first and second pages with zero-based index turn off::

  $ pdf2docx convert test.pdf test.docx --start=1 --end=3 --zero_based_index=False



By page numbers
-----------------------

Convert the first, third and 5th pages::

  $ pdf2docx convert test.pdf test.docx --pages=0,2,4


Multi-Processing
--------------------------

Turn on multi-processing with default count of CPU::

  $ pdf2docx convert test.pdf test.docx --multi_processing=True

Specify the count of CPUs::

  $ pdf2docx convert test.pdf test.docx --multi_processing=True --cpu_count=4

.. include:: footer.rst
