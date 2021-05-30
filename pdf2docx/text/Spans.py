# -*- coding: utf-8 -*-

'''A group of TextSpan and ImageSpan objects.
'''

from ..common.Collection import ElementCollection
from .TextSpan import TextSpan
from ..image.ImageSpan import ImageSpan

class Spans(ElementCollection):
    '''Collection of TextSpan and ImageSpan instances.'''

    def restore(self, raws:list):
        '''Recreate TextSpan or ImageSpan from source dict list.'''
        for raw_span in raws:
            if 'image' in raw_span:
                span = ImageSpan(raw_span)
            else:
                span = TextSpan(raw_span)
                if not span.text.strip() and not span.style: 
                    span = None

            self.append(span)
        return self

    @property
    def text_spans(self):
        '''Get TextSpan instances.'''
        spans = list(filter(
            lambda span: isinstance(span, TextSpan), self._instances
        ))
        return Spans(spans)

    @property
    def image_spans(self):
        '''Get ImageSpan instances.'''
        spans = list(filter(
            lambda span: isinstance(span, ImageSpan), self._instances
        ))
        return Spans(spans)


    def strip(self):
        '''Remove redundant blanks at the begin/end span.'''
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