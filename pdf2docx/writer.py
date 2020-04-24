import os
from docx import Document

from . import docx


class Writer:
    '''
        generate .docx file with python-docx based on page layout data.
    '''

    def __init__(self):
        self._doc = Document()

    def make_page(self, layout):
        '''generate page'''
        docx.make_page(self._doc, layout)

    def save(self, filename='res.docx'):
        '''save docx file'''
        if os.path.exists(filename):
            os.remove(filename)
        self._doc.save(filename)