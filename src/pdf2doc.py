import os
from docx import Document
import fitz

from .processor import pdf as PDFProcessor
from .processor import docx as DOCXProcessor


class Reader:
    '''
        read PDF file `file_path` with PyMuPDF to get the layout data, including text, image and 
        the associated properties, e.g. boundary box, font, size, image width, height, then parse
        it with consideration for sentence completeness, DOCX generation structure.
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

    def rects(self, page):
        '''get shape, especially rectangle from page source
        '''
        res = []
        for xref in page._getContents():
            page_content = self._doc._getXrefStream(xref).decode()
            print(page_content)
            res.extend(PDFProcessor.rectangles(page_content))
        return res

    def annots(self, page):
        annot = page.firstAnnot

        print(len(list(page.annots())))

        while annot:
            if annot.type[0] in (8, 9, 10, 11): # one of the 4 types above
                rect = annot.rect # this is the rectangle the annot covers
                # extract the text within that rect ...
                print(annot.rect)
            annot = annot.next # None returned after last annot
        else:
            print('nothing found')


    def parse(self, page, debug=False, filename=None):
        ''' parse page layout

            args:
                page: current page
                debug: plot layout for illustration if True            
                filename: pdf filename for the plotted layout
        '''
        if debug and not filename:
            raise Exception('Please specify `filename` for layout plotting when debug=True.')

        # layout plotting args
        doc = fitz.open() if debug else None
        kwargs = {
            'debug': debug,
            'doc': doc,
            'filename': filename
        }

        # page source
        layout = page.getText('dict')
        words = page.getTextWords()
        rects = self.rects(page)

        # raw layout, rectangles
        if debug:
            PDFProcessor.plot_layout(doc, layout, 'Original PDF')
            PDFProcessor.plot_rectangles(doc, layout, rects, 'Recognized Rectangles')

        # parse page
        PDFProcessor.layout(layout, words, rects, **kwargs)

        # save layout plotting as pdf file
        if debug:
            doc.save(filename)
            doc.close()

        return layout


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