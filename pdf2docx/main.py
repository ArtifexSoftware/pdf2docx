#!/usr/bin/python3
# -*- coding: utf-8 -*-


from pdf2docx.converter import Converter


def parse(pdf_file, docx_file, start=0, end=None, pages=[]):
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
        pdf_pages = [cv[int(x)] for x in pages]
    else:
        end = end or pdf_len
        pdf_pages = cv[int(start):int(end)]

    # process page by page
    for page in pdf_pages:
        print(f"Processing {page.number}/{pdf_len-1}...")
        cv.parse(page).make_page()

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
        pdf_pages = [cv[int(x)] for x in pages]
    else:
        end = end or pdf_len
        pdf_pages = cv[int(start):int(end)]

    # process page by page
    tables = []
    for page in pdf_pages:
        print(f"Processing {page.number}/{pdf_len-1}...")
        page_tables = cv.extract_tables(page)
        tables.extend(page_tables)

    cv.close()

    return tables


def main():
    import fire
    fire.Fire(parse)


if __name__ == '__main__':
    main()