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

'''


from ..shape.Shapes import Shapes
from ..shape.Shape import Stroke
from ..common import constants
from ..common.share import RectType


class Border:

    def __init__(self, border_type='h', border_range:tuple=None, borders:tuple=None, reference:bool=False):
        '''Border for stream table.
            ---
            Args:
            - border_type: 'h' - horizontal border; 'v' - vertical border
            - border_range: valid range, e.g. (x0, x1) for vertical border
            - borders: boundary borders, e.g. top and bottom horizontal borders for current vertical border; 
            left and right vertical borders for current horizontal border. 
            - reference: reference Border is used to show a potential case, which converts to table border when finalized;
            otherwise, it is ignored.
            
        '''
        # border type
        self.is_horizontal = border_type.upper()=='H'
        self.finalized = False        # whether the position is determined
        self.is_reference = reference # whether reference only border

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
    def value(self):
        ''' Finalized position, e.g. y-coordinate of horizontal border. Average value if not finalized.'''
        return self._value if self.finalized else (self.LRange+self.URange)/2.0


    @property
    def centerline(self):
        '''Center line of this border.'''
        if self.is_horizontal:
            return (self._LBorder.value, self.value, self._UBorder.value, self.value)
        else:
            return (self.value, self._LBorder.value, self.value, self._UBorder.value)


    def is_valid(self, value:float):
        '''Whether the given position locates in the valid border range.'''
        # consider margin here, but pay attention to underline which may be counted
        return (self.LRange-constants.MINOR_DIST) <= value <= (self.URange+constants.MINOR_DIST) 


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


    def finalize_by_value(self, value:float):
        ''' Finalize border with given position.'''
        # can be finalized only one time
        if self.finalized or not self.is_valid(value): return self

        self._value = value
        self.finalized = True
        self.is_reference = False
        return self


    def finalize_by_stroke(self, stroke:Stroke):
        ''' Finalize border with specified stroke shape, which is generally a showing border-like shape.
             
            NOTE:
            - the boundary borders may also be affected by this stroke shape.
            - border-like stroke may be an underline/strike-through.      
        '''        
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
        self.finalize_by_value(value)
        self.color = stroke.color
        self.width = stroke.width

        # and, try to finalize boundary borders
        self._LBorder.finalize_by_value(low_pos)
        self._UBorder.finalize_by_value(upper_pos)

        # update rect type as table border
        stroke.type = RectType.BORDER


    def to_stroke(self):
        '''Convert to border stroke.'''
        # ignore if reference only
        if self.is_reference: return None

        stroke = Stroke({'color': self.color, 'width': self.width}).update_bbox(self.centerline)
        stroke.type = RectType.BORDER # set border style        
        return stroke


class HBorder(Border):
    def __init__(self, border_range:tuple=None, borders:tuple=None, reference:bool=False):
        '''Horizontal border.'''
        super().__init__('h', border_range, borders, reference)


class VBorder(Border):
    def __init__(self, border_range:tuple=None, borders:tuple=None, reference:bool=False):
        '''Vertical border.'''
        super().__init__('v', border_range, borders, reference)


class Borders:
    '''Collection of Border instances.'''
    def __init__(self):
        ''' Init collection with empty borders.'''
        self._instances = [] # type: list[Border]


    def __iter__(self):
        return (instance for instance in self._instances)

    def __len__(self):
        return len(self._instances)
    

    def add(self, border:Border): self._instances.append(border)
    

    def extend(self, borders:list): self._instances.extend(borders)


    def finalize(self, strokes:Shapes, fills:Shapes):
        ''' Finalize the position of all borders:
            - follow explicit stroke/border
            - follow explicit fill/shading
            - align h-borders or v-borders as more as possible to simplify the table structure.
            ---
            Args:
            - strokes: a group of explicit border strokes.
            - fills: a group of explicit cell shadings.
        '''
        # finalize borders by explicit strokes in first priority
        self._finalize_by_strokes(strokes)

        # finalize borders by explicit fillings in second priority
        tmp_strokes = []
        for fill in fills:
            if fill.is_determined: continue

            x0, y0, x1, y1 = fill.bbox
            tmp_strokes.extend([
                Stroke().update_bbox((x0, y0, x1, y0)), # top
                Stroke().update_bbox((x0, y1, x1, y1)), # bottom
                Stroke().update_bbox((x0, y0, x0, y1)), # left
                Stroke().update_bbox((x1, y0, x1, y1))  # right
            ])
        self._finalize_by_strokes(tmp_strokes)

        # finalize borders by their layout finally:
        # - un-finalized, and
        # - not reference-only borders        
        borders = list(filter(lambda border: not (border.finalized or border.is_reference), self._instances))

        #  h-borders
        h_borders = list(filter(lambda border: border.is_horizontal, borders))
        self._finalize_by_layout(h_borders)

        # v-borders
        v_borders = list(filter(lambda border: not border.is_horizontal, borders))
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
        ''' Finalize the position of all borders: align borders as more as possible to simplify the table structure.
            ---
            Args:
            - borders: a list of HBorder or VBorder instances
            
            Taking finalizing vertical borders for example:
            - initialize a list of x-coordinates, [x0, x1, x2, ...], with the interval points of each border
            - every two adjacent x-coordinates forms an interval for checking, [x0, x1], [x1, x2], ...
            - for each interval, count the intersection status of center point, x=(x0+x1)/2.0, with all borders
            - sort center point with the count of intersections in decent order
            - finalize borders with x-coordinate of center points in sorting order consequently
            - terminate the process when all borders are finalized
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
            s = list(map(
                    lambda border: int(border.is_valid(x)), borders))
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
                if border_status: border.finalize_by_value(x)