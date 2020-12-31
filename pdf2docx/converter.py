# -*- coding: utf-8 -*-

import os
import json
from time import perf_counter
from multiprocessing import Pool, cpu_count
import fitz
from docx import Document
from .page.Page import Page


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
        self._fitz_doc = fitz.Document(pdf_file)

        # initialize pages
        self._pages = [Page(fitz_page) for fitz_page in self._fitz_doc]


    def __getitem__(self, index):
        num = self._fitz_doc.pageCount
        if isinstance(index, slice):
            if index.stop is None or index.stop > num:
                stop = num
            else:
                stop = index.stop
            pages = [self._pages[i] for i in range(stop)]
            return pages[index]
        else:
            try:
                page = self._pages[index]
            except IndexError:
                msg = f'Page index {index} out of range'
                raise IndexError(msg)
            else:
                return page


    def __len__(self): return len(self._pages)


    @property
    def fitz_doc(self): return self._fitz_doc


    def close(self): self._fitz_doc.close()

    
    def parse(self, page_indexes=None, config:dict=None):
        '''Parse pages in specified page_indexes.'''
        indexes = page_indexes if page_indexes else range(len(self._pages))
        num_pages = len(indexes)
        for i, idx in enumerate(indexes, start=1):
            print(f'\rParsing Page {idx+1}: {i}/{num_pages}...', end='', flush=True)
            try:
                self._pages[idx].parse(config)
            except Exception as e:
                print(f'\nIgnore page due to error: {e}', flush=True)

        return self


    def make_docx(self, docx_filename=None):
        '''Create docx file with converted pages. Note to run page parsing first.'''
        # check parsed pages
        parsed_pages = list(filter(
            lambda page: page.finalized, self._pages
        ))
        if not parsed_pages:
            raise Exception('No parsed pages. Please parse page first.')

        # docx file to convert to        
        filename = docx_filename if docx_filename else self.filename_pdf.replace('.pdf', '.docx')
        if os.path.exists(filename): os.remove(filename)

        # create page by page
        docx_file = Document() 
        num_pages = len(parsed_pages)
        print()
        for i, page in enumerate(parsed_pages, start=1):
            if not page.finalized: continue # ignore unparsed pages
            print(f'\rCreating Page {page.id+1}: {i}/{num_pages}...', end='')
            try:
                page.make_docx(docx_file)
            except Exception as e:
                print(f'Ignore page due to error: {e}', flush=True)

        # save docx
        docx_file.save(filename)


    def store(self):
        '''Store parsed pages in dict format.'''
        return {
            'filename': os.path.basename(self.filename_pdf),
            'page_num': len(self._pages), # count of all pages
            'pages'   : [page.store() for page in self._pages if page.finalized], # parsed pages only
        }


    def restore(self, data:dict):
        '''Restore pages from parsed results.'''
        for raw_page in data.get('pages', []):
            idx = raw_page.get('id', -1)
            self._pages[idx].restore(raw_page)


    def serialize(self, filename:str):
        '''Write parsed pages to specified JSON file.'''
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(self.store(), indent=4))
    

    def deserialize(self, filename:str):
        '''Load parsed pages from specified JSON file.'''
        with open(filename, 'r') as f:
            data = json.load(f)
        self.restore(data)


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

        # parse and create docx
        self.convert(docx_filename, pages=[i], config=config)
        
        # layout information for debugging
        self.serialize(layout_file)


    def convert(self, docx_filename=None, start=0, end=None, pages=None, config:dict=None):
        ''' Convert specified PDF pages to DOCX file.
            docx_filename : DOCX filename to write to
            start         : first page to process
            end           : last page to process
            pages         : range of pages
            config        : configuration parameters
        '''
        config = config if config else {}
        
        # pages to convert
        page_indexes = self._page_indexes(start, end, pages, len(self))
        
        # convert page by page
        t0 = perf_counter()        
        if config.get('multi_processing', False):
            self._parse_and_create_pages_with_multi_processing(docx_filename, page_indexes, config)
        else:
            self._parse_and_create_pages(docx_filename, page_indexes, config)       
        print(f'\n{"-"*50}\nTerminated in {perf_counter()-t0}s.')        


    def extract_tables(self, start=0, end=None, pages=None, config:dict=None):
        '''Extract table contents from specified PDF pages.'''
        # PDF pages to convert
        config = config if config else {}
        page_indexes = self._page_indexes(start, end, pages, len(self))

        # process page by page
        self.parse(page_indexes, config)

        # get parsed tables
        tables = []
        for page in self._pages:
            if page.finalized: tables.extend(page.extract_tables())
        return tables


    def _parse_and_create_pages(self, docx_filename:str, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - docx_filename: DOCX filename to write to
            - page_indexes : list[int], page indexes to parse
        '''
        self.parse(page_indexes=page_indexes, config=config).make_docx(docx_filename)


    def _parse_and_create_pages_with_multi_processing(self, docx_filename:str, page_indexes:list, config:dict):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - docx_filename: DOCX filename to write to
            - page_indexes : list[int], page indexes to parse

            https://pymupdf.readthedocs.io/en/latest/faq.html#multiprocessing
        '''
        # make vectors of arguments for the processes
        cpu = min(config['cpu_count'], cpu_count()) if 'cpu_count' in config else cpu_count()
        start, end = min(page_indexes), max(page_indexes)
        prefix = 'pages' # json file writing parsed pages per process
        vectors = [(i, cpu, start, end, self.filename_pdf, config, f'{prefix}-{i}.json') for i in range(cpu)]

        # start parsing processes
        pool = Pool()
        pool.map(self._parse_pages_per_cpu, vectors, 1)
        
        # restore parsed page data
        for i in range(cpu):
            filename = f'{prefix}-{i}.json'
            if not os.path.exists(filename): continue            
            self.deserialize(filename)
            os.remove(filename)
        
        # create docx file
        self.make_docx(docx_filename)


    @staticmethod
    def _parse_pages_per_cpu(vector):
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
        all_indexes = range(s, e+1)
        num_pages = len(all_indexes)

        # pages per segment
        seg_size = int(num_pages/cpu) + 1
        seg_from = idx * seg_size
        seg_to = min(seg_from + seg_size, num_pages)
        page_indexes = [all_indexes[i] for i in range(seg_from, seg_to)]

        # parse pages and serialize data for further processing
        cv.parse(page_indexes, config)
        cv.serialize(json_filename)
        cv.close()


    @staticmethod
    def _page_indexes(start, end, pages, pdf_len):
        # parsing arguments
        if pages: 
            indexes = [int(x) for x in pages if 0<=x<pdf_len]
        else:
            end = end or pdf_len
            s = slice(int(start), int(end))
            indexes = range(pdf_len)[s]
        
        return indexes
