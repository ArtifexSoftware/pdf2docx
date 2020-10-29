# -*- coding: utf-8 -*-

import os
import json
from time import perf_counter
from multiprocessing import Pool, cpu_count
import fitz
from docx import Document
from .layout.Layout import Layout


class Converter:
    ''' Read PDF file `pdf_file` with PyMuPDF to get raw layout data page by page, including text, 
        image and the associated properties, e.g. bounding box, font, size, image width, height, 
        then parse it with consideration for docx re-generation structure. Finally, generate docx
        with python-docx.
    '''

    def __init__(self, pdf_file:str):
        ''' Initialize fitz object with given pdf file path; initialize docx object.'''
        # pdf/docx filename
        self.filename_pdf = pdf_file        

        # fitz object to read pdf
        self._doc_pdf = fitz.Document(pdf_file)


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


    def __len__(self): return len(self._doc_pdf)


    @property
    def doc_pdf(self): return self._doc_pdf

    # @property
    # def doc_docx(self): return self._doc_docx


    def make_page(self, 
            page:fitz.Page, 
            docx_file:Document,
            docx_filename:str=None,
            config:dict=None):
        ''' Parse pdf `page` and write to `docx_file` with name `docx_filename`. 
            If `docx_filename`=None, a same filename with source pdf file is used.
            Return a Layout object.
        '''
        # Layout blocks with image blocks updated
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout = page.getText('rawdict')

        # page size: though 'width', 'height' are contained in `raw_dict`, 
        # they are based on un-rotated page. So, update page width/height 
        # to right direction in case page is rotated
        *_, w, h = page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })

        # init page layout
        layout = Layout(raw_layout, page, config)

        # parse page layout
        layout.parse()
        
        # check docx filename
        filename = docx_filename if docx_filename else self.filename_pdf.replace('.pdf', '.docx')
        if os.path.exists(filename): os.remove(filename)

        # write and save docx
        layout.make_page(docx_file)
        docx_file.save(filename)

        return layout


    def close(self): self._doc_pdf.close()


    def debug_page(self, page:fitz.Page, docx_filename:str=None, config:dict=None):
        ''' Parse, create and plot single page for debug purpose.
            Illustration pdf will be created during parsing the raw pdf layout.
        '''
        config = config if config else {}

        # include debug information
        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(self.filename_pdf)
        filename_json  = os.path.join(path, 'layout.json')
        debug_doc = fitz.Document()
        config.update({
            'debug'   : True,
            'doc'     : debug_doc,
            'filename': os.path.join(path, f'debug_{filename}')
        })

        # convert page
        docx_file = Document() # docx file to write
        layout = self.make_page(page, docx_file, docx_filename, config)
        
        # layout information for debugging
        layout.serialize(filename_json) 

        return layout


    def make_docx(self, page_indexes:list, docx_filename:str=None, config:dict=None):
        '''Parse and create a list of pages.
            ---
            Args:
            - page_indexes    : list[int], page indexes to parse
            - multi_processing: bool, multi-processing mode if True
        '''
        # docx file to write
        docx_file = Document()

        t0 = perf_counter()
        config = config if config else {}
        if config.get('multi_processing', False):
            self._make_docx_multi_processing(docx_file, page_indexes, config)
        else:
            self._make_docx(docx_file, page_indexes, config)
        
        print(f'\n{"-"*50}\nTerminated in {perf_counter()-t0}s.')


    def extract_tables(self, page_indexes:list, config:dict=None):
        '''Extract table contents.'''
        tables = []
        num_pages = len(page_indexes)
        # process page by page
        config = config if config else {}
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...')
            page = self.doc_pdf[i]
            page_tables = self.parse_page(page, config).extract_tables()
            tables.extend(page_tables)

        return tables


    def _make_docx(self, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - page_indexes: list[int], page indexes to parse
        '''
        num_pages = len(page_indexes)
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...', end='', flush=True)

            # parse page
            page = self.doc_pdf[i]
            layout = self.parse_page(page, config)

            # write and save page
            self.write_page(layout, docx_file, filename)
            

        self.save()


    def _make_docx_multi_processing(self, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - page_indexes: list[int], page indexes to parse

            https://pymupdf.readthedocs.io/en/latest/faq.html#multiprocessing
        '''
        # make vectors of arguments for the processes
        cpu = cpu_count()
        start, end = min(page_indexes), max(page_indexes)
        prefix_layout = 'layout'
        vectors = [(i, cpu, start, end, self.filename_pdf, f'{prefix_layout}-{i}.json', config) for i in range(cpu)]

        # start parsing processes
        pool = Pool()
        pool.map(self._make_docx_per_cpu, vectors, 1)
        
        # restore layouts
        raw_layouts = {}
        for i in range(cpu):
            filename = f'{prefix_layout}-{i}.json'
            if not os.path.exists(filename): continue

            # read parsed layouts
            with open(filename, 'r') as f:
                raw_layouts.update(json.load(f))

            os.remove(filename)
        
        # create docx pages
        print()
        num_pages = len(page_indexes)
        for page_index in page_indexes:
            key = str(page_index)
            if key not in raw_layouts: continue

            print(f'\rCreating Pages: {page_index+1}/{num_pages}...', end='')
            raw_layout = raw_layouts[key]
            Layout(raw_layout).make_page(self.doc_docx)

        self.save()


    @staticmethod
    def _make_docx_per_cpu(vector):
        ''' Render a page range of a document.
            ---
            Args:
            - vector: a list containing required parameters.
                - 0  : segment number for current process                
                - 1  : count of CPUs
                - 2,3: whole pages range to process since sometimes need only parts of pdf pages                
                - 4  : pdf filename
                - 5  : json filename storing parsed results
        '''
        # recreate the arguments
        idx, cpu, s, e, pdf_filename, json_filename, config = vector

        # worker
        cv = Converter(pdf_filename)

        # all pages to process
        pages_indexes = range(s, e+1)
        num_pages = len(pages_indexes)

        # pages per segment
        seg_size = int(num_pages/cpu) + 1
        seg_from = idx * seg_size
        seg_to = min(seg_from + seg_size, num_pages)

        res = {}
        for i in range(seg_from, seg_to):  # work through our page segment
            page_index = pages_indexes[i]
            print(f'\rParsing Pages: {page_index+1}/{num_pages} per CPU {idx}...', end='', flush=True)

            # parse page
            page = cv.doc_pdf[page_index]
            cv.initialize(page, config).parse()

            # page results
            res[page_index] = cv.layout.store()

        # serialize results
        with open(json_filename, 'w') as f:
            f.write(json.dumps(res))
