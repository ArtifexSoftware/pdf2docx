import fitz
import re
from functools import cmp_to_key
from translation_engine import google_translate
import util


class PDFReader:
    def __init__(self, file_path):
        self.doc = fitz.open(file_path)

    def raw_layout(self, page_num=0):
        page = self.doc[page_num]
        layout = page.getText('dict')
        # reading order: from top to bottom, from left to right
        layout['blocks'].sort(key=lambda block: (block['bbox'][1], block['bbox'][0]))
        return layout


class PDFParser:

    @staticmethod
    def page_layout(layout):
        '''page layout process:
            - merge lines in block to a complete sentence
            - split block with multi-lines into seperated blocks
            - merge blocks to further complete sentence
        '''

        # merge lines in block
        layout = PDFParser.merge_lines(layout)

        # split blocks
        layout = PDFParser.split_blocks(layout)

        # detect table here
        # TODO

        # merge blocks
        layout = PDFParser.merge_blocks(layout)

        return layout

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

    @staticmethod
    def merge_lines(layout):
        '''a completed pragraph is divied with lines in PDF reader,
           so this method try to combine associated lines in a block into a paragraph
        '''
        for block in layout['blocks']:
            # skip image block
            if block['type']==1:
                continue

            # sort lines: align left
            lines = block['lines']
            lines.sort(key=cmp_to_key(PDFParser.__cmp_align_vertical))

            # group by left boundary if text is in horizontal direction
            # group by top boundary if text is in vertical direction
            # remove duplicated at the same time
            ref, groups = lines[0], [[lines[0]]]
            for line in lines:
                if util.is_vertical_aligned(ref['bbox'], line['bbox'], ref['dir']==(1.0, 0.0)):                   
                    if abs(ref['bbox'][1]-line['bbox'][1]) < util.DM: # duplicated line
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
                temp_span['text'] = ''.join(map(PDFParser.__process_line, spans))
                temp_line['spans'] = temp_span

                # done for a block
                combined_lines.append(temp_line)

            # detect bullet:
            # - two sets in one line
            # - the first set contains 1 or 2 char
            # - the gap between them should not larger than the max length  of them
            if len(combined_lines)==2:
                line1, line2 = combined_lines
                max_length = max(line1['bbox'][2]-line1['bbox'][0], line2['bbox'][2]-line2['bbox'][0])
                margin_left = line2['bbox'][0]-line1['bbox'][2]
                if (util.is_horizontal_aligned(line1['bbox'], line2['bbox'], line1['dir']==(1.0,0.0)) and 
                    margin_left<max_length and 
                    len(line1['spans']['text'].strip())<3 ):
                    line = line2.copy()
                    line['wmode'] = 1 # bullet
                    line['mark'] = line1['spans']['text'].strip() + ' '
                    line['bbox'] = block['bbox']
                    combined_lines = [line]

            block['lines'] = combined_lines

        return layout

    @staticmethod
    def split_blocks(layout):
        '''split block with multi-lines into single line block,
           which will be used to merge block in next step
        '''
        blocks = []
        for block in layout['blocks']:
            if block['type']==1:
                blocks.append(block)
                continue
            lines = block['lines']
            if len(lines) > 1:
                for line in lines:
                    splited_block = {
                        'type': block['type'],
                        'bbox': line['bbox'],
                        'lines': [line]
                    }
                    blocks.append(splited_block)
            else:
                blocks.append(block)
        layout['blocks'] = blocks
        return layout

    @staticmethod
    def merge_blocks(layout):
        '''a sentence may be seperated in different blocks, so this step is to merge them back
           - previous line is not the end and current line is not the begin
           - skip if current line is a bullet item
           - suppose pragraph margin is larger than line margin
        '''
        merged_blocks = []
        ref = None
        ref_margin = 0.0
        for block in layout['blocks']:
            if block['type']==1:
                merged_blocks.append(block)
                continue

            merged = False

            if not ref or not ref['lines'][0]['spans']['text'].strip() or not block['lines'][0]['spans']['text'].strip():
                merged_blocks.append(block)
            else:
                dx = block['bbox'][0]-ref['bbox'][0]
                dy = block['bbox'][1]-ref['bbox'][3]
                w = ref['bbox'][2]-ref['bbox'][0]
                h = ref['bbox'][3]-ref['bbox'][1]

                if abs(dx) >= w or abs(dy)>=h:                   
                    merged_blocks.append(block)
                elif block['lines'][0]['wmode']==1: # bullet item
                    merged_blocks.append(block)
                else:
                    text1 = ref['lines'][0]['spans']['text']
                    text2 = block['lines'][0]['spans']['text']

                    if abs(dy-ref_margin)<util.DM or (not util.is_end_sentence(text1) and not util.is_start_sentence(text2)):
                        merged = True
                        # combine block to ref
                        left = min(block['bbox'][0], ref['bbox'][0])
                        right = max(block['bbox'][2], ref['bbox'][2])
                        top = min(block['bbox'][1], ref['bbox'][1])
                        bottom = max(block['bbox'][3], ref['bbox'][3])
                        merged_blocks[-1]['bbox'] = (left, top, right, bottom)
                        merged_blocks[-1]['lines'][0]['bbox'] = (left, top, right, bottom)
                        merged_blocks[-1]['lines'][0]['spans']['text'] += block['lines'][0]['spans']['text']
                        
                    else:
                        merged_blocks.append(block)                    

            # update reference line margin if merged
            ref_margin = dy if merged else 0.0

            # update reference block
            ref = merged_blocks[-1]

        layout['blocks'] = merged_blocks
        return layout

    @staticmethod
    def plot_layout(axis, layout):
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
        L, R, T, B = PDFParser.page_margin(layout)
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
    def __cmp_align_vertical(set1, set2):
        '''sort set (blocks or lines in block) with top-left point: vertical to text direction.
           an ideal solution:
                lines.sort(key=lambda line: (line['bbox'][0], line['bbox'][1]))
           but two approximate but not definitely equal values should be also considered as equal in this case
        '''
        if set1.get('dir', (1.0, 0.0))==(1.0, 0.0): # reading direction: x
            L1 = set1['bbox'][2]-set1['bbox'][0]
            L2 = set2['bbox'][2]-set2['bbox'][0]
            L = max(set1['bbox'][2], set2['bbox'][2]) - min(set1['bbox'][0], set2['bbox'][0])
            h = set1['bbox'][1]-set2['bbox'][1]
            dm = set1['bbox'][0] - set2['bbox'][0]
        else:
            L1 = set1['bbox'][3]-set1['bbox'][1]
            L2 = set2['bbox'][3]-set2['bbox'][1]
            L = max(set1['bbox'][3], set2['bbox'][3]) - min(set1['bbox'][1], set2['bbox'][1])
            h = set1['bbox'][0]-set2['bbox'][0]
            dm = set1['bbox'][1]-set2['bbox'][1]

        if L1+L2>L: # vertically align
            if abs(h) < util.DM:
                return 0
            else:
                return -1 if h<0 else 1
        else:
            return -1 if dm<0 else 1

    @staticmethod
    def __process_line(span):
        '''combine text in lines'''
        text = span['text']
        if text.endswith(('‐', '-')): # these two '-' are not same
            text = text[0:-1]
        elif not text.endswith(' '):
            text += ' '
        return text


if __name__ == '__main__':

    import matplotlib.pyplot as plt
   
    pdf_file = 'D:/11_Translation_Web/pdf2word/case.pdf'
    # pdf_file = 'D:/WorkSpace/TestSpace/PDFTranslation/examples/example.pdf'    

    doc = PDFReader(pdf_file)
    page_num = 153

    ax1 = plt.subplot(121)
    ax2 = plt.subplot(122)
    
    layout1 = doc.raw_layout(page_num)
    PDFParser.plot_layout(ax1, layout1)

    layout2 = PDFParser.page_layout(layout1)
    PDFParser.plot_layout(ax2, layout2)

    plt.show()

    # get combined text
    for block in layout2['blocks']:
        if block['type']==1: continue
        for line in block['lines']:
            if line['wmode']==1:
                print(line['mark'], line['spans']['text'])
            else:
                print(line['spans']['text'])             
            print()
        print('======================')




    
