import fitz
import re
from functools import cmp_to_key
from translation_engine import google_translate
import util





class PDFParser:
    def __init__(self, file_path):
        self.doc = fitz.open(file_path)

    def plot_layout(self, axis, layout):
        '''plot page layout for debug'''

        w, h = layout['width'], layout['height']
        blocks = layout['blocks']

        # plot setting
        axis.set_xticks([])
        axis.set_yticks([])
        axis.set_xlim(0, w)
        axis.set_ylim(0, h)
        axis.xaxis.set_ticks_position('top')
        axis.yaxis.set_ticks_position('left')
        axis.invert_yaxis()
        axis.set_aspect('equal')

        # plot left/right margin
        list_bbox = list(map(lambda x: x['bbox'], blocks))
        L, R, T, B = self.page_margin(layout)
        axis.plot([L, L], [0, h], 'r--', linewidth=0.5)
        axis.plot([R, R,], [0, h], 'r--', linewidth=0.5)
        axis.plot([0, w,], [T, T], 'r--', linewidth=0.5)
        axis.plot([0, w,], [B, B], 'r--', linewidth=0.5)

        # plot block position
        for i, block in enumerate(blocks):
            # lines in current block
            for line in block.get('lines', []):
                patch = util.rectangle(line['bbox'], linecolor='w', fillcolor=util.getColor(i))
                axis.add_patch(patch)

            # block border
            patch = util.rectangle(block['bbox'], linecolor='k')
            axis.add_patch(patch)


    @staticmethod 
    def cmp_line_align_vertical(line1, line2):
        '''sort lines with top-left point: vertical to text direction.
           an ideal solution:
                lines.sort(key=lambda line: (line['bbox'][0], line['bbox'][1]))
           but two approximate but not definitely equal values should be also considered as equal in this case
        '''
        if line1['dir']==(1.0, 0.0): # horizontal
            d1 = line1['bbox'][0]-line2['bbox'][0]
            d2 = line1['bbox'][1]-line2['bbox'][1]
        else:
            d1 = line1['bbox'][1]-line2['bbox'][1]
            d2 = line1['bbox'][0]-line2['bbox'][0]

        if abs(d1) < 1:
            if abs(d2) < 1:
                return 0
            else:
                return -1 if d2<0 else 1
        else:
            return -1 if d1<0 else 1

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
            lines.sort(key=cmp_to_key(self.cmp_line_align_vertical))

            # group by left boundary if text is in horizontal direction
            # group by top boundary if text is in vertical direction
            # remove duplicated at the same time
            ref, groups = lines[0], [[lines[0]]]
            horizontal = ref['dir']==(1.0, 0.0)
            for line in lines:
                d1 = line['bbox'][0]-ref['bbox'][0]
                d2 = line['bbox'][1]-ref['bbox'][1]
                if not horizontal:
                    d1, d2 = d2, d1

                if abs(d1) < 1:                   
                    if abs(d2) < 1: # duplicated line
                        continue
                    else: # line with same left/top border
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

    import matplotlib.pyplot as plt
   
    # pdf_file = 'D:/11_Translation_Web/pdf2word/test.pdf'
    pdf_file = 'D:/WorkSpace/TestSpace/PDFTranslation/examples/case.pdf'
    page_num = 428

    parser = PDFParser(pdf_file)
    layout0 = parser.page_layout_raw(page_num)
    layout = parser.page_layout_merged_lines(page_num)

    ax1 = plt.subplot(121)
    ax2 = plt.subplot(122)
    parser.plot_layout(ax1, layout0)
    parser.plot_layout(ax2, layout)
    plt.show()

    # get combined text
    for block in layout['blocks']:
        if block['type']==1: continue
        for line in block['lines']:
            # print(google_translate(line['spans']['text']))
            print(line['spans']['text'])
            print()




    
