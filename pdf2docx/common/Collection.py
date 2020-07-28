# -*- coding: utf-8 -*-

'''
A group of instances, e.g. instances, Spans, Rectangles.

@created: 2020-07-24
@author: train8808@gmail.com
'''

from .BBox import BBox
from .Block import Block

class Collection:
    '''Collection of specific instances.'''
    def __init__(self, instances:list=[], parent=None) -> None:
        ''' Construct text line from a list of raw line dict.'''
        self._instances = instances if instances else [] # type: list[BBox]
        self._parent = parent # type: Block


    def __getitem__(self, idx):
        try:
            instances = self._instances[idx]
        except IndexError:
            msg = f'Collection index {idx} out of range'
            raise IndexError(msg)
        else:
            return instances


    def __iter__(self):
        return (instance for instance in self._instances)


    def __len__(self):
        return len(self._instances)

    
    def from_dicts(self, *args, **kwargs):
        '''Construct Collection from a list of dict.'''
        raise NotImplementedError


    def append(self, bbox:BBox):
        '''Append an instance and update parent's bbox accordingly.'''
        if not bbox: return
        self._instances.append(bbox)
        if not self._parent is None: # Note: `if self._parent` does not work here
            self._parent.union(bbox.bbox)


    def extend(self, bboxes:list):
        '''Append a list of instances.'''
        for bbox in bboxes:
            self.append(bbox)


    def insert(self, nth:int, bbox:BBox):
        '''Insert a BBox and update parent's bbox accordingly.'''
        if not bbox: return
        self._instances.insert(nth, bbox)
        if not self._parent is None:
            self._parent.union(bbox.bbox)

    def reset(self, bboxes:list=[]):
        '''Reset instances list.'''
        self._instances = []
        self.extend(bboxes)
        return self


    def store(self) -> list:
        '''Store attributes in json format.'''
        return [ instance.store() for instance in self._instances]
