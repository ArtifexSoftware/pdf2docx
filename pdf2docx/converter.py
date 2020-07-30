# -*- coding: utf-8 -*-

import os
import fitz
from docx import Document

from .layout.Layout import Layout
from .common.base import PlotControl
from .common import utils


class Converter:
    ''' Read PDF file `pdf_file` with PyMuPDF to get raw layout data page by page, including text, 
        image and the associated properties, e.g. boundary box, font, size, image width, height, 
        then parse it with consideration for docx re-generation structure. Finally, generate docx
        with python-docx.
    '''

    def __init__(self, pdf_file:str, docx_file:str=None, debug:bool=False) -> None:
        ''' Initialize fitz object with given pdf file path; initialize docx object.

            If debug=True, illustration pdf will be created during parsing the raw pdf layout.
        '''
        # pdf/docx filename
        self.filename_pdf = pdf_file
        self.filename_docx = docx_file if docx_file else pdf_file.replace('.pdf', '.docx')
        if os.path.exists(self.filename_docx):
            os.remove(self.filename_docx)

        # fitz object to read pdf
        self._doc_pdf = fitz.open(pdf_file)

        # docx object to write file
        self._doc_docx = Document()

        # layout object: main worker
        self._layout = None # type: Layout

        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        self.debug_mode = debug
        path, filename = os.path.split(pdf_file)
        self.filename_debug = os.path.join(path, f'debug_{filename}')
        self._doc_debug = fitz.open() if debug else None

        # to serialize layout for debug purpose
        self._filename_debug_layout = os.path.join(path, 'layout.json')


    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.stop is None or index.stop > self._doc_pdf.pageCount:
                stop = self._doc_pdf.pageCount
            else:
                stop = index.stop
            res = [self._doc_pdf[i] for i in range(stop)]
            return res[index]
        else:
            return self._doc_pdf[index]

    def __len__(self):
        return len(self._doc_pdf)

    @property
    def layout(self):
        return self._layout

    @property
    def doc_pdf(self):
        return self._doc_pdf

    @property
    def doc_docx(self):
        return self._doc_docx

    @property
    def _debug_kwargs(self):
        return {
                'debug': self.debug_mode,
                'doc': self._doc_debug,
                'filename': self.filename_debug
            }

    def init(self, page:fitz.Page) -> Layout:
        '''Initialize layout object.'''
        # Layout object based on raw dict
        raw_layout = page.getText('rawdict')
        self._layout = Layout(raw_layout)
        
        # get rectangle shapes from page source:
        # these shapes are generally converted from docx, e.g. highlight, underline,
        # which are different from PDF comments like highlight, rectangle.
        for xref in page._getContents():            
            page_content = self._doc_pdf._getXrefStream(xref).decode(encoding="ISO-8859-1")
            self._layout.rects.from_stream(page_content, self._layout.height)
        
        # get annotations(comment shapes) from PDF page: consider highlight, underline, 
        # strike-through-line only.
        annots = page.annots()
        self._layout.rects.from_annotations(annots)

        # plot raw layout
        if self.debug_mode:
            # new section for current pdf page
            utils.new_page_section(self._doc_debug, self._layout.width, self._layout.height, f'Page {page.number}')

            # initial layout
            self._layout.plot(self._doc_debug, 'Original Text Blocks', key=PlotControl.LAYOUT)
            self._layout.plot(self._doc_debug, 'Original Rectangle Shapes', key=PlotControl.SHAPE)

        return self._layout


    def parse(self, page:fitz.Page):
        '''Parse page layout.'''
        # parse page: text/table/layout format
        self.init(page).parse(**self._debug_kwargs)

        # debug:
        # - save layout plotting as pdf file
        # - write layout information
        if self.debug_mode:
            self._doc_debug.save(self.filename_debug)
            self._layout.serialize(self._filename_debug_layout)

        return self


    def make_page(self):
        '''Create docx page based on parsed layout.'''
        self._layout.make_page(self._doc_docx)
        self.save_docx()


    def extract_tables(self, page:fitz.Page):
        '''Extract table contents.'''
        return self.init(page).extract_tables()


    def save_docx(self):
        '''Save docx file.'''        
        self._doc_docx.save(self.filename_docx)


    def close(self):
        '''Close pdf files.'''
        self._doc_pdf.close()
        if self.debug_mode:
            self._doc_debug.close()