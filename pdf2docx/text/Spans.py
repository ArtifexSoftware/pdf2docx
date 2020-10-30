# -*- coding: utf-8 -*-

'''
A group of TextSpan and ImageSpan objects.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from ..common.Collection import Collection
from .TextSpan import TextSpan
from ..image.ImageSpan import ImageSpan

class Spans(Collection):
    '''Text span list.'''

    def restore(self, raws:list):
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


    def strip(self):
        '''remove redundant blanks at the begin/end span.'''
        stripped = False
        if not self._instances: return stripped
        
        # left strip the first span
        left_span = self._instances[0]
        if isinstance(left_span, TextSpan): stripped = stripped or left_span.lstrip() 

        # right strip the last span
        right_span = self._instances[-1]
        if isinstance(right_span, TextSpan): stripped = stripped or right_span.rstrip()

        # update bbox
        if stripped: self._parent.update_bbox(self.bbox)

        return stripped