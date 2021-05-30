# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.'''

import logging
from ..common.Collection import BaseCollection
from ..common import constants
from .RawPage import RawPage
from ..font.Fonts import Fonts


class Pages(BaseCollection):
    '''A collection of ``Page``.'''

    def parse(self, fitz_doc, **settings):
        '''Analyse document structure, e.g. page section, header, footer.

        Args:
            fitz_doc (fitz.Document): ``PyMuPDF`` Document instance.
            settings (dict): Parsing parameters.
        '''
        # ---------------------------------------------
        # 0. extract fonts properties
        # ---------------------------------------------
        fonts, default_font = Pages._extract_fonts(fitz_doc, **settings)

        # ---------------------------------------------
        # 1. extract and then clean up raw page
        # ---------------------------------------------
        pages, raw_pages = [], []
        words_found = False
        for page in self:
            if page.skip_parsing: continue

            # init and extract data from PDF
            raw_page = RawPage(fitz_page=fitz_doc[page.id])
            raw_page.restore(**settings)

            # check if any words are extracted since scanned pdf may be directed
            if not words_found and raw_page.raw_text.strip():
                words_found = True

            # process blocks and shapes based on bbox
            raw_page.clean_up(**settings)

            # process font properties
            raw_page.process_font(fonts, default_font)            

            # after this step, we can get some basic properties
            # NOTE: floating images are detected when cleaning up blocks, so collect them here
            page.width = raw_page.width
            page.height = raw_page.height
            page.float_images.reset().extend(raw_page.blocks.floating_image_blocks)

            raw_pages.append(raw_page)
            pages.append(page)

        # show message if no words found
        if not words_found:
            logging.warning('Words count: 0. It might be a scanned pdf, which is not supported yet.')

        
        # ---------------------------------------------
        # 2. parse structure in document/pages level
        # ---------------------------------------------
        # NOTE: blocks structure might be changed in this step, e.g. promote page header/footer,
        # so blocks structure based process, e.g. calculating margin, parse section should be 
        # run after this step.
        header, footer = Pages._parse_document(raw_pages)


        # ---------------------------------------------
        # 3. parse structure in page level, e.g. page margin, section
        # ---------------------------------------------
        # parse sections
        for page, raw_page in zip(pages, raw_pages):
            # page margin
            margin = raw_page.calculate_margin(**settings)
            raw_page.margin = page.margin = margin

            # page section
            sections = raw_page.parse_section(**settings)
            page.sections.extend(sections)
    

    @staticmethod
    def _extract_fonts(fitz_doc, **settings):
        '''Extract font properties, e.g. font family name and line height ratio.'''
        # default font specified by user
        default_name = settings['default_font_name']
        default_font = Fonts.get_defult_font(default_name)

        # extract fonts from pdf
        fonts = Fonts.extract(fitz_doc, default_font)

        # always add a program defined defult font -> in case unnamed font in TextSpan
        font = Fonts.get_defult_font(constants.DEFAULT_FONT_NAME)
        fonts.append(font)

        return fonts, default_font


    @staticmethod
    def _parse_document(raw_pages:list):
        '''Parse structure in document/pages level, e.g. header, footer'''
        # TODO
        return '', ''