# -*- coding: utf-8 -*-

'''
There's no exact border for stream table, so define a BORDER class with a valid range.
For instance, a vertical border is reasonable when it locates in range (x0, x1). In addition,
it must start from a horizontal border (top) and end with another horizontal border (bottom).
It's also true for horizontal borders.

NOTE:
Consider horizontal and vertical borders only.

@created: 2020-08-29
@author: train8808@gmail.com
'''


from ..shape.Rectangle import Rectangle
from ..common.utils import expand_centerline, RGB_value
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
        
        # border width
        self.width = 0.2

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
            x0, x1 = -1, -1
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
        rect = Rectangle({
            'bbox' : bbox,
            'color': RGB_value((1,1,1)) # white by default
        })
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
        if self.is_valid(y):
            self._y = y
            self.finalized = True
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
        if self.is_valid(x):
            self._x = x
            self.finalized = True
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
            intersects = list(map(
                lambda h_border: h_border.intersect_length(border), self._HBorders))
            if intersects:
                self._dy_max = max(intersects)
                self._dy_min = min(intersects)

            self._HBorders.append(border)
        
        elif isinstance(border, VBorder):
            # check intersection with contained h-borders
            intersects = list(map(
                lambda v_border: v_border.intersect_length(border), self._VBorders))
            if intersects:
                self._dx_max = max(intersects)
                self._dx_min = min(intersects)

            self._VBorders.append(border)
    

    def extend(self, borders:list):
        for border in borders: self.add(border)

    @property
    def HBorders(self): return self._HBorders

    @property
    def VBorders(self): return self.VBorders

    def finalize(self):
        ''' Finalize the position of all borders: to align h-borders or v-borders as more as possible,
            so to simplify the table structure.
        '''
        # 1. Calculate dx: a half of the smallest intersection range
        # self._finalize_borders(self._HBorders, self._dy_min, self._dy_max)
        # self._finalize_borders(self._VBorders, self._dx_min, self._dx_max)
        pass


    @staticmethod
    def _finalize_borders(borders:list, dx_min:float, dx_max:float):
        ''' Finalize the position of all borders: align borders as more as possible to simplify the table structure.
            ---
            Args:
            - borders: a list of Border instances
            - dx_min : minimum length of intersected border range
            - dx_max : maximum length of intersected border range
            
            Taking finalizing vertical borders for example:
            1. initialize a group of vertical lines (space dx) from valid range of each v-border
            2. count the intersection with valid range of v-borders for each line
            3. merge vertical lines going through same v-borders
            4. sort vertical lines with the count of intersections with v-borders
            5. finalize v-borders with x-coordinate of the vertical line in sorting order
            6. terminate the process util all v-borders are finalized
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