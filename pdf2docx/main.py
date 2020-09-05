#!/usr/bin/python3
# -*- coding: utf-8 -*-


from .converter import Converter


def parse(pdf_file, docx_file=None, start=0, end=None, pages=None, multi_processing=False):
    ''' Run the pdf2docx parser.
    
        Args:
            pdf_file (str) : PDF filename to read from
            docx_file (str): DOCX filename to write to
            start (int)    : first page to process, starting from zero
            end (int)      : last page to process, starting from zero
            pages (list)   : range of pages
    '''

    cv = Converter(pdf_file, docx_file)

    # parsing arguments
    pdf_len = len(cv)
    if pages: 
        indexes = [int(x) for x in pages if 0<=x<pdf_len]
    else:
        end = end or pdf_len
        s = slice(int(start), int(end))
        indexes = range(pdf_len)[s]

    # process page by page
    cv.make_docx(indexes, multi_processing)

    # close pdf
    cv.close()
    

def extract_tables(pdf_file, start=0, end=None, pages=[]):
    ''' Extract table content from pdf pages.
    
        Args:
            pdf_file (str) : PDF filename to read from
            start (int)    : first page to process, starting from zero
            end (int)      : last page to process, starting from zero
            pages (list)   : range of pages
    '''

    cv = Converter(pdf_file)

    # parsing arguments
    pdf_len = len(cv)
    if pages: 
        indexes = [int(x) for x in pages if 0<=x<pdf_len]
    else:
        end = end or pdf_len
        s = slice(int(start), int(end))
        indexes = range(pdf_len)[s]

    # process page by page
    tables = cv.extract_tables(indexes)
    cv.close()

    return tables


def main():
    import fire
    fire.Fire(parse)


if __name__ == '__main__':
    main()