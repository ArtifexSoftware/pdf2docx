#!/usr/bin/python3
# -*- coding: utf-8 -*-


from pdf2docx.reader import Reader
from pdf2docx.writer import Writer


def parse(pdf_file, docx_file, start=0, end=None, pages=[]):
    ''' Run the pdf2docx parser
    
        Args:
            pdf_file (str) : PDF filename to read from
            docx_file (str): DOCX filename to write to
            start (int)    : first page to process, starting from zero
            end (int)      : last page to process, starting from zero
            pages (list)   : range of pages
    '''

    pdf = Reader(pdf_file)
    docx = Writer()

    # parsing arguments
    pdf_len = len(pdf)
    if pages: 
        pdf_pages = [pdf[int(x)] for x in pages]
    else:
        end = end or pdf_len
        pdf_pages = pdf[int(start):int(end)]

    # process page by page
    for page in pdf_pages:
        print(f"Processing {page.number}/{pdf_len-1}...")
        # parse layout
        layout = pdf.parse(page)        
        # create docx
        docx.make_page(layout)

    # save docx, close pdf
    docx.save(docx_file)
    pdf.close()
    

def main():
    import fire
    fire.Fire(parse)


if __name__ == '__main__':
    main()