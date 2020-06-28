import os
from docx import Document
import fitz

from . import pdf
from . import pdf_shape
from . import pdf_debug


class Reader:
    ''' Read PDF file `file_path` with PyMuPDF to get the raw layout data, including text, image and 
        the associated properties, e.g. boundary box, font, size, image width, height, then parse
        it with consideration for docx re-generation structure.
    '''

    def __init__(self, file_path, debug=False):
        ''' Initialize fitz object with given pdf file path.
            If debug=True, illustration pdf will be created during parsing the raw pdf layout.
        '''
        self.debug_mode = debug
        self.filename = file_path

        # main fitz object to read pdf
        self._doc = fitz.open(file_path)

        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(file_path)
        self._debug_doc_path = os.path.join(path, f'debug_{filename}')
        self._debug_doc = fitz.open() if debug else None


    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.stop is None or index.stop > self._doc.pageCount:
                stop = self._doc.pageCount
            else:
                stop = index.stop
            res = [self._doc[i] for i in range(stop)]
            return res[index]
        else:
            return self._doc[index]


    def __len__(self):
        return len(self._doc)


    @property
    def core(self):
        return self._doc


    @property
    def debug_kwargs(self):        
        return {
                'debug': self.debug_mode,
                'doc': self._debug_doc,
                'filename': self._debug_doc_path
            }


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
            page_content = self._doc._getXrefStream(xref).decode(encoding="ISO-8859-1")
            rects = pdf_shape.rects_from_source(page_content, height)
            res.extend(rects)
        
        # get annotations(comment shapes) from PDF page: consider highlight, underline, 
        # strike-through-line only.
        annots = page.annots()
        rects = pdf_shape.rects_from_annots(annots)
        res.extend(rects)

        return res

    
    def layout(self, page):
        ''' raw dict of PDF page retrieved with PyMuPDF, and with rectangles included.
        '''
        # raw layout
        layout = page.getText('rawdict')

        # calculate page margin
        layout['margin'] = pdf.page_margin(layout)

        # rectangles: appended to raw layout
        layout['rects'] = self.rects(page)

        # plot raw layout
        if self.debug_mode:
            # new section for current pdf page
            pdf_debug.new_page_section(self._debug_doc, layout, f'Page {page.number}')

            # initial layout            
            pdf_debug.plot_layout(self._debug_doc, layout, 'Original Text Blocks')
            pdf_debug.plot_rectangles(self._debug_doc, layout, 'Original Rectangle Shapes')

        return layout


    def parse(self, page):
        ''' parse page layout

            args:
                page: current page
                debug: plot layout for illustration if True            
                filename: pdf filename for the plotted layout
        '''
        # page source
        layout = self.layout(page)        

        # parse page
        pdf.layout(layout, **self.debug_kwargs)

        # save layout plotting as pdf file
        self.save_debug_doc()

        return layout

    
    def save_debug_doc(self):
        if self.debug_mode:
            self._debug_doc.save(self._debug_doc_path)
    
    def close(self):
        self._doc.close()
        if self.debug_mode:
            self._debug_doc.close()