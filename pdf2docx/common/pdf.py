# -*- coding: utf-8 -*-

'''
PDF operations, e.g. extract rectangles, based on PyMuPDF

@created: 2020-07-22
@author: train8808@gmail.com
'''

import fitz
from . import utils


def new_page(doc, width:float, height:float, title:str):
    ''' Insert a new page with given title.
        ---
        Args:
        - doc: fitz.Document
        - width, height: page size
        - title: page title shown in page
    '''
    # insert a new page
    page = doc.newPage(width=width, height=height)    

    # plot title at the top-left corner
    gray = utils.RGB_component_from_name('gray')
    page.insertText((5, 16), title, color=gray, fontsize=15)
    
    return page


def recover_pixmap(doc:fitz.Document, item:list):
    '''Restore pixmap with soft mask considered.
        ---
        - doc: fitz document
        - item: an image item got from page.getImageList()

        Read more:
        - https://pymupdf.readthedocs.io/en/latest/document.html#Document.getPageImageList        
        - https://pymupdf.readthedocs.io/en/latest/faq.html#how-to-handle-stencil-masks
        - https://github.com/pymupdf/PyMuPDF/issues/670
    '''
    # data structure of `item`:
    # (xref, smask, width, height, bpc, colorspace, ...)
    x = item[0]  # xref of PDF image
    s = item[1]  # xref of its /SMask

    # base image
    pix = fitz.Pixmap(doc, x)

    # reconstruct the alpha channel with the smask if exists
    if s > 0:        
        # copy of base image, with an alpha channel added
        pix = fitz.Pixmap(pix, 1)  
        
        # create pixmap of the /SMask entry
        ba = bytearray(fitz.Pixmap(doc, s).samples)
        for i in range(len(ba)):
            if ba[i] > 0: ba[i] = 255
        pix.setAlpha(ba)

    # we may need to adjust something for CMYK pixmaps here -> 
    # recreate pixmap in RGB color space if necessary
    # NOTE: pix.colorspace may be None for images with alpha channel values only
    if pix.colorspace and not pix.colorspace.name in (fitz.csGRAY.name, fitz.csRGB.name):
        pix = fitz.Pixmap(fitz.csRGB, pix)

    return pix

