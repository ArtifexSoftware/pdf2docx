# pdf2docx

- read PDF file with PyMuPDF
- parse text/image and format
- generate docx with python-docx

```python
import os
from pdf2docx import Reader, Writer


output_dir = 'demo/path'
pdf_file = os.path.join(output_dir, 'demo.pdf')
docx_file = os.path.join(output_dir, 'demo.docx')

pdf = Reader(pdf_file)
docx = Writer()

for page in pdf[0:5]:
	layout = pdf.parse(page)
	docx.make_page(layout)

docx.save(docx_file)
```
