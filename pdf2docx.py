import os
from docx import Document
import fitz

import PDFProcessor
import DOCXProcessor


class Reader:
    '''
        read PDF file `file_path` with PyMuPDF to get the layout data, including text, image and 
        the associated properties, e.g. boundary box, font, size, image width, height, then parse
        it with consideration for sentence completence, DOCX generation structure.
    '''

    def __init__(self, file_path):
        self._doc = fitz.open(file_path)

    def __getitem__(self, index):
        if isinstance(index, slice):
            stop = index.stop if not index.stop is None else self._doc.pageCount
            res = [self._doc[i] for i in range(stop)]
            return res[index]
        else:
            return self._doc[index]

    @staticmethod
    def layout(page):
        '''raw layout of PDF page'''
        layout = page.getText('dict')
        # reading order: from top to bottom, from left to right
        layout['blocks'].sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
        return layout

    @staticmethod
    def parse(page, debug=False):
        '''precessed layout'''
        raw = Reader.layout(page)
        if debug:
        	return PDFProcessor.layout_debug(raw)
        else:
        	return PDFProcessor.layout(raw)


class Writer:
    '''
        generate .docx file with python-docx based on page layout data.
    '''

    def __init__(self):
        self._doc = Document()

    def make_page(self, layout):
        '''generate page'''
        DOCXProcessor.make_page(self._doc, layout)

    def save(self, filename='res.docx'):
        '''save docx file'''
        if os.path.exists(filename):
            os.remove(filename)
        self._doc.save(filename)



if __name__ == '__main__':

	output = 'D:/11_Translation_Web/pdf2word'
	# output = 'D:/WorkSpace/TestSpace/PDFTranslation/src/res'
	pdf_file = os.path.join(output, 'case.pdf')
	docx_file = os.path.join(output, 'demo.docx')

	pdf = Reader(pdf_file)
	docx = Writer()

	for page in pdf[7:]:
		layout = pdf.parse(page)
		docx.make_page(layout)

	docx.save(docx_file)
