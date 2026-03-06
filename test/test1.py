import os
import sys

# Use the pdf2docx module from this repo instead of the installed package
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from pdf2docx import Converter

source_pdf_file = f'E:/Pdf2Docx/Issues/369/test.pdf'
docx_file = f'E:/Pdf2Docx/Issues/369/test.docx'
c = Converter(source_pdf_file)
c.convert(docx_file)
c.close()


print(f'Conversion complete: {docx_file}')