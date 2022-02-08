# -*- coding: utf-8 -*-

'''Base class for text/image/table blocks.
'''

from .share import BlockType, TextAlignment
from .Element import Element


class Block(Element):
    '''Base class for text/image/table blocks.

    Attributes:
        raw (dict): initialize object from raw properties.
        parent (optional): parent object that this block belongs to.
    '''
    def __init__(self, raw:dict=None, parent=None):        
        self._type = BlockType.UNDEFINED

        # horizontal spacing
        if raw is None: raw = {}
        self.alignment = self._get_alignment(raw.get('alignment', 0))
        self.left_space = raw.get('left_space', 0.0)
        self.right_space = raw.get('right_space', 0.0)
        self.first_line_space = raw.get('first_line_space', 0.0)

        # RELATIVE position of tab stops
        self.tab_stops = raw.get('tab_stops', []) 

        # vertical spacing
        self.before_space = raw.get('before_space', 0.0)
        self.after_space = raw.get('after_space', 0.0)        
        self.line_space = raw.get('line_space', 0.0)
        self.line_space_type = raw.get('line_space_type', 1) # 0-exactly, 1-relatively

        super().__init__(raw, parent)


    @property
    def is_text_block(self):
        '''Whether test block.'''        
        return self._type==BlockType.TEXT    
    
    @property
    def is_inline_image_block(self):
        '''Whether inline image block.'''
        return self._type==BlockType.IMAGE
    
    @property
    def is_float_image_block(self):
        '''Whether float image block.'''
        return self._type==BlockType.FLOAT_IMAGE
    
    @property
    def is_image_block(self):
        '''Whether inline or float image block.'''
        return self.is_inline_image_block or self.is_float_image_block

    @property
    def is_text_image_block(self):
        '''Whether text block or inline image block.'''
        return self.is_text_block or self.is_inline_image_block

    @property
    def is_lattice_table_block(self):
        '''Whether lattice table (explicit table borders) block.'''
        return self._type==BlockType.LATTICE_TABLE

    @property
    def is_stream_table_block(self):
        '''Whether stream table (implied by table content) block.'''
        return self._type==BlockType.STREAM_TABLE

    @property
    def is_table_block(self):
        '''Whether table (lattice or stream) block.'''
        return self.is_lattice_table_block or self.is_stream_table_block

    def set_text_block(self):
        '''Set block type.'''
        self._type = BlockType.TEXT

    def set_inline_image_block(self):
        '''Set block type.'''
        self._type = BlockType.IMAGE

    def set_float_image_block(self):
        '''Set block type.'''
        self._type = BlockType.FLOAT_IMAGE

    def set_lattice_table_block(self):
        '''Set block type.'''
        self._type = BlockType.LATTICE_TABLE

    def set_stream_table_block(self):
        '''Set block type.'''
        self._type = BlockType.STREAM_TABLE

    def _get_alignment(self, mode:int):
        for t in TextAlignment:
            if t.value==mode:
                return t
        return TextAlignment.LEFT

    def parse_horizontal_spacing(self, bbox, *args):
        """Set left alignment, and calculate left space. 
        
        Override by :obj:`pdf2docx.text.TextBlock`.

        Args:
            bbox (fitz.rect): boundary box of this block.
        """
        # NOTE: in PyMuPDF CS, horizontal text direction is same with positive x-axis,
        # while vertical text is on the contrarory, so use f = -1 here
        idx, f = (0, 1.0) if self.is_horizontal_text else (3, -1.0)
        self.alignment = TextAlignment.LEFT
        self.left_space = (self.bbox[idx] - bbox[idx]) * f
       

    def store(self):
        '''Store attributes in json format.'''
        res = super().store()
        res.update({
            'type'             : self._type.value,
            'alignment'        : self.alignment.value,
            'left_space'       : self.left_space,
            'right_space'      : self.right_space,
            'first_line_space' : self.first_line_space,
            'before_space'     : self.before_space,
            'after_space'      : self.after_space,
            'line_space'       : self.line_space,
            'line_space_type'  : self.line_space_type,
            'tab_stops'        : self.tab_stops
            })
        return res


    def make_docx(self, *args, **kwargs):
        """Create associated docx element.

        Raises:
            NotImplementedError
        """
        raise NotImplementedError