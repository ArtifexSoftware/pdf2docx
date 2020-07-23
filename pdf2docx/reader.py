from Github.pdf2docx.pdf2docx.common import utils
import os
import fitz

from .layout.Layout import Layout


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

        # to serialize layout for debug purpose
        self._debug_layout_file = os.path.join(path, 'layout.json')


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

    
    def parse(self, page):
        '''Parse page layout.'''
        # -----------------------------------------------------
        # Layout object based on raw dict
        # -----------------------------------------------------
        raw_layout = page.getText('rawdict')
        L = Layout(raw_layout)
        
        # get rectangle shapes from page source:
        # these shapes are generally converted from docx, e.g. highlight, underline,
        # which are different from PDF comments like highlight, rectangle.
        for xref in page._getContents():            
            page_content = self._doc._getXrefStream(xref).decode(encoding="ISO-8859-1")
            L.rects.from_stream(page_content, L.height)
        
        # get annotations(comment shapes) from PDF page: consider highlight, underline, 
        # strike-through-line only.
        annots = page.annots()
        L.rects.from_annotations(annots)
        
        # plot raw layout
        if self.debug_mode:
            # new section for current pdf page
            utils.new_page_section(self._debug_doc, L.width, L.height, f'Page {page.number}')

            # initial layout
            L.plot(self._debug_doc, 'Original Text Blocks', key='layout')
            L.plot(self._debug_doc, 'Original Rectangle Shapes', key='shape')

        # -----------------------------------------------------
        # parse page: text/table/layout format
        # -----------------------------------------------------
        L.parse(**self.debug_kwargs)

        # -----------------------------------------------------
        # debug:
        # - save layout plotting as pdf file
        # - write layout information
        # -----------------------------------------------------
        if self.debug_mode:
            self._debug_doc.save(self._debug_doc_path)
            L.serialize(self._debug_layout_file)

        return L


    def extract_tables(self, page):
        ''' Extract table contents.
        '''
        # page source
        layout = self.layout(page)

        # extract tables
        tables = pdf.extract_tables(layout)

        return tables

    
    def close(self):
        self._doc.close()
        if self.debug_mode:
            self._debug_doc.close()