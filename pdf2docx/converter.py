# -*- coding: utf-8 -*-

import os
import json
from time import perf_counter
from multiprocessing import Pool, cpu_count
import fitz
from docx import Document
from .page.Page import Page


class Converter:
    '''The ``PDF`` to ``docx`` converter.
    
    * Read PDF file with ``PyMuPDF`` to get raw layout data page by page, including text,
      image, drawing and its properties, e.g. boundary box, font, size, image width, height.
    * Then parse it to docx structure, e.g. paragraph and its properties like indentaton, 
      spacing, text alignment; table and its properties like border, shading, merging. 
    * Finally, generate docx with ``python-docx``.
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
    def fitz_doc(self): 
        '''fitz.Document: The fitz ``Document``.'''
        return self._fitz_doc


    def close(self): self._fitz_doc.close()

    
    def parse(self, page_indexes=None, kwargs:dict=None):
        """Parse pages in specified ``page_indexes``.

        Args:
            page_indexes (list, optional): Pages to parse. Defaults to None, the entire pages.
            kwargs (dict, optional): Configuration parameters. Defaults to None.

        Returns:
            Converter: self
        """        
        indexes = page_indexes if page_indexes else range(len(self._pages))
        num_pages = len(indexes)
        for i, idx in enumerate(indexes, start=1):
            print(f'\rParsing Page {idx+1}: {i}/{num_pages}...', end='', flush=True)
            try:
                self._pages[idx].parse(kwargs)
            except Exception as e:
                print(f'\nIgnore page due to error: {e}', flush=True)

        return self


    def make_docx(self, docx_filename=None):
        '''Create docx file with converted pages.
        
        Args:
            docx_filename (str): docx filename to write to.
        
        .. note::
            It should be run after parsing page ``parse()``. Otherwise, no parsed pages
            for creating docx file.
        '''
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


    def debug_page(self, i:int, docx_filename:str=None, debug_pdf:str=None, layout_file:str=None, kwargs:dict=None):
        '''Parse, create and plot single page for debug purpose.
        
        Args:
            i (int): Page index to convert.
            docx_filename (str): docx filename to write to.
            debug_pdf (str): New pdf file storing layout information. Default to add prefix ``debug_``.
            layout_file (str): New json file storing parsed layout data. Default to ``layout.json``.
        '''
        kwargs = kwargs if kwargs else {}

        # include debug information
        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(self.filename_pdf)
        if not debug_pdf: debug_pdf = os.path.join(path, f'debug_{filename}')
        if not layout_file: layout_file  = os.path.join(path, 'layout.json')
        kwargs.update({
            'debug'         : True,
            'debug_doc'     : fitz.Document(),
            'debug_filename': debug_pdf
        })

        # parse and create docx
        self.convert(docx_filename, pages=[i], kwargs=kwargs)
        
        # layout information for debugging
        self.serialize(layout_file)


    def convert(self, docx_filename:str=None, start:int=0, end:int=None, pages:list=None, kwargs:dict=None):
        """Convert specified PDF pages to docx file.

        Args:
            docx_filename (str, optional): docx filename to write to. Defaults to None.
            start (int, optional): First page to process. Defaults to 0, the first page.
            end (int, optional): Last page to process. Defaults to None, the last page.
            pages (list, optional): Range of page indexes. Defaults to None.
            kwargs (dict, optional): Configuration parameters. Defaults to None.
        
        List of configuration parameters::

            zero_based_index               : True, page index from 0 if True else 1
            multi_processing               : False, set multi-processes, especially for PDF with large pages
            cpu_count                      : cpu_count(), the count of cpu used for multi-processing
            connected_border_tolerance     : 0.5, two borders are intersected if the gap lower than this value
            max_border_width               : 6.0, max border width
            min_border_clearance           : 2.0, the minimum allowable clearance of two borders
            float_image_ignorable_gap      : 5.0, float image if the intersection exceeds this value
            float_layout_tolerance         : 0.1, [0,1] the larger of this value, the more tolerable of float layout
            page_margin_factor_top         : 0.5, [0,1] reduce top margin by factor
            page_margin_factor_bottom      : 0.5, [0,1] reduce bottom margin by factor
            shape_merging_threshold        : 0.5, [0,1] merge shape if the intersection exceeds this value
            shape_min_dimension            : 2.0, ignore shape if both width and height is lower than this value
            line_overlap_threshold         : 0.9, [0,1] delete line if the intersection to other lines exceeds this value
            line_merging_threshold         : 2.0, combine two lines if the x-distance is lower than this value
            line_separate_threshold        : 5.0, two separate lines if the x-distance exceeds this value
            lines_left_aligned_threshold   : 1.0, left aligned if delta left edge of two lines is lower than this value
            lines_right_aligned_threshold  : 1.0, right aligned if delta right edge of two lines is lower than this value
            lines_center_aligned_threshold : 2.0, center aligned if delta center of two lines is lower than this value
            clip_image_res_ratio           : 3.0, resolution ratio (to 72dpi) when cliping page image
            curve_path_ratio               : 0.2, clip page bitmap if the component of curve paths exceeds this ratio
        
        .. note::
            Change extension from ``pdf`` to ``docx`` if ``docx_file`` is None.
        
        .. note::
            * ``start`` and ``end`` is counted from zero if ``--zero_based_index=True`` (by default).
            * Start from the first page if ``start`` is omitted.
            * End with the last page if ``end`` is omitted.
        
        .. note::
            ``pages`` has a higher priority than ``start`` and ``end``. ``start`` and ``end`` works only
            if ``pages`` is omitted.
        """ 
        kwargs = kwargs if kwargs else {}
        
        # pages to convert
        page_indexes = self._page_indexes(start, end, pages, len(self))
        
        # convert page by page
        t0 = perf_counter()        
        if kwargs.get('multi_processing', False):
            self._parse_and_create_pages_with_multi_processing(docx_filename, page_indexes, kwargs)
        else:
            self._parse_and_create_pages(docx_filename, page_indexes, kwargs)       
        print(f'\n{"-"*50}\nTerminated in {perf_counter()-t0}s.')        


    def extract_tables(self, start:int=0, end:int=None, pages:list=None, kwargs:dict=None):
        '''Extract table contents from specified PDF pages.

        Args:
            start (int, optional): First page to process. Defaults to 0, the first page.
            end (int, optional): Last page to process. Defaults to None, the last page.
            pages (list, optional): Range of page indexes. Defaults to None.
            kwargs (dict, optional): Configuration parameters. Defaults to None.
        
        Returns:
            list: A list of parsed table content.
        '''
        # PDF pages to convert
        kwargs = kwargs if kwargs else {}
        page_indexes = self._page_indexes(start, end, pages, len(self))

        # process page by page
        self.parse(page_indexes, kwargs)

        # get parsed tables
        tables = []
        for page in self._pages:
            if page.finalized: tables.extend(page.extract_tables())
        return tables


    def _parse_and_create_pages(self, docx_filename:str, page_indexes:list, kwargs:dict):
        '''Parse and create pages based on page indexes.
        
        Args:
            docx_filename (str): docx filename to write to.
            page_indexes (list[int]): Page indexes to parse.
        '''
        self.parse(page_indexes=page_indexes, kwargs=kwargs).make_docx(docx_filename)


    def _parse_and_create_pages_with_multi_processing(self, docx_filename:str, page_indexes:list, kwargs:dict):
        '''Parse and create pages based on page indexes with multi-processing.

        Reference:

            https://pymupdf.readthedocs.io/en/latest/faq.html#multiprocessing

        Args:
            docx_filename (str): docx filename to write to.
            page_indexes (list[int]): Page indexes to parse.
        '''
        # make vectors of arguments for the processes
        cpu = min(kwargs['cpu_count'], cpu_count()) if 'cpu_count' in kwargs else cpu_count()
        start, end = min(page_indexes), max(page_indexes)
        prefix = 'pages' # json file writing parsed pages per process
        vectors = [(i, cpu, start, end, self.filename_pdf, kwargs, f'{prefix}-{i}.json') for i in range(cpu)]

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
        '''Render a page range of a document.
        
        Args:
            vector (list): A list containing required parameters.
                * 0  : segment number for current process                
                * 1  : count of CPUs
                * 2,3: whole pages range to process since sometimes need only parts of pdf pages                
                * 4  : pdf filename
                * 5  : configuration parameters
                * 6  : json filename storing parsed results
        '''
        # recreate the arguments
        idx, cpu, s, e, pdf_filename, kwargs, json_filename = vector

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
        cv.parse(page_indexes, kwargs)
        cv.serialize(json_filename)
        cv.close()


    @staticmethod
    def _page_indexes(start, end, pages, pdf_len):
        '''Parsing arguments.'''
        if pages: 
            indexes = [int(x) for x in pages if 0<=x<pdf_len]
        else:
            end = end or pdf_len
            s = slice(int(start), int(end))
            indexes = range(pdf_len)[s]
        
        return indexes
