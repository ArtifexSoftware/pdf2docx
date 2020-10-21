# -*- coding: utf-8 -*-

import os
import json
from collections import defaultdict
from time import perf_counter
from multiprocessing import Pool, cpu_count
import fitz
from docx import Document

from .layout.Layout import Layout
from .shape.Path import PathsExtractor
from .image.Image import ImagesExtractor



class Converter:
    ''' Read PDF file `pdf_file` with PyMuPDF to get raw layout data page by page, including text, 
        image and the associated properties, e.g. bounding box, font, size, image width, height, 
        then parse it with consideration for docx re-generation structure. Finally, generate docx
        with python-docx.
    '''

    def __init__(self, pdf_file:str, docx_file:str=None):
        ''' Initialize fitz object with given pdf file path; initialize docx object.'''
        # pdf/docx filename
        self.filename_pdf = pdf_file
        self.filename_docx = docx_file if docx_file else pdf_file.replace('.pdf', '.docx')
        if os.path.exists(self.filename_docx): os.remove(self.filename_docx)

        # fitz object to read pdf
        self._doc_pdf = fitz.Document(pdf_file)

        # docx object to write file
        self._doc_docx = Document()

        # layout object: main worker
        self._paths_extractor = None  # PathsExtractor
        self._layout = None # type: Layout        


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

    def save(self): self._doc_docx.save(self.filename_docx)

    def close(self): self._doc_pdf.close()


    def initialize(self, page:fitz.Page):
        '''Initialize layout object.'''
        # -----------------------------------------
        # Layout blocks with image blocks updated
        # -----------------------------------------
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout = self._page_blocks(page)

        # -----------------------------------------
        # page size
        # -----------------------------------------
        # though 'width', 'height' are contained in `raw_dict`, they are based on un-rotated page.
        # so, update page width/height to right direction in case page is rotated
        *_, w, h = page.rect # always reflecting page rotation
        raw_layout.update({ 'width' : w, 'height': h })
        
        # -----------------------------------------
        # page paths
        # -----------------------------------------
        # convert vector graphic paths to pixmap
        self._paths_extractor = PathsExtractor()
        images, paths = self._paths_extractor.extract_paths(page)
        raw_layout['blocks'].extend(images)
        raw_layout['paths'] = paths

        # init layout
        self._layout = Layout(raw_layout, page.rotationMatrix)    

        return self._layout


    def debug_page(self, page:fitz.Page):
        ''' Parse, create and plot single page for debug purpose.
            Illustration pdf will be created during parsing the raw pdf layout.
        '''
        # debug information
        # fitz object in debug mode: plot page layout
        # file path for this debug pdf: demo.pdf -> debug_demo.pdf
        path, filename = os.path.split(self.filename_pdf)
        filename_json  = os.path.join(path, 'layout.json')
        debug_kwargs = {
            'debug'   : True,
            'doc'     : fitz.Document(),
            'filename': os.path.join(path, f'debug_{filename}')
        }

        # init page layout
        self.initialize(page)
        self._layout.plot(**debug_kwargs)
        self._paths_extractor.paths.plot(debug_kwargs['doc'], 'Source Paths', self._layout.width, self._layout.height)

        # parse and save debug files
        self.layout.parse(**debug_kwargs)
        if len(debug_kwargs['doc']): debug_kwargs['doc'].save(debug_kwargs['filename']) # layout plotting        
        self.layout.serialize(filename_json) # layout information
        
        # make docx page
        self._layout.make_page(self.doc_docx)
        self.save()

        return self


    def make_docx(self, page_indexes:list, multi_processing=False):
        '''Parse and create a list of pages.
            ---
            Args:
            - page_indexes    : list[int], page indexes to parse
            - multi_processing: bool, multi-processing mode if True
        '''
        t0 = perf_counter()
        if multi_processing:
            self._make_docx_multi_processing(page_indexes)
        else:
            self._make_docx(page_indexes)
        
        print(f'\n{"-"*50}\nTerminated in {perf_counter()-t0}s.')


    def extract_tables(self, page_indexes:list):
        '''Extract table contents.'''
        tables = []
        num_pages = len(page_indexes)
        # process page by page        
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...')
            page = self.doc_pdf[i]
            page_tables = self.initialize(page).extract_tables()
            tables.extend(page_tables)

        return tables


    @staticmethod
    def _page_blocks(page:fitz.Page):
        '''Get page blocks and adjust image blocks.'''
        # Layout object based on raw dict:
        # NOTE: all these coordinates are relative to un-rotated page
        # https://pymupdf.readthedocs.io/en/latest/page.html#modifying-pages
        raw_layout = page.getText('rawdict')

        # Adjust image blocks:
        # Image blocks are generated for every image location – whether or not there are any duplicates. 
        # This is in contrast to Page.getImageList(), which will contain each image only once.
        # https://pymupdf.readthedocs.io/en/latest/textpage.html#dictionary-structure-of-extractdict-and-extractrawdict
        # 
        # So, a compromise:
        # - get image contents with `page.getImageList`
        # - get image location with `page.getText('rawdict')`
        # 
        # extract and recover images
        recovered_images = ImagesExtractor.extract_images(page)

        # group original image blocks by image contents
        image_blocks_group = defaultdict(list)
        for block in raw_layout['blocks']:
            if block['type'] != 1: continue
            image_blocks_group[hash(block['image'])].append(block)

        # update raw layout blocks
        def same_images(img, img_list):
            bbox = list(map(round, img['bbox']))
            for _img in img_list:
                if list(map(round, _img['bbox']))==bbox: return True
            return False

        for k, image_blocks in image_blocks_group.items():
            for image in recovered_images:
                if not same_images(image, image_blocks): continue
                for image_block in image_blocks: image_block['image'] = image['image']
                raw_layout['blocks'].extend(image_blocks)
                break

        return raw_layout


    def _make_docx(self, page_indexes:list):
        ''' Parse and create pages based on page indexes.
            ---
            Args:
            - page_indexes: list[int], page indexes to parse
        '''
        num_pages = len(page_indexes)
        for i in page_indexes:
            print(f'\rProcessing Pages: {i+1}/{num_pages}...', end='', flush=True)
            page = self.doc_pdf[i]
            self.initialize(page).parse().make_page(self.doc_docx)
        self.save()


    def _make_docx_multi_processing(self, page_indexes:list):
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
        vectors = [(i, cpu, start, end, self.filename_pdf, f'{prefix_layout}-{i}.json') for i in range(cpu)]

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
        idx, cpu, s, e, pdf_filename, json_filename = vector

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
            cv.initialize(page).parse()

            # page results
            res[page_index] = cv.layout.store()

        # serialize results
        with open(json_filename, 'w') as f:
            f.write(json.dumps(res))
            