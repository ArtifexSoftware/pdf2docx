# -*- coding: utf-8 -*-

import os
import fitz
from docx import Document

from .layout.Layout import Layout
from .common.base import PlotControl
from .common.pdf import new_page_section


class Converter:
    ''' Read PDF file `pdf_file` with PyMuPDF to get raw layout data page by page, including text, 
        image and the associated properties, e.g. bounding box, font, size, image width, height, 
        then parse it with consideration for docx re-generation structure. Finally, generate docx
        with python-docx.
    '''

    def __init__(self, pdf_file:str, docx_file:str=None, debug:bool=False):
        ''' Initialize fitz object with given pdf file path; initialize docx object.

            If debug=True, illustration pdf will be created during parsing the raw pdf layout.
        '''
        # pdf/docx filename
        self.filename_pdf = pdf_file
        self.filename_docx = docx_file if docx_file else pdf_file.replace('.pdf', '.docx')
        if os.path.exists(self.filename_docx): os.remove(self.filename_docx)

        # fitz object to read pdf
        self._doc_pdf = fitz.open(pdf_file)

        # docx object to write file
        self._doc_docx = Document()

        # layout object: main worker
        self._layout = None # type: Layout

        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(pdf_file)
        self._debug_kwargs = {
            'debug'   : debug,
            'doc'     : fitz.open() if debug else None,
            'filename': os.path.join(path, f'debug_{filename}'),
            'layout'  : os.path.join(path, 'layout.json')
        }


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
    def layout(self): return self._layout

    @property
    def doc_pdf(self): return self._doc_pdf

    @property
    def doc_docx(self): return self._doc_docx


    def make_page(self, page:fitz.Page):
        '''Parse pdf page and create docx page.'''
        # parse page: text/table/layout format
        self._init(page).parse(**self._debug_kwargs).make_page(self._doc_docx)

        # save files
        self.save_docx()
        self._debug_save()

        return self


    def extract_tables(self, page:fitz.Page):
        '''Extract table contents.'''
        return self._init(page).extract_tables()


    def make_docx(self, page_indexes:list):
        '''Parse and create a list of pages.
            ---
            Args:
            - page_indexes: list[int], page indexes to parse
        '''
        pass


    def save_docx(self):
        '''Save docx file.'''        
        self._doc_docx.save(self.filename_docx)


    def close(self):
        '''Close pdf files.'''
        self._doc_pdf.close()
        if self._debug_kwargs['debug']: self._debug_kwargs['doc'].close()


    def _init(self, page:fitz.Page):
        '''Initialize layout object.'''
        # Layout object based on raw dict
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout = page.getText('rawdict')

        # though 'width', 'height' are contained in `raw_dict`, they are based on un-rotated page.
        # so, update page width/height to right direction in case page is rotated
        *_, w, h = page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })
        self._layout = Layout(raw_layout, page.rotationMatrix)
        
        # get rectangle shapes from page source
        self._layout.rects.from_stream(self.doc_pdf, page)
        
        # get annotations(comment shapes) from PDF page, e.g. 
        # highlight, underline and strike-through-line        
        self._layout.rects.from_annotations(page)

        # plot raw layout
        self._plot_initial_layout(page.number)

        return self._layout


    def _make_docx(self, page_indexes:list):
        '''Parse and create a list of pages.
            ---
            Args:
            - page_indexes: list[int], page indexes to parse
        '''
        for i in page_indexes:
            pass

    def _make_docx_multi_processing(self):
        pass


    def _plot_initial_layout(self, page_number:int):
        '''Plot initial layout.'''
        if not self._debug_kwargs['debug']: return

        doc = self._debug_kwargs['doc']

        # new section for current pdf page
        new_page_section(doc, self._layout.width, self._layout.height, f'Page {page_number}')

        # initial layout
        self._layout.plot(doc, 'Original Text Blocks', key=PlotControl.LAYOUT)
        self._layout.plot(doc, 'Original Rectangle Shapes', key=PlotControl.SHAPE)


    def _debug_save(self):
        if not self._debug_kwargs['debug']: return
        # save layout plotting as pdf file
        self._debug_kwargs['doc'].save(self._debug_kwargs['filename'])
        # write layout information
        self._layout.serialize(self._debug_kwargs['layout'])




