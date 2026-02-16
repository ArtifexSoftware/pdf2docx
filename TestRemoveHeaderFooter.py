# !/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import difflib
from collections import Counter, defaultdict
from pdf2docx import Converter
import os


# pdf转成txt，并且过滤页眉页脚，输出结果以json标准输出打印，不保留中间docx结果。在下面写入pdf文件路径即可。
pdf_file_dir = "./test/samples/demo-pdf-convert-txt-remove-footer.pdf"


class PdfConvertTxt():
    def __init__(self, args=None):
        super(PdfConvertTxt, self).__init__()

    def string_similar(self, s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).quick_ratio()

    def process_header(self, dict, page_to_remove):
        avg_similar_score = 1
        max_vote_ratio = 1
        idx = 0

        while (avg_similar_score > 0.5 or max_vote_ratio > 0.5):
            header_list = []
            header_content_len = []
            for item in dict.items():
                str = item[1].split("\n")
                if (len(str) > idx):
                    header_list.append({"str": str[idx], "len": len(str[idx])})
                    header_content_len.append(len(str[idx]))
                else:
                    header_list.append({"str": "", "len": 0})
                    header_content_len.append(0)

            times = 0
            total_score = 0
            for i in range(0, len(header_list)):
                for j in range(i + 1, len(header_list)):
                    times += 1
                    score = self.string_similar(header_list[i]["str"], header_list[j]["str"])
                    total_score += score
            if (times <= 0):
                break
            avg_similar_score = total_score / times

            # 创建一个字典来保存每个header的总得分和次数
            header_scores = {}
            for i in range(len(header_list)):
                total_score = 0
                times = 0
                for j in range(len(header_list)):
                    if i != j:
                        times += 1
                        score = self.string_similar(header_list[i]["str"], header_list[j]["str"])
                        total_score += score
                if times > 0:
                    header_scores[i] = total_score / times
                else:
                    header_scores[i] = 0

            # 打印每个header的平均得分
            # for header_index, avg_score in header_scores.items():
            #    print(f'Average score for header at index {header_index}: {avg_score}')

            # 计算字符串相同长度出现最多次数的频率占比
            dic = Counter(header_content_len)
            dic = sorted(dic.items(), key=lambda item: item[1], reverse=True)
            max_vote_ratio = dic[0][1] / len(header_content_len)

            # 创建一个字典来保存每个下标的频次占比
            header_vote_ratio = {}
            # 计算每个长度的频次
            dic = Counter(header_content_len)
            for i in range(len(header_list)):
                header_vote_ratio[i] = dic[header_content_len[i]] / len(header_content_len)

            # 打印每个header的频次占比
            # for header_index, vote_ratio in header_vote_ratio.items():
            #    print(f'Vote ratio for header at index {header_index}: {vote_ratio}')

            # print(header_list)
            # print(header_content_len)

            for header_index in header_scores.keys():
                avg_score = header_scores[header_index]
                vote_ratio = header_vote_ratio[header_index]
                vote_len = dic[header_content_len[header_index]]
                if avg_score > 0.8 or vote_ratio > 0.4 or vote_len >= 5:  # 这是一个假设的条件，你需要根据你的需求修改
                    page_to_remove[header_index].append(idx)

            idx += 1
            if (idx >= 5):
                break

    def process_footer(self, dict, page_to_remove):
        avg_similar_score = 1
        max_vote_ratio = 1
        idx = -1
        while (avg_similar_score > 0.5 or max_vote_ratio > 0.5):
            footer_list = []
            footer_content_len = []
            for item in dict.items():
                str = item[1].split("\n")
                if (len(str) + idx >= 0):
                    footer_list.append({"str": str[idx], "len": len(str[idx])})
                    footer_content_len.append(len(str[idx]))
                else:
                    footer_list.append({"str": "", "len": 0})
                    footer_content_len.append(0)
            times = 0
            total_score = 0
            for i in range(0, len(footer_list)):
                for j in range(i + 1, len(footer_list)):
                    times += 1
                    score = self.string_similar(footer_list[i]["str"], footer_list[j]["str"])
                    total_score += score
            if (times <= 0):
                break
            avg_similar_score = total_score / times

            # 创建一个字典来保存每个footer的总得分和次数
            header_scores = {}
            for i in range(len(footer_list)):
                total_score = 0
                times = 0
                for j in range(len(footer_list)):
                    if i != j:
                        times += 1
                        score = self.string_similar(footer_list[i]["str"], footer_list[j]["str"])
                        total_score += score
                if times > 0:
                    header_scores[i] = total_score / times
                else:
                    header_scores[i] = 0
            ## 打印每个header的平均得分
            # for header_index, avg_score in header_scores.items():
            #    print(f'Average score for header at index {header_index}: {avg_score}')

            # 计算字符串相同长度出现最多次数的频率占比
            dic = Counter(footer_content_len)
            dic = sorted(dic.items(), key=lambda item: item[1], reverse=True)
            max_vote_ratio = dic[0][1] / len(footer_content_len)

            # 创建一个字典来保存每个下标的频次占比
            header_vote_ratio = {}
            # 计算每个长度的频次
            dic = Counter(footer_content_len)
            for i in range(len(footer_list)):
                header_vote_ratio[i] = dic[footer_content_len[i]] / len(footer_content_len)

            ## 打印每个header的频次占比
            # for header_index, vote_ratio in header_vote_ratio.items():
            #    print(f'Vote ratio for header at index {header_index}: {vote_ratio}')

            # print(footer_list)
            # print(footer_content_len)

            for header_index in header_scores.keys():
                avg_score = header_scores[header_index]
                vote_ratio = header_vote_ratio[header_index]
                vote_len = dic[footer_content_len[header_index]]
                if avg_score > 0.8 or vote_ratio > 0.4 or vote_len >= 5:  # 这是一个假设的条件，你需要根据你的需求修改
                    page_to_remove[header_index].append(idx)
            idx -= 1
            if (idx <= -5):
                break

    def remove_run(self, dict):
        page_to_remove = defaultdict(list)
        self.process_header(dict, page_to_remove)
        self.process_footer(dict, page_to_remove)
        # print("\n<key:每一页，value: 该页需要删除的段落索引list>:\n", page_to_remove)
        results = []

        patten = re.compile(r'([，、；])\s+|([\w\u4e00-\u9fa5]{1})\s+([\u4e00-\u9fa5]{1})')
        for i, item in enumerate(dict.items()):  # 遍历每一页
            str = item[1].split("\n")  # 每一页按行分割
            result = []
            delete_idx_in_page_i = page_to_remove[i]
            for idx, s in enumerate(str):
                if i == 0 and idx == 0:
                    s = patten.sub(r'\1\2\3', s).strip()
                    #s = s.encode('ISO-8859-1').decode('utf-8')
                    result.append(s)
                elif (idx in delete_idx_in_page_i or idx - len(str) in delete_idx_in_page_i):
                    continue
                else:
                    s = patten.sub(r'\1\2\3', s).strip()
                    #s = s.encode('ISO-8859-1').decode('utf-8')
                    result.append(s)
            results.append(result)
        return results

    def is_border_table(self, table):
        has_border_table = False
        for row in table.rows:
            for cell in row.cells:
                if "<w:tcBorders>" in cell._tc.xml:
                    has_border_table = True
                    return has_border_table
        return has_border_table

    def get_max_table_col_number(self, table):
        max_table_col_num = 0
        for i, row in enumerate(table.rows[:]):
            row_content = []
            if (len(row.cells) > max_table_col_num):
                max_table_col_num = len(row.cells)
        return max_table_col_num

    def process(self, file_dir):
        pdf_file = file_dir
        try:
            docx_file = file_dir + ".docx"
            cv = Converter(pdf_file)
            docx_list = cv.convert(docx_file)      # all pages by default
            cv.close()
            # print("convert end")
            book_contents = []
            for document in docx_list:
                for table in document.tables:
                    if (self.is_border_table(table) and self.get_max_table_col_number(table) > 1):
                        table._element.getparent().remove(table._element)
                text = ""
                for paragraph in document.paragraphs:
                    text += paragraph.text + "\n"

                text = "\n".join([s for s in text.splitlines() if s])
                text = [s.lstrip() for s in text.splitlines()]

                book_content = []
                for para in text:
                    book_content.append(para)

                book_contents.append(book_content)

            book_content_dict = {}
            for index, book_content in enumerate(book_contents, start=0):
                book_content_dict[index] = '\n'.join(book_content)
            result = self.remove_run(book_content_dict)

            output = {}
            # output["bos_url"] = url
            output["book_content"] = result
            output = json.dumps(output, ensure_ascii=False)
            print(output)
        except Exception as e:
            return str(e)
        
# script_path = os.path.abspath(__file__)
# test_dir = os.path.dirname(script_path)
# sample_path = os.path.join(test_dir, 'samples')
# PdfConvertTxt().process(sample_path + "/demo-pdf-convert-txt-remove-footer.pdf")
PdfConvertTxt().process(pdf_file_dir)