.. include:: header.rst

Extract table
======================

::

    from pdf2docx import Converter

    pdf_file = '/path/to/sample.pdf'

    cv = Converter(pdf_file)
    tables = cv.extract_tables(start=0, end=1)
    cv.close()

    for table in tables:
        print(table)

The output may look like::

    ...
    [['Input ', None, None, None, None, None], 
    ['Description A ', 'mm ', '30.34 ', '35.30 ', '19.30 ', '80.21 '],
    ['Description B ', '1.00 ', '5.95 ', '6.16 ', '16.48 ', '48.81 '],
    ['Description C ', '1.00 ', '0.98 ', '0.94 ', '1.03 ', '0.32 '],
    ['Description D ', 'kg ', '0.84 ', '0.53 ', '0.52 ', '0.33 '],
    ['Description E ', '1.00 ', '0.15 ', None, None, None],
    ['Description F ', '1.00 ', '0.86 ', '0.37 ', '0.78 ', '0.01 ']]


.. include:: footer.rst
