# -*- coding: utf-8 -*-

'''A group of instances, e.g. Blocks, Lines, Spans, Shapes.
'''

import fitz
from .Element import Element
from .share import (IText, TextDirection)
from .algorithm import (solve_rects_intersection, graph_bfs)


class BaseCollection:
    '''Base collection representing a list of instances.'''
    def __init__(self, instances:list=None, parent=None):
        '''Init collection from a list of instances.'''
        self._parent = parent
        self._instances = []
        self.extend(instances or []) # Note to exclude empty instance by default

    def __getitem__(self, idx):
        try:
            instances = self._instances[idx]
        except IndexError:
            msg = f'Collection index {idx} out of range.'
            raise IndexError(msg)
        else:
            return instances

    def __iter__(self): return (instance for instance in self._instances)

    def __len__(self): return len(self._instances)

    @property
    def parent(self): return self._parent


    @property
    def bbox(self):
        '''bbox of combined collection.'''
        rect = fitz.Rect()
        for instance in self._instances:
            rect |= instance.bbox
        return fitz.Rect([round(x,1) for x in rect]) # NOTE: round to avoid digital error


    def append(self, instance): 
        if not instance: return
        self._instances.append(instance)


    def extend(self, instances:list): 
        if not instances: return
        for instance in instances: self.append(instance)


    def reset(self, instances:list=None):
        """Reset instances list.

        Args:
            instances (list, optional): reset to target instances. Defaults to None.

        Returns:
            BaseCollection: self
        """
        self._instances = []
        self.extend(instances or [])
        return self


    def store(self):
        '''Store attributes in json format.'''
        return [ instance.store() for instance in self._instances ]


    def restore(self, *args, **kwargs):
        '''Construct Collection from a list of dict.'''
        raise NotImplementedError


class Collection(BaseCollection, IText):
    '''Collection of instance focusing on grouping and sorting elements.'''
    
    @property
    def text_direction(self):
        '''Get text direction. All instances must have same text direction.''' 
        res = set(instance.text_direction for instance in self._instances)
        return list(res)[0] if len(res)==1 else TextDirection.MIX 


    def group(self, fun):
        """Group instances according to user defined criterion.

        Args:
            fun (function): with 2 arguments representing 2 instances (Element) and return bool.

        Returns:
            list: a list of grouped ``Collection`` instances.
        
        Examples 1::

            # group instances intersected with each other
            fun = lambda a,b: a.bbox & b.bbox
        
        Examples 2::

            # group instances aligned horizontally
            fun = lambda a,b: a.horizontally_aligned_with(b)
        
        .. note::
            It's equal to a GRAPH searching problem, build adjacent list, and then search graph
            to find all connected components.
        """
        # build adjacent list:
        # the i-th item is a set of indexes, which connected to the i-th instance.
        # NOTE: O(n^2) method, but it's acceptable (~0.2s) when n<1000 which is satisfied by page blocks
        num = len(self._instances)
        index_groups = [set() for i in range(num)] # type: list[set]        
        for i, instance in enumerate(self._instances):
            # connections of current instance to all instances after it
            for j in range(i+1, num):
                if fun(instance, self._instances[j]):
                    index_groups[i].add(j)
                    index_groups[j].add(i)

        # search graph -> grouped index of instance
        groups = graph_bfs(index_groups)
        groups = [self.__class__([self._instances[i] for i in group]) for group in groups]
        return groups

    
    def group_by_connectivity(self, dx:float, dy:float):
        """Collect connected instances into same group.

        Args:
            dx (float): x-tolerances to define connectivity
            dy (float): y-tolerances to define connectivity

        Returns:
            list: a list of grouped ``Collection`` instances.
        
        .. note::
            * It's equal to a GRAPH traversing problem, which the critical point in 
              building the adjacent list, especially a large number of vertex (paths).

            * Checking intersections between paths is actually a Rectangle-Intersection 
              problem, studied already in many literatures.
        """
        # build the graph -> adjacent list:
        # the i-th item is a set of indexes, which connected to the i-th instance
        num = len(self._instances)
        index_groups = [set() for _ in range(num)] # type: list[set]

        # solve rectangle intersection problem
        i_rect_x, i = [], 0
        d_rect = (-dx, -dy, dx, dy)
        for rect in self._instances:
            points = [a+b for a,b in zip(rect.bbox, d_rect)] # consider tolerance
            i_rect_x.append((i,   points, points[0]))
            i_rect_x.append((i+1, points, points[2]))
            i += 2
        i_rect_x.sort(key=lambda item: item[-1])
        solve_rects_intersection(i_rect_x, 2*num, index_groups)

        # search graph -> grouped index of instance
        groups = graph_bfs(index_groups)
        groups = [self.__class__([self._instances[i] for i in group]) for group in groups]
        return groups
    
    
    def group_by_columns(self, factor:float=0.0, sorted:bool=True, text_direction:bool=False):
        '''Group elements into columns based on the bbox.'''
        # split in columns
        fun = lambda a,b: a.vertically_align_with(b, factor=factor, text_direction=text_direction)
        groups = self.group(fun)
        
        # increase in x-direction if sort
        if sorted: 
            idx = 3 if text_direction and self.is_vertical_text else 0
            groups.sort(key=lambda group: group.bbox[idx])

        return groups


    def group_by_rows(self, factor:float=0.0, sorted:bool=True, text_direction:bool=False):
        '''Group elements into rows based on the bbox.'''
        # split in rows
        fun = lambda a,b: a.horizontally_align_with(b, factor=factor, text_direction=text_direction)
        groups = self.group(fun)

        # increase in y-direction if sort
        if sorted: 
            idx = 0 if text_direction and self.is_vertical_text else 1
            groups.sort(key=lambda group: group.bbox[idx])

        return groups


    def group_by_physical_rows(self, sorted:bool=False, text_direction:bool=False):
        '''Group lines into physical rows.'''
        fun = lambda a,b: a.in_same_row(b)
        groups = self.group(fun)

        # increase in y-direction if sort
        if sorted: 
            idx = 0 if text_direction and self.is_vertical_text else 1
            groups.sort(key=lambda group: group.bbox[idx])

        return groups


    def sort_in_reading_order(self):
        '''Sort collection instances in reading order (considering text direction), e.g.
            for normal reading direction: from top to bottom, from left to right.
        '''
        if self.is_horizontal_text:
            self._instances.sort(key=lambda e: (e.bbox.y0, e.bbox.x0, e.bbox.x1))
        else:
            self._instances.sort(key=lambda e: (e.bbox.x0, e.bbox.y1, e.bbox.y0))
        return self


    def sort_in_line_order(self):
        '''Sort collection instances in a physical with text direction considered, e.g.
            for normal reading direction: from left to right.
        '''
        if not self.is_vertical_text:
            self._instances.sort(key=lambda e: (e.bbox.x0, e.bbox.y0, e.bbox.x1))
        else:
            self._instances.sort(key=lambda e: (e.bbox.y1, e.bbox.x0, e.bbox.y0))
        return self


    def sort_in_reading_order_plus(self):
        '''Sort instances in reading order, especially for instances in same row. Taking 
        natural reading direction for example: reading order for rows, from left to right 
        for instances in row. In the following example, A comes before B::

                         +-----------+
            +---------+  |           |
            |   A     |  |     B     |
            +---------+  +-----------+
        
        Steps:

            * Sort elements in reading order, i.e. from top to bottom, from left to right.
            * Group elements in row.
            * Sort elements in row: from left to right.
        '''
        instances = []
        for row in self.group_by_physical_rows(sorted=True, text_direction=True):
            row.sort_in_line_order()
            instances.extend(row)        
        self.reset(instances)



class ElementCollection(Collection):
    '''Collection of ``Element`` instances.'''

    def _update_bbox(self, e:Element):
        '''Update parent bbox.'''
        if not self._parent is None: # Note: `if self._parent` does not work here
            self._parent.union_bbox(e)


    def append(self, e:Element):
        """Append an instance, update parent's bbox accordingly and set the parent of the added instance.

        Args:
            e (Element): instance to append.
        """
        if not e: return
        self._instances.append(e)
        self._update_bbox(e)

        # set parent
        if not self._parent is None: e.parent = self._parent 


    def insert(self, nth:int, e:Element):
        """Insert a Element and update parent's bbox accordingly.

        Args:
            nth (int): the position to insert.
            e (Element): the instance to insert.
        """        
        if not e: return
        self._instances.insert(nth, e)
        self._update_bbox(e)
        e.parent = self._parent # set parent

    
    def pop(self, nth:int):
        """Delete the ``nth`` instance.

        Args:
            nth (int): the position to remove.

        Returns:
            Collection: the removed instance.
        """        
        return self._instances.pop(nth)


    def is_flow_layout(self, line_separate_threshold:float, cell_layout=False):
        '''Whether contained elements are in flow layout or not.'''
        # float layout if vertical text but not cell layout, since vertical text 
        # will be simulated with stream table
        if not cell_layout and self.is_vertical_text:
            return False

        # flow layout if single column only
        if len(self)<=1: return True
        if len(self.group_by_columns())>1: return False

        # group in physical row and check distance between lines
        idx0, idx1 = (0, 2) if self.is_horizontal_text else (3, 1)
        for row in self.group_by_physical_rows(text_direction=True):
            for i in range(1, len(row)):
                dis = abs(row[i].bbox[idx0]-row[i-1].bbox[idx1])
                if dis >= line_separate_threshold: return False

        return True


    def contained_in_bbox(self, bbox):
        '''Filter instances contained in target bbox.

        Args:
            bbox  (fitz.Rect): target boundary box.
        '''
        instances = list(filter(
            lambda e: bbox.contains(e.bbox), self._instances))
        return self.__class__(instances)


    def split_with_intersection(self, bbox:fitz.Rect, threshold:float=1e-3):
        """Split instances into two groups: one intersects with ``bbox``, the other not.

        Args:
            bbox (fitz.Rect): target rect box.
            threshold (float): It's intersected when the overlap rate exceeds this threshold. Defaults to 0.

        Returns:
            tuple: two group in original class type.
        """
        intersections, no_intersections = [], []
        for instance in self._instances:
            # A contains B => A & B = B
            intersection = instance.bbox & bbox
            if intersection.is_empty:
                no_intersections.append(instance)
            else:
                factor = round(intersection.get_area()/instance.bbox.get_area(), 2)
                if factor >= threshold:
                    intersections.append(instance)
                else:
                    no_intersections.append(instance)
        return self.__class__(intersections), self.__class__(no_intersections)
