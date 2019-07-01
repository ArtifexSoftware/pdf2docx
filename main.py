import os
from docx import Document
import PDFProcessor
import DOCXMaker


# output = 'D:/11_Translation_Web/pdf2word'
output = 'D:/WorkSpace/TestSpace/PDFTranslation/src/res'
pdf_file = os.path.join(output, 'case.pdf')
docx_file = os.path.join(output, 'demo.docx')

pdf = PDFProcessor.Reader(pdf_file)
docx = Document()

for page in pdf[7:15]:
	raw = pdf.layout(page)
	layout = PDFProcessor.layout(raw)
	DOCXMaker.make_page(docx, layout)

# save file
if os.path.exists(docx_file):
    os.remove(docx_file)
docx.save(docx_file)
