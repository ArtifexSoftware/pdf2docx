# -*- coding: utf-8 -*-

'''Collection of :py:class:`~pdf2docx.page.Page` instances.


'''

from ..common.Collection import BaseCollection
from .RawPage import RawPage


class Pages(BaseCollection):
    '''A collection of ``Page``.'''

    def parse(self, fitz_doc, settings:dict):
        '''Analyse document structure, e.g. page section, header, footer.

        Args:
            fitz_doc (fitz.Document): ``PyMuPDF`` Document instance.
            settings (dict): Parsing parameters.
        '''
        # ---------------------------------------------
        # 1. extract and then clean up raw page
        # ---------------------------------------------
        raw_pages = []
        for page in self:
            raw_page = RawPage(fitz_page=fitz_doc[page.id])
            raw_page.restore(settings)
            raw_page.clean_up(settings)
            raw_pages.append(raw_page)

            # after this step, we can get some basic properties
            # NOTE: floating images are detected when cleaning up blocks, so collect them here
            page.width = raw_page.width
            page.height = raw_page.height
            page.float_images.reset().extend(raw_page.blocks.floating_image_blocks)
        
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
        for page, raw_page in zip(self, raw_pages):
            # page margin
            margin = raw_page.calculate_margin(settings)
            raw_page.margin = page.margin = margin

            # page section
            sections = raw_page.parse_section(settings)
            page.sections.extend(sections)


    @staticmethod
    def _parse_document(raw_pages:list):
        '''Parse structure in document/pages level, e.g. header, footer'''
        # TODO
        return '', ''