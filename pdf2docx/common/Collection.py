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


    def sort_in_reading_order(self):
        '''Sort collection instances in reading order: from top to bottom, from left to right.'''
        self._instances.sort(key=lambda instance: (instance.bbox.y0, instance.bbox.x0))


    def reset(self, bboxes:list=[]):
        '''Reset instances list.'''
        self._instances = []
        self.extend(bboxes)
        return self


    def store(self) -> list:
        '''Store attributes in json format.'''
        return [ instance.store() for instance in self._instances]


    def group(self):
        '''Collect instances intersected with each other as groups.'''
        groups = [] # type: list[Collection]
        counted_index = set() # type: set[int]

        for i in range(len(self._instances)):

            # do nothing if current rect has been considered already
            if i in counted_index:
                continue

            # start a new group
            instance = self._instances[i]
            group = { i }

            # get intersected instances
            self._get_intersected_instances(instance, group)

            # update counted instances
            counted_index = counted_index | group

            # add rect to groups
            group_instances = [self._instances[x] for x in group]
            instances = self.__class__(group_instances)
            groups.append(instances)

        return groups


    def _get_intersected_instances(self, bbox:BBox, group:set):
        ''' Get intersected instances and store in `group`.
            ---
            Args:
              - group: set[int], a set() of index of intersected instances
        '''

        for i in range(len(self._instances)):

            # ignore bbox already processed
            if i in group: continue

            # if intersected, check bboxs further
            target = self._instances[i]
            if bbox.bbox & target.bbox:
                group.add(i)
                self._get_intersected_instances(target, group)