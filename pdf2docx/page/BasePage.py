'''Base page with basic properties, e.g. width, height and margin.'''

class BasePage:
    def __init__(self, width:float=0.0, height:float=0.0, margin:tuple=None):
        '''Initialize page layout.

        Args:
            width (float, optional): Page width. Defaults to 0.0.
            height (float, optional): Page height. Defaults to 0.0.
            margin (tuple, optional): Page margin. Defaults to None.
        '''
        # page size and margin
        self.width = width
        self.height = height
        self.margin = margin or (0,) * 4
    

    @property
    def bbox(self): return (0.0, 0.0, self.width, self.height)


    @property
    def working_bbox(self):
        '''bbox with margin considered.'''
        x0, y0, x1, y1 = self.bbox
        L, R, T, B = self.margin
        return (x0+L, y0+T, x1-R, y1-B)