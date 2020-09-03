# -*- coding: utf-8 -*-

'''
Module to determin stream table borders.

Though no exact borders exist for stream table, it's better to simplify table structure by
aligning borders as more as possible. Taking vertical borders for example, it can be moved 
in a valid range in horizontal direction, but restricted by top and bottom borders in vertical 
direction. It's also true for horizontal borders.

Accordingly, introduce `Border` object, which has the following attributes:
- valid range, e. g. (100, 250);
- boundary borders, e. g. (top_border, bottom_border) for v-border, 
                       or (left_border, right_border) for h-border.

The target is to finalize the position in valid range, e. g. x=125 for v-border with valid range 
(120, 250). Then it's y-direction is determined by its boundary borders, where the y-coordinates 
are finalized in same logic. Finally, this border is fixed since both x- and y- directions are 
determined.

NOTE:
Consider horizontal and vertical borders only.

@created: 2020-08-29
@author: train8808@gmail.com
'''


from ..shape.Rectangles import Rectangles
from ..shape.Rectangle import Rectangle
from ..common.utils import expand_centerline, RGB_value
from ..common.constants import MAX_W_BORDER, HIDDEN_W_BORDER
from ..common.base import RectType


class Border:

    def __init__(self, border_range:tuple=None, borders:tuple=None):
        '''Border for stream table.
            ---
            Args:
            - border_range: valid range, e.g. (x0, x1) for vertical border
            - borders: boundary borders, e.g. top and bottom horizontal borders for current vertical
            border; left and right vertical borders for current horizontal border. 
        '''
        # valid range
        self.set_border_range(border_range)

        # boundary borders
        self.set_boundary_borders(borders)
        
        # border style
        self.width = HIDDEN_W_BORDER
        self.color = RGB_value((1,1,1)) # white by default

        # whether the position is determined
        self.finalized = False

    
    def is_valid(self, x:float):
        '''Whether the given position `x` locates in the valid border range.'''
        return self.LRange < x < self.URange
    
    def set_border_range(self, border_range):
        '''Set border valid ranges.'''
        if border_range:
            x0, x1 = border_range
        else:
            x0, x1 = -9999, 9999
        self.LRange:float = x0
        self.URange:float = x1
        return self

    def set_boundary_borders(self, borders):
        '''Set boundary borders.'''
        if borders:
            lower_border, upper_border = borders
        else:
            lower_border, upper_border = None, None
        self._LBorder:Border = lower_border # left border, or top border
        self._UBorder:Border = upper_border # right border, or bottom border
        return self
    
    def intersect_length(self, border):
        '''Intersection of valid range with given Border instance.'''
        LRange = max(self.LRange, border.LRange)
        URange = min(self.URange, border.URange)
        return max(URange-LRange, 0.0)

    @property
    def centerline(self):
        raise NotImplementedError

    def to_rect(self):
        '''COnvert to Rectangle instance.'''
        centerline = self.centerline
        bbox = expand_centerline(centerline[0:2], centerline[2:], width=self.width)

        # create Rectangle instance
        rect = Rectangle({'color': self.color}).update(bbox)
        rect.type = RectType.BORDER # set border style
        
        return rect


class HBorder(Border):

    def __init__(self, border_range:tuple=None, borders:tuple=None):
        '''Horizontal border -> to determin y-coordinate.'''
        super().__init__(border_range, borders)
        self._y = None
    
    @property
    def y(self):
        ''' y-coordinate of horizontal border. Average value if not finalized.'''
        return self._y if self.finalized else (self.LRange+self.URange)/2.0

    @property
    def centerline(self):
        '''Center line of this border.'''
        return (self._LBorder.x, self.y, self._UBorder.x, self.y)

    def finalize(self, y:float):
        ''' Finalize border with given position.'''
        # can be finalized only one time
        if self.finalized or not self.is_valid(y): return self
        self._y = y
        self.finalized = True
        return self

    def finalize_by_rect(self, h_rect:Rectangle):
        ''' Finalize border with specified horizontal rect, which is generally a showing border.        
            NOTE: the boundary borders may also be affected by this rect.
        '''
        bbox = h_rect.bbox
        y = (bbox.y0+bbox.y1)/2.0

        # skip if no intersection in y-direction
        if self.finalized or not self.is_valid(y): return self

        # skip if no intersection in x-ditrection
        if bbox.x1 <= self._LBorder.LRange or bbox.x0 >= self._UBorder.URange: return self

        # now, it can be used to finalize current border
        self.finalize(y)
        self.color = h_rect.color
        self.width = bbox.y1 - bbox.y0

        # and, try to finalize boundary borders
        self._LBorder.finalize(bbox.x0)
        self._UBorder.finalize(bbox.x1)

        return self


class VBorder(Border):

    def __init__(self, border_range:tuple=None, borders:tuple=None):
        '''Vertical border -> to determin x-coordinate.'''
        super().__init__(border_range, borders)
        self._x = None

    @property
    def x(self):
        ''' x-coordinate of vertical border. Average value if not finalized.'''
        return self._x if self.finalized else (self.LRange+self.URange)/2.0

    @property
    def centerline(self):
        '''Center line of this border.'''
        return (self.x, self._LBorder.y, self.x, self._UBorder.y)  
    
    def finalize(self, x:float):
        '''Finalize border with given position.'''
        # can be finalized fo only one time
        if self.finalized or not self.is_valid(x): return self
        self._x = x
        self.finalized = True
        return self
    
    def finalize_by_rect(self, v_rect:Rectangle):
        ''' Finalize border with specified horizontal rect, which is generally a showing border.        
            NOTE: the boundary borders may also be affected by this rect.
        '''
        bbox = v_rect.bbox
        x = (bbox.x0+bbox.x1)/2.0

        # skip if no intersection in y-direction
        if self.finalized or not self.is_valid(x): return self

        # skip if no intersection in x-ditrection
        if bbox.y1 <= self._LBorder.LRange or bbox.y0 >= self._UBorder.URange: return self

        # now, it can be used to finalize current border
        self.finalize(x)
        self.color = v_rect.color
        self.width = bbox.x1 - bbox.x0

        # and, try to finalize boundary borders
        self._LBorder.finalize(bbox.y0)
        self._UBorder.finalize(bbox.y1)

        # update rect type as table border
        v_rect.type = RectType.BORDER

        return self


class Borders:
    '''Collection of Border instances.'''
    def __init__(self):
        ''' Init collection with empty borders.'''
        self._HBorders = [] # type: list[HBorder]
        self._VBorders = [] # type: list[VBorder]

        # overlap between valid h-border ranges
        self._dy_max, self._dy_min = 0.0, 0.0

        # overlap between valid v-border ranges
        self._dx_max, self._dx_min = 0.0, 0.0

    def __iter__(self):
        return (instance for instance in self._HBorders+self._VBorders)

    def __len__(self):
        return len(self._HBorders) + len(self._VBorders)
    

    def add(self, border:Border):
        '''Add border and update '''
        if isinstance(border, HBorder):
            # check intersection with contained h-borders
            d_max, d_min = self._max_min_intersects(self._HBorders, border)
            if d_max is not None:
                self._dy_max = d_max
                self._dy_min = d_min
            self._HBorders.append(border)
        
        elif isinstance(border, VBorder):
            # check intersection with contained v-borders
            d_max, d_min = self._max_min_intersects(self._VBorders, border)
            if d_max is not None:
                self._dx_max = d_max
                self._dx_min = d_min
            self._VBorders.append(border)
    

    def extend(self, borders:list):
        for border in borders: self.add(border)

    @property
    def HBorders(self): return self._HBorders

    @property
    def VBorders(self): return self._VBorders

    def finalize(self, rects:Rectangles):
        ''' Finalize the position of all borders: to align h-borders or v-borders as more as possible,
            so to simplify the table structure.
            ---
            Args:
            - rects: a group of explicit border rects. Stream table borders should follow these borders.
        '''
        # process h- and v- rects respectively
        h_rects = list(filter(
            lambda rect: rect.bbox.width >= rect.bbox.height <= MAX_W_BORDER, rects))
        for rect in h_rects:
            for border in self._HBorders:            
                border.finalize_by_rect(rect)

        v_rects = list(filter(
            lambda rect: rect.bbox.height > rect.bbox.width <= MAX_W_BORDER, rects))
        for rect in v_rects:
            for border in self._VBorders:            
                border.finalize_by_rect(rect)        

        # process un-finalized h-borders further
        borders = list(filter(lambda border: not border.finalized, self._HBorders))
        self._finalize_borders(borders, self._dy_min, self._dy_max)

        # process un-finalized v-borders further
        borders = list(filter(lambda border: not border.finalized, self._VBorders))
        self._finalize_borders(borders, self._dx_min, self._dx_max)

    
    @staticmethod
    def _max_min_intersects(borders, border:Border):
        '''Get max/min intersection between `borders` and `border`. Return None if no any intersections.'''
        intersects = list(map(
            lambda border_: border_.intersect_length(border), borders))
        intersects = list(filter(
            lambda border_: border_>0, intersects
        ))
        if intersects:
            return max(intersects), min(intersects)
        else:
            return None, None


    @staticmethod
    def _finalize_borders(borders:list, dx_min:float, dx_max:float):
        ''' Finalize the position of all borders: align borders as more as possible to simplify the table structure.
            ---
            Args:
            - borders: a list of HBorder or VBorder instances
            - dx_min : minimum length of intersected border range
            - dx_max : maximum length of intersected border range
            
            Taking finalizing vertical borders for example:
            - for each border, initialize a group of x-coordinates with spacing `dx` in its valid range
            - for each x-coordinate, count the intersection status with all borders
            - merge x-coordinates (using average value) passing through same borders
            - sort x-coordinates with the count of intersections in decent order
            - finalize borders with x-coordinate in sorting order consequently
            - terminate the process when all borders are finalized
        '''
        # no intersection exists for any borders -> it can be finalized right now.
        if dx_max == 0.0: return

        # resolution 
        dx = dx_min / 2.0

        # initialize vertical lines and check intersection status
        x_status = {} # coordinate -> status
        for border in borders:
            x = border.LRange+dx
            while x < border.URange:
                # intersection status with each border
                c = list(map(
                    lambda border: str(int(border.is_valid(x))), borders))
                x_status[x] = '-'.join(c) # e.g. 1-0-0-1-0-0

                x += dx

        # merge vertical lines if its intersection status is same
        merged_x_status = {} # status -> coordinate
        for k, v in x_status.items():
            if v in merged_x_status:
                merged_x_status[v].append(k)
            else:
                merged_x_status[v] = [k]
        
        # merge vertical lines with average x-coordinates, and
        # calculate the count of intersected borders for merged lines
        data = []
        for k, v in merged_x_status.items():
            # average coordinate
            x = sum(v)/len(v)
            c = list(map(float, k.split('-')))
            data.append((x, c))
        
        # sort per count since preferring the position of line passing through more borders
        data.sort(key=lambda item: (sum(item[1]), item[0]), reverse=True)

        # finalize borders
        num = len(borders)
        current_status = [0] * num
        for x, status in data:
            # terminate if all borders are finalized
            if sum(current_status) == num: break

            # only one line is allowed to pass through one border range -> sum(A.*B)=0
            #  e.g. A = [1,0,1,0], B=[0,1,0,0] -> valid
            #       A = [1,0,1,0], B =[1,0,0,0] -> invalid due to two lines passing through border 1
            duplicated = sum([c1*c2 for c1,c2 in zip(current_status, status)])
            if duplicated: continue

            # update current status
            current_status = [c1+c2 for c1,c2 in zip(current_status, status)]

            # now, finalize borders
            for border, border_status in zip(borders, status):
                if border_status: border.finalize(x)