# -*- coding: utf-8 -*-

'''
Table block object parsed from raw image and text blocks.
@created: 2020-07-22
@author: train8808@gmail.com
---

{
    'type': 3, # or 4 for implicit table
    'bbox': (x0, y0, x1, y1),
    'cells': [[
        {
            'bbox': (x0, y0, x1, y1),
            'border_color': (sRGB,,,), # top, right, bottom, left
            'bg_color': sRGB,
            'border_width': (,,,),
            'merged_cells': (x,y), # this is the bottom-right cell of merged region: x rows, y cols
            'blocks': [
                text blocks
            ]
        }, # end of cell

        None,  # merged cell

        ...,   # more cells
    ], # end of row

    ...] # more rows    
}

'''

from ..common.Block import Block


class TextBlock(Block):

    def plot(self, page, block, style=True, content=True):
        '''Plot table block, i.e. cell/line/span, in PDF page.'''
        for rows in block['cells']:
            for cell in rows:
                # ignore merged cells
                if not cell: continue            
                
                # plot cell style
                if style:
                    # border color and width
                    bc = [x/255.0 for x in utils.RGB_component(cell['border-color'][0])]
                    w = cell['border-width'][0]

                    # shading color
                    if cell['bg-color'] != None:
                        sc = [x/255.0 for x in utils.RGB_component(cell['bg-color'])] 
                    else:
                        sc = None
                    page.drawRect(cell['bbox'], color=bc, fill=sc, width=w, overlay=False)
                
                # or just an illustration
                else:
                    bc = (1,0,0) if is_explicit_table_block(block) else (0.6,0.7,0.8)
                    page.drawRect(cell['bbox'], color=bc, fill=None, width=1, overlay=False)

                # plot blocks in cell
                if content:
                    for cell_block in cell['blocks']:
                        _plot_text_block(page, cell_block)