# -*- coding: utf-8 -*-

'''
A group of TextSpan and ImageSpan objects.

@created: 2020-07-23
@author: train8808@gmail.com
'''

from .TextSpan import TextSpan

class Spans:
    '''Text span list.'''
    def __init__(self, raws:list=[], parent=None) -> None:
        ''' Construct text span from a list of raw span dict.'''
        self._spans = [ TextSpan(raw) for raw in raws ] # text span by default 
        self._parent = parent # type: Line


    def __getitem__(self, idx):
        try:
            spans = self._spans[idx]
        except IndexError:
            msg = f'Span index {idx} out of range'
            raise IndexError(msg)
        else:
            return spans

    def __iter__(self):
        return (span for span in self._spans)

    def __len__(self):
        return len(self._spans)

    def reset(self, spans:list):
        ''' Reset contained spans with specified ones.
            ---
            Args:
              - spans: list[TextSpan or ImageSpan], target spans
        '''
        self._spans = spans
        return self

    def append(self, span:TextSpan):
        ''' Add a span and update the bbox accordingly.'''
        if not span: return
        self._spans.append(span)
        if not self._parent is None:
            self._parent.union(span.bbox)

    def store(self) -> list:
        return [ span.store() for span in self._spans]

    
    @property
    def text(self) -> str:
        '''Join span text.'''
        # filter text span
        text_spans = list(filter(
            lambda span: isinstance(span, TextSpan), self._spans
        ))
        return ''.join([span.text for span in text_spans])
