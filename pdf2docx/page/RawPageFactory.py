'''
Load :py:class:`~pdf2docx.page.RawPage` with specified pdf engine, 
e.g. PyMuPDF, pdfminer.six. For now, only PyMuPDF is implemented.
'''

from .RawPageFitz import RawPageFitz


class RawPageFactory:

    MAP = {
        'PYMUPDF': RawPageFitz
    }

    @classmethod
    def create(cls, page_engine, backend:str='pymupdf'):
        '''Create RawPage class with specified backend.'''
        klass = cls.MAP.get(backend.upper(), None)
        if not klass:
            raise TypeError(f'Page with pdf engine "{backend}" is not implemented yet.')
        else:
            return klass(page_engine=page_engine)
        