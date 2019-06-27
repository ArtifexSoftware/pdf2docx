import fitz
import re
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from functools import cmp_to_key

import util





class PDFParser:
    def __init__(self, file_path):
        self.doc = fitz.open(file_path)

    def plot_layout(self, layout):
        '''plot page layout for debug'''

        w, h = layout['width'], layout['height']
        blocks = layout['blocks']

        # figure
        fig, ax = plt.subplots(figsize=(5.0, 5*h/w))
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim(0, w)
        ax.set_ylim(0, h)
        ax.xaxis.set_ticks_position('top')
        ax.yaxis.set_ticks_position('left')
        ax.invert_yaxis()
        ax.set_aspect('equal')

        # plot left/right margin
        list_bbox = list(map(lambda x: x['bbox'], blocks))
        L, R, T, B = self.page_margin(layout)
        ax.plot([L, L], [0, h], 'r--', linewidth=0.5)
        ax.plot([R, R,], [0, h], 'r--', linewidth=0.5)
        ax.plot([0, w,], [T, T], 'r--', linewidth=0.5)
        ax.plot([0, w,], [B, B], 'r--', linewidth=0.5)

        # plot block position
        for i, block in enumerate(blocks):
            # lines in current block
            for line in block.get('lines', []):
                patch = util.rectangle(line['bbox'], linecolor='w', fillcolor=util.getColor(i))
                ax.add_patch(patch)

            # block border
            patch = util.rectangle(block['bbox'], linecolor='k')
            ax.add_patch(patch)

        plt.show()

    @staticmethod 
    def cmp_line_align_left(line1, line2):
        '''sort lines with top-left point: smaller left border comes first.
           an ideal solution:
                lines.sort(key=lambda line: (line['bbox'][0], line['bbox'][1]))
           but two approximate but not definitely equal values should be also considered as equal in this case
        '''
        dx = line1['bbox'][0]-line2['bbox'][0]
        if abs(dx) < 1:
            dy = line1['bbox'][1]-line2['bbox'][1]
            if abs(dy) < 1:
                return 0
            else:
                return -1 if dy<0 else 1
        else:
            return -1 if dx<0 else 1

    @staticmethod
    def process_line(span):
        text = span['text']    
        if text.endswith(('‐', '-')): # these two '-' are not same
            text = text[0:-1]
        elif not text.endswith(' '):
            text += ' '
        return text

    @staticmethod
    def page_margin(layout):
        '''get page margin:
           - left: as small as possible in x direction and should not intersect with any other bbox
           - right: MAX(width-left, max(bbox[3]))
           - top: MIN(bbox[1])
           - bottom: MIN(bbox[3])
        '''       

        # check candidates for left margin:
        list_bbox = list(map(lambda x: x['bbox'], layout['blocks']))
        list_bbox.sort(key=lambda x: (x[0], x[2]))
        lm_bbox, num = list_bbox[0], 0
        candidates = []
        for bbox in list_bbox:
            if abs(bbox[0]-lm_bbox[0])<1:
                num += 1
            else:
                candidates.append((lm_bbox, num))            
                num = 1
                if bbox[0] < lm_bbox[2]:
                    break
            lm_bbox = bbox  

        # get left margin which is supported by bboxes as more as possible
        candidates.sort(key=lambda x: x[1], reverse=True)
        left = candidates[0][0][0]

        # right margin
        x_max = max(map(lambda x: x[2], list_bbox))
        width = layout['width']
        right = width-left if width-left > x_max else x_max

        # top/bottom margin
        top = min(map(lambda x: x[1], list_bbox))
        bottom = max(map(lambda x: x[3], list_bbox))

        return left, right, top, bottom

    def page_layout_raw(self, page_num=0):
        page = self.doc[page_num]
        layout = page.getText('dict')
        # reading order: from top to bottom, from left to right
        layout['blocks'].sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
        return layout

    def page_layout_merged_lines(self, page_num=0):
        '''a completed pragraph is divied with lines in PDF reader,
           so this method try to combine associated lines in a block into a paragraph
        '''

        layout = self.page_layout_raw(page_num)

        for block in layout['blocks']:
            # skip image block
            if block['type']==1:
                continue

            # sort lines: align left
            lines = block['lines']
            lines.sort(key=cmp_to_key(self.cmp_line_align_left))

            # group by left boundary, remove duplicated at the same time
            ref, groups = None, []
            for line in lines:
                if ref and abs(line['bbox'][0]-ref['bbox'][0]) < 1:
                    # duplicated line
                    if abs(line['bbox'][1]-ref['bbox'][1]) < 1:
                        continue
                    # line with same left border
                    else:
                        groups[-1].append(line)
                else:
                    # new line set
                    groups.append([line])

                ref = line

            # combined lines:
            # lines in same set are considered as a paragraph
            combined_lines = []
            for group in groups:
                temp_line = group[0].copy()

                # update bbox
                left = min(map(lambda x: x['bbox'][0], group))
                top = min(map(lambda x: x['bbox'][1], group))
                right = max(map(lambda x: x['bbox'][2], group))
                bottom = max(map(lambda x: x['bbox'][3], group))
                temp_line['bbox'] = (left, top, right, bottom)

                # combine spans
                temp_span = group[0]['spans'][0]
                spans = []
                for line in group:
                    spans.extend(line['spans'])
                temp_span['text'] = ''.join(map(self.process_line, spans))
                temp_line['spans'] = temp_span

                # done for a block
                combined_lines.append(temp_line)

            block['lines'] = combined_lines

        return layout

    def page_layout(self):
        pass



if __name__ == '__main__':
   
    pdf_file = 'D:/11_Translation_Web/pdf2word/test.pdf'
    parser = PDFParser(pdf_file)

    # layout0 = parser.page_layout_raw(555)
    # parser.plot_layout(layout0)

    layout = parser.page_layout_merged_lines(0)
    parser.plot_layout(layout)

    # get combined text
    for block in layout['blocks']:
        if block['type']==1: continue
        for line in block['lines']:
            print(line['spans']['text'])
            print()




    
