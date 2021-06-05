# -*- coding: utf-8 -*-

'''Module to determin stream table borders.

Though no exact borders exist for stream table, it's better to simplify table structure by
aligning borders as more as possible. Taking vertical borders for example, it can be moved 
in a valid range in horizontal direction, but restricted by top and bottom borders in vertical 
direction. It's also true for horizontal borders.

Accordingly, introduce ``Border`` object, which has the following attributes:

* Valid range, e.g. ``(100, 250)``;
* Boundary borders, e.g. ``(top_border, bottom_border)`` for v-border,
  or ``(left_border, right_border)`` for h-border.

The target is to finalize the position in valid range, e.g. ``x=125`` for v-border with valid range 
``(120, 250)``. Then it's y-direction is determined by its boundary borders, where the y-coordinates 
are finalized in same logic. Finally, this border is fixed since both x- and y- directions are 
determined.

.. note::
    Consider horizontal and vertical borders only.
'''

from collections import defaultdict
from ..shape.Shapes import Shapes
from ..shape.Shape import Stroke
from ..common import constants
from ..common.share import RectType, rgb_value
from ..common.Collection import BaseCollection


class Border:
    '''Border for stream table.'''

    def __init__(self, border_type='hi', border_range:tuple=None, borders:tuple=None, reference:bool=False):
        '''Border for stream table.
        
        Args:
            border_type (str): border orientation/position, e.g. 'hi' represents horizontal inner border.
                * ``h/v``       - horizontal/vertical border;
                * ``t/b/l/r/i`` - outer border (top/bottom/left/right), or inner border
            border_range (tuple): Valid range, e.g. ``(x0, x1)`` for vertical border.
            borders (tuple): Boundary borders in ``Border`` type, e.g. 
                * top and bottom horizontal borders for current vertical border; 
                * left and right vertical borders for current horizontal border. 
            reference (bool): Reference border will not convert to real table border.
        '''
        # border type
        self.border_type = border_type.upper()

        # Whether the MAIN dimension (e.g. the vertical position for H-border) is determined.
        # NOTE: the other dimension (e.g. the left/right position for H-border) is determined 
        # by boundary borders, so a border is fully determined on condition that:
        # - it is finalized, 
        # - AND the boundary borders are also finalized. 
        self.finalized = False

        # Whether reference only border.
        self.is_reference = reference

        # valid range
        self.set_border_range(border_range)

        # boundary borders
        self.set_boundary_borders(borders)

        # the position to be finalized, e.g. y-coordinate for horizontal border
        self._value = None
        
        # border style
        self.width = constants.HIDDEN_W_BORDER
        self.color = 0 # black by default
        

    @property
    def is_horizontal(self): return 'H' in self.border_type

    @property
    def is_vertical(self): return 'V' in self.border_type

    @property
    def is_top(self): return 'T' in self.border_type

    @property
    def is_bottom(self): return 'B' in self.border_type

    @property
    def value(self):
        '''Finalized position, e.g. y-coordinate of horizontal border. 

        Average value if not finalized, but close to the table side for top and bottom 
        boundary borders.
        '''
        if self.finalized:
            return self._value
        else:
            avg = (self.LRange+self.URange)/2.0
            if self.is_top:
                return max(self.URange-3, avg)
            elif self.is_bottom:
                return min(self.LRange+3, avg)
            else:
                return avg

    @property
    def centerline(self):
        '''Center line of this border.'''
        if self.is_horizontal:
            return (self._LBorder.value, self.value, self._UBorder.value, self.value)
        else:
            return (self.value, self._LBorder.value, self.value, self._UBorder.value)


    def is_valid(self, value:float):
        '''Whether the given position locates in the valid border range.

            Args:
                value (float): Target position.
            
            Returns:
                bool: Valid position or not.
        '''
        # consider margin here, but pay attention to underline which may be counted
        return (self.LRange-constants.MINOR_DIST) <= value <= (self.URange+constants.MINOR_DIST) 


    def set_border_range(self, border_range:tuple=None):
        """Set border valid ranges.

        Args:
            border_range (tuple, optional): Lower/upper range to set. Defaults to None.

        Returns:
            Border: self
        """ 
        if border_range:
            x0, x1 = border_range
        else:
            x0, x1 = -9999, 9999
        self.LRange:float = x0
        self.URange:float = x1
        return self


    def set_boundary_borders(self, borders:tuple=None):
        """Set boundary borders.

        Args:
            borders (tuple, optional): Lower/upper boundary borders to set. Defaults to None.

        Returns:
            Border: self
        """
        if borders:
            lower_border, upper_border = borders
        else:
            lower_border, upper_border = None, None
        self._LBorder:Border = lower_border # left border, or top border
        self._UBorder:Border = upper_border # right border, or bottom border
        return self


    def get_boundary_borders(self):
        '''Get boundary borders.

        Returns:
            tuple: ``(lower b-border, upper b-border)``
        '''
        return (self._LBorder, self._UBorder)


    def finalize_by_value(self, value:float):
        '''Finalize border with given position.

        Args:
            value (float): Target position.
        '''
        # can be finalized only one time
        if self.finalized or not self.is_valid(value): return False

        self._value = value
        self.finalized = True
        self.is_reference = False

        return True


    def finalize_by_stroke(self, stroke:Stroke):
        '''Finalize border with specified stroke shape, which is generally a showing border-like shape.

        Args:
            stroke (Stroke): Target stroke to finalize this border.

        .. note::
            * The boundary borders may also be affected by this stroke shape.
            * The border-like stroke may be an underline or strike-through.      
        '''
        # NOTE: don't do this: `if self.finalized: continue`, 
        # because `self.finalized` just determed the main dimension, still need a chance to determin 
        # the other dimension.         

        if self.is_horizontal:
            # x0, x1, and y of h-stroke
            low_pos, upper_pos = stroke.x0, stroke.x1
            value = stroke.y0 # equal to stroke.y1
        else:
            # y0, y1 and x of v-stroke
            low_pos, upper_pos = stroke.y0, stroke.y1
            value = stroke.x0 # equal to stroke.x1

        # skip if not in valid range of a border
        if not self.is_valid(value): return

        # skip if not span in the border direction
        if low_pos > self._LBorder.URange and upper_pos < self._UBorder.LRange: return

        # now, finalize current border
        # NOTE: set border properties only if finalized by value successfully
        if self.finalize_by_value(value):
            self.color = stroke.color
            self.width = stroke.width
            stroke.type = RectType.BORDER  # update rect type as table border

        # and, give a chance to finalize boundary borders no matter this border is finalized or not,
        self._LBorder.finalize_by_value(low_pos)
        self._UBorder.finalize_by_value(upper_pos)


    def to_stroke(self):
        '''Convert to border stroke.'''
        # ignore if reference only
        if self.is_reference: return None

        stroke = Stroke({'color': self.color, 'width': self.width}).update_bbox(self.centerline)
        stroke.type = RectType.BORDER # set border style        
        return stroke


class Borders(BaseCollection):
    '''Collection of ``Border`` instances.'''

    def finalize(self, strokes:Shapes, fills:Shapes):
        '''Finalize the position of all borders.
        
        Args:
            strokes (Shapes): A group of explicit border strokes.
            fills (Shapes): A group of explicit cell shadings.

        .. note::
            A border is finalized in priority below:
            
            * Follow explicit stroke/border.
            * Follow explicit fill/shading.
            * Align h-borders or v-borders as more as possible to simplify the table structure.            
        '''
        # add dummy borders to be finalized by explicit strokes/fillings
        self._add_full_dummy_borders()

        # finalize borders by explicit strokes in first priority
        self._finalize_by_strokes(strokes)

        # finalize borders by explicit fillings in second priority
        tmp_strokes = []
        for fill in fills:
            # ignore determined filling or filling in white bg-color
            if fill.is_determined or fill.color == rgb_value((1,1,1)): continue

            x0, y0, x1, y1 = fill.bbox
            tmp_strokes.extend([
                Stroke().update_bbox((x0, y0, x1, y0)), # top
                Stroke().update_bbox((x0, y1, x1, y1)), # bottom
                Stroke().update_bbox((x0, y0, x0, y1)), # left
                Stroke().update_bbox((x1, y0, x1, y1))  # right
            ])
        self._finalize_by_strokes(tmp_strokes)

        # finalize borders by their layout finally (use an average position):
        # - un-finalized, and
        # - not reference-only borders        
        borders = list(filter(lambda border: not (border.finalized or border.is_reference), self._instances))

        # h-borders
        # NOTE: exclude the top and bottom boundary borders, since they'll be adjusted by
        # principle that minimizing the table region.
        h_borders = list(filter(
            lambda border: border.is_horizontal and 
                    not (border.is_top or border.is_bottom), borders))
        self._finalize_by_layout(h_borders)

        # v-borders
        v_borders = list(filter(lambda border: border.is_vertical, borders))
        self._finalize_by_layout(v_borders)

    
    def _finalize_by_strokes(self, strokes:list):
        '''Finalize borders by explicit strokes.'''
        for stroke in strokes:
            if stroke.is_determined: continue
            
            for border in self._instances:
                # horizontal stroke can finalize horizontal border only
                if stroke.horizontal != border.is_horizontal: continue
                
                border.finalize_by_stroke(stroke)                


    @staticmethod
    def _finalize_by_layout(borders:list):
        '''Finalize the position of all borders: 
        align borders as more as possible to simplify the table structure.

        Taking finalizing vertical borders for example:

        * initialize a list of x-coordinates, ``[x0, x1, x2, ...]``, with the interval points of each border
        * every two adjacent x-coordinates forms an interval for checking, ``[x0, x1]``, ``[x1, x2]``, ...
        * for each interval, count the intersection status of center point, ``x=(x0+x1)/2.0``, with all borders
        * sort center point with the count of intersections in decent order
        * finalize borders with x-coordinate of center points in sorting order consequently
        * terminate the process when all borders are finalized
        
        Args:
            borders (list): A list of ``Border`` instances.
        '''
        # collect interval points and sort in x-increasing order
        x_points = set()
        for border in borders:
            x_points.add(border.LRange)
            x_points.add(border.URange)
        
        x_points = list(x_points)
        x_points.sort()

        # check intersection status of each intervals
        x_status = [] # [(x, status), ...]
        for i in range(len(x_points)-1):
            x = (x_points[i]+x_points[i+1])/2.0 # cenper point
            s = [int(border.is_valid(x)) for border in borders]
            x_status.append((x,s))
            
        # sort per count since preferring passing through more borders
        x_status.sort(key=lambda item: sum(item[1]), reverse=True)

        # finalize borders
        num = len(borders)
        current_status = [0] * num
        for x, status in x_status:
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
                if border_status: border.finalize_by_value(int(x))


    def _add_full_dummy_borders(self):
        '''Add reference borders to build full lattices.
        
        The original borders extracted from contents may be not able to represent the real 
        structure. Then, the reference borders has a chance to be finalized by explicit stroke 
        or fillings::

           +-------+---------+----------+
           +-------+---------+          +  <- shading in the first row, but not represented
           +-------+---------+          +  <- empty in these cells, so no borders extracted
           +-------+---------+----------+

        Add two dummy borders to form full lattices::

           +-------+---------+----------+
           +-------+---------+~~~~~~~~~~+  <- dummy borders
           +-------+---------+~~~~~~~~~~+
           +-------+---------+----------+
        '''
        h_borders = list(filter(lambda border: border.is_horizontal, self._instances))
        v_borders = list(filter(lambda border: border.is_vertical, self._instances))

        # group h-borders
        raw_borders_map = defaultdict(list)
        h_range_set = set()
        for border in h_borders:
            h_range = (border.LRange, border.URange)
            h_range_set.add(h_range)
            raw_borders_map[border.get_boundary_borders].append(h_range)

        # sort v-borders and try to add dummy h-borders between adjacent v-borders
        v_borders.sort(key=lambda border: border.value)
        for i in range(len(v_borders)-1):
            left, right = v_borders[i], v_borders[i+1]
            left_l_border, left_u_border = left.get_boundary_borders()
            right_l_border, right_u_border = right.get_boundary_borders()

            # the candidate v-borders must be connected
            if left_l_border!=right_l_border and left_u_border!=right_u_border: continue

            # get valid range
            lower_bound = max(left_l_border.LRange, right_l_border.LRange)
            upper_bound = min(left_u_border.URange, right_u_border.URange)

            # add dummy border if not exist
            raw_borders = raw_borders_map.get((left,right), []) # existed borders
            for h_range in h_range_set:
                # ignore if existed
                if h_range in raw_borders: continue

                # dummy border must in valid range
                if h_range[0]>upper_bound or h_range[1]<lower_bound: continue

                h_border = Border('HI', h_range, (left, right), reference=True)
                self._instances.append(h_border)
