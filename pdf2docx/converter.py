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


    def close(self): self._doc_pdf.close()


    @staticmethod
    def parse(page:fitz.Page, config:dict=None):
        ''' Parse one specified pdf `page` and return a Layout object.'''        
        return Layout(page, config).parse()


    def debug_page(self, i:int, docx_filename:str=None, debug_pdf=None, layout_file=None, config:dict=None):
        ''' Parse, create and plot single page for debug purpose.
            ---
            Args:
            - i (int): page index to convert
            - docx_filename (str): DOCX filename to write to
            - debug_pdf (str): new pdf file storing layout information (add prefix "debug_" by default)
            - layout_file (str): new json file storing parsed layout data (layout.json by default)
        '''
        config = config if config else {}

        # include debug information
        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(self.filename_pdf)
        if not debug_pdf: debug_pdf = os.path.join(path, f'debug_{filename}')
        if not layout_file: layout_file  = os.path.join(path, 'layout.json')
        config.update({
            'debug'         : True,
            'debug_doc'     : fitz.Document(),
            'debug_filename': debug_pdf
        })

        # parse and make page
        layouts = self.make_docx(docx_filename, pages=[i], config=config)
        
        # layout information for debugging
        layouts[0].serialize(layout_file) 

        return layouts[0]


    def make_docx(self, docx_filename=None, start=0, end=None, pages=None, config:dict=None):
        ''' Convert specified PDF pages to DOCX file.
            docx_filename : DOCX filename to write to
            start         : first page to process, starting from zero if --zero_based_index=True
            end           : last page to process, starting from zero if --zero_based_index=True
            pages         : range of pages
            config        : configuration parameters
        '''
        config = config if config else {}
        
        # DOCX file to convert to
        docx_file = Document() 
        filename = docx_filename if docx_filename else self.filename_pdf.replace('.pdf', '.docx')
        if os.path.exists(filename): os.remove(filename)

        # PDF pages to convert
        zero_based = config.get('zero_based_index', True)
        page_indexes = self._page_indexes(start, end, pages, len(self), zero_based)
        
        # convert page by page
        t0 = perf_counter()        
        if config.get('multi_processing', False):
            layouts = self._make_docx_multi_processing(docx_file, page_indexes, config)
        else:
            layouts = self._make_docx(docx_file, page_indexes, config)       
        print(f'\n{"-"*50}\nTerminated in {perf_counter()-t0}s.')

        # save docx
        docx_file.save(filename)

        return layouts


    def extract_tables(self, start=0, end=None, pages=None, config:dict=None):
        '''Extract table contents from specified PDF pages.'''
        # PDF pages to convert
        config = config if config else {}
        zero_based = config.get('zero_based_index', True)
        page_indexes = self._page_indexes(start, end, pages, len(self), zero_based)

        # process page by page
        tables = []
        num_pages = len(page_indexes)        
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...')
            page_tables = self.parse(self.doc_pdf[i], config).extract_tables()
            tables.extend(page_tables)

        return tables


    def _make_docx(self, docx_file:Document, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - docx_file   : docx.Document, docx file write to
            - page_indexes: list[int], page indexes to parse
        '''
        layouts = []
        num_pages = len(page_indexes)
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...', end='', flush=True)
            layout = self.parse(self.doc_pdf[i], config)            
            layout.make_page(docx_file) # write to docx
            layouts.append(layout)
        
        return layouts


    def _make_docx_multi_processing(self, docx_file:Document, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - docx_file   : docx.Document, docx file write to
            - page_indexes: list[int], page indexes to parse

            https://pymupdf.readthedocs.io/en/latest/faq.html#multiprocessing
        '''
        # make vectors of arguments for the processes
        cpu = min(config['cpu_count'], cpu_count()) if 'cpu_count' in config else cpu_count()
        start, end = min(page_indexes), max(page_indexes)
        prefix_layout = 'layout'
        vectors = [(i, cpu, start, end, self.filename_pdf, config, f'{prefix_layout}-{i}.json') for i in range(cpu)]

        # start parsing processes
        pool = Pool()
        pool.map(self._make_docx_per_cpu, vectors, 1)
        
        # read parsed layout data
        raw_layouts = {}
        for i in range(cpu):
            filename = f'{prefix_layout}-{i}.json'
            if not os.path.exists(filename): continue            
            with open(filename, 'r') as f:
                raw_layouts.update(json.load(f))
            os.remove(filename)
        
        # restore layouts and create docx pages
        print()
        num_pages = len(page_indexes)
        layouts = []
        for page_index in page_indexes:
            key = str(page_index)
            if key not in raw_layouts: continue

            print(f'\rCreating Pages: {page_index+1}/{num_pages}...', end='')
            layout = Layout()
            layout.restore(raw_layouts[key]).make_page(docx_file)
            layouts.append(layout)
        
        return layouts


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
                - 5  : configuration parameters
                - 6  : json filename storing parsed results
        '''
        # recreate the arguments
        idx, cpu, s, e, pdf_filename, config, json_filename = vector

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

            # store page parsed results
            page = cv.doc_pdf[page_index]            
            res[page_index] = cv.parse(page, config).store()

        # serialize results
        with open(json_filename, 'w') as f:
            f.write(json.dumps(res))


    @staticmethod
    def _page_indexes(start, end, pages, pdf_len, zero_based=True):
        # index starts from zero or one
        if not zero_based:
            start = max(start-1, 0)
            if end: end -= 1
            if pages: pages = [i-1 for i in pages]

        # parsing arguments
        if pages: 
            indexes = [int(x) for x in pages if 0<=x<pdf_len]
        else:
            end = end or pdf_len
            s = slice(int(start), int(end))
            indexes = range(pdf_len)[s]
        
        return indexes
