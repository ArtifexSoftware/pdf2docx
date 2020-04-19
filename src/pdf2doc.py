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
        ''' Get rectangle shapes from page source and comment annotations.            
            return a list of rectangles:
                [{
                    "bbox": (x0, y0, x1, y1),
                    "color": sRGB,
                    'type': None
                    },
                    {...}
                ]
        '''
        res = []

        # use page height to convert the default origin from bottom left (PDF)
        # to top right (PyMuPDF)
        height = page.MediaBox.y1

        # get rectangle shapes from page source:
        # these shapes are generally converted from docx, e.g. highlight, underline,
        # which are different from PDF comments like highlight, rectangle.
        for xref in page._getContents():
            page_content = self._doc._getXrefStream(xref).decode()
            rects = PDFProcessor.rects_from_source(page_content, height)
            res.extend(rects)
        
        # get annotations(comment shapes) from PDF page: consider highlight, underline, 
        # strike-through-line only.
        annots = page.annots()
        rects = PDFProcessor.rects_from_annots(annots)
        res.extend(rects)

        return res

    
    def layout(self, page):
        ''' raw dict of PDF page retrieved with PyMuPDF, and with rectangles included.
        '''
        # raw layout
        layout = page.getText('rawdict')

        # rectangles
        rects = self.rects(page)

        # append rectangles to raw dict
        layout['rects'] = rects

        return layout


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
        layout = self.layout(page)

        # raw layout, rectangles
        if debug:
            PDFProcessor.plot_layout(doc, layout, 'Original PDF')
            PDFProcessor.plot_rectangles(doc, layout, 'Recognized Rectangles')

        # parse page
        PDFProcessor.layout(layout, **kwargs)

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