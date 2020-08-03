# -*- coding: utf-8 -*-

'''
A group of instances, e.g. instances, Spans, Rectangles.

@created: 2020-07-24
@author: train8808@gmail.com
'''

from .BBox import BBox
from .Block import Block
from .base import IText, TextDirection

class Collection(IText):
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


    @property
    def text_direction(self):
        '''Get text direction. All instances must have same text direction.''' 
        if self._instances and hasattr(self._instances[0], 'text_direction'):
            res = set(instance.text_direction for instance in self._instances)
            if len(res)==1:
                return list(res)[0]

        # normal direction by default
        return TextDirection.LEFT_RIGHT 


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
        '''Sort collection instances in reading order (considering text direction), e.g.
            for normal reading direction: from top to bottom, from left to right.
        '''
        if self.is_horizontal:
            self._instances.sort(key=lambda instance: (instance.bbox.y0, instance.bbox.x0, instance.bbox.x1))
        else:
            self._instances.sort(key=lambda instance: (instance.bbox.x0, instance.bbox.y1, instance.bbox.y0))

    def sort_in_line_order(self):
        '''Sort collection instances in a physical with text direction considered, e.g.
            for normal reading direction: from left to right.
        '''
        if self.is_horizontal:
            self._instances.sort(key=lambda instance: (instance.bbox.x0, instance.bbox.y0, instance.bbox.x1))
        else:
            self._instances.sort(key=lambda instance: (instance.bbox.y1, instance.bbox.x0, instance.bbox.y0))

    def reset(self, bboxes:list=[]):
        '''Reset instances list.'''
        self._instances = []
        self.extend(bboxes)
        return self


    def store(self) -> list:
        '''Store attributes in json format.'''
        return [ instance.store() for instance in self._instances ]


    def group(self, fun):
        '''group instances according to user defined criterion.
            ---
            Args:
              - fun: function with 2 parameters (BBox) representing 2 instances, and return bool
            
            Examples:
            ```
            # group instances intersected with each other
            fun = lambda a,b: a & b
            # group instances aligned horizontally
            fun = lambda a,b: a.horizontally_aligned_with(b)
            ```
        '''
        groups = [] # type: list[Collection]
        counted_index = set() # type: set[int]

        # sort in reading order
        self.sort_in_reading_order()

        # check each instance to the others
        for i,instance in enumerate(self._instances):

            # do nothing if current rect has been considered already
            if i in counted_index:
                continue

            # start a new group
            group = { i }

            # get intersected instances
            self._group_instances(instance, group, fun)

            # update counted instances
            counted_index = counted_index | group

            # add rect to groups
            group_instances = [self._instances[x] for x in group]
            instances = self.__class__(group_instances)
            groups.append(instances)

        return groups


    def _group_instances(self, bbox:BBox, group:set, fun):
        ''' Get instances related to given bbox.
            ---
            Args:
              - bbox: reference bbox
              - group: set[int], a set() of index of intersected instances
              - fun: define the relationship with reference bbox. 
                    2 parameters: instance 1 and instance 2, return bool.
        '''

        idx = 1 if self.is_horizontal else 0

        for i, target in enumerate(self._instances):

            # ignore bbox already processed
            if i in group: continue

            # # ignore instances with different text direction
            # if self.text_direction != bbox.text_direction:
            #     continue

            # if satisfying given relationship, check bboxs further
            if fun(bbox, target):
                group.add(i)
                self._group_instances(target, group, fun)

            # it's sorted already, so no relationship exists if not intersected in vertical direction 
            else:
                if target.bbox_raw[idx] > bbox.bbox_raw[idx+2]:
                    break