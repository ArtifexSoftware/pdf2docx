#!/usr/bin/python3
# -*- coding: utf-8 -*-

import logging
from .converter import Converter


class PDF2DOCX:
    '''Command line interface for ``pdf2docx``.'''

    @staticmethod
    def convert(pdf_file:str, docx_file:str=None, password:str=None, start:int=0, end:int=None, pages:list=None, **kwargs):
        '''Convert pdf file to docx file.
        
        Args:
            pdf_file (str) : PDF filename to read from.
            docx_file (str, optional): docx filename to write to. Defaults to None.
            password (str): Password for encrypted pdf. Default to None if not encrypted.
            start (int, optional): First page to process. Defaults to 0.
            end (int, optional): Last page to process. Defaults to None.
            pages (list, optional): Range of pages. Defaults to None.
            kwargs (dict) : Configuration parameters.
        
        .. note::
            Refer to :py:meth:`~pdf2docx.converter.Converter.convert` for detailed description on above arguments.
        '''
        # index starts from zero or one
        if not kwargs.get('zero_based_index', True):
            start = max(start-1, 0)
            if end: end -= 1
            if pages: pages = [i-1 for i in pages]

        cv = Converter(pdf_file, password)
        try:
            cv.convert(docx_file, start, end, pages, kwargs)
        except Exception as e:
            logging.error(e)
        finally:
            cv.close()
    

    @staticmethod
    def debug(pdf_file:str, password:str=None, page_index:int=0, docx_file:str=None, debug_pdf:str=None, layout_file:str='layout.json', **kwargs):
        '''Convert one PDF page and plot layout information for debugging.
        
        Args:
            pdf_file (str) : PDF filename to read from.
            password (str): Password for encrypted pdf. Default to None if not encrypted.
            page_index (int, optional): Page index to convert.
            docx_file (str, optional): docx filename to write to.
            debug_pdf (str, optional): Filename for new pdf storing layout information. Defaults to same name with pdf file.
            layout_file (str, optional): Filename for new json file storing parsed layout data. Defaults to ``layout.json``.
            kwargs (dict)  : Configuration parameters.
        '''
        # index starts from zero or one
        if not kwargs.get('zero_based_index', True):
            page_index = max(page_index-1, 0)

        # explode exception directly if debug mode
        cv = Converter(pdf_file, password)
        cv.debug_page(page_index, docx_file, debug_pdf, layout_file, kwargs)
        cv.close()
            


    @staticmethod
    def table(pdf_file, password:str=None, start:int=0, end:int=None, pages:list=None, **kwargs):
        '''Extract table content from pdf pages.
        
        Args:
            pdf_file (str) : PDF filename to read from.
            password (str): Password for encrypted pdf. Default to None if not encrypted.
            start (int, optional): First page to process. Defaults to 0.
            end (int, optional): Last page to process. Defaults to None.
            pages (list, optional): Range of pages. Defaults to None.
        '''
        # index starts from zero or one
        if not kwargs.get('zero_based_index', True):
            start = max(start-1, 0)
            if end: end -= 1
            if pages: pages = [i-1 for i in pages]
        
        cv = Converter(pdf_file, password)
        try:
            tables = cv.extract_tables(start, end, pages, kwargs)
        except Exception as e:
            tables = []
            logging.error(e)
        finally:
            cv.close()

        return tables


parse = PDF2DOCX.convert


def main():
    import fire
    fire.Fire(PDF2DOCX)


if __name__ == '__main__':
    main()