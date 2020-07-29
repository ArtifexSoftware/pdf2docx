# -*- coding: utf-8 -*-

'''
A group of TextSpan and ImageSpan objects.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from ..common.Collection import Collection
from .TextSpan import TextSpan
from .ImageSpan import ImageSpan

class Spans(Collection):
    '''Text span list.'''

    def from_dicts(self, raws:list):
        for raw_span in raws:
            span = ImageSpan(raw_span) if 'image' in raw_span else TextSpan(raw_span)
            self.append(span)
        return self

    @property
    def text_spans(self):
        spans = list(filter(
            lambda span: isinstance(span, TextSpan), self._instances
        ))
        return Spans(spans)

    @property
    def image_spans(self):
        spans = list(filter(
            lambda span: isinstance(span, ImageSpan), self._instances
        ))
        return Spans(spans)
    
    @property
    def text(self) -> str:
        '''Join span text.'''
        return ''.join([span.text for span in self.text_spans])
