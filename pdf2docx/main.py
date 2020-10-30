#!/usr/bin/python3
# -*- coding: utf-8 -*-

from .converter import Converter


class PDF2DOCX:
    '''Command line interface for pdf2docx.'''

    @staticmethod
    def convert(pdf_file, docx_file=None, start=0, end=None, pages=None, **kwargs):
        ''' Convert pdf file to docx file.
        
            Args:
                pdf_file (str) : PDF filename to read from
                docx_file (str): DOCX filename to write to
                start (int)    : first page to process, starting from zero if --zero_based_index=True
                end (int)      : last page to process, starting from zero if --zero_based_index=True
                pages (list)   : range of pages
                kwargs (dict)  : configuration parameters
                                zero_based_index               : True, page index from 0 if True else 1
                                multi_processing               : False, set multi-processes, especially for PDF with large pages
                                cpu_count                      : cpu_count(), the count of cpu used for multi-processing
                                connected_border_tolerance     : 0.5, two borders are intersected if the gap lower than this value
                                max_border_width               : 6.0, max border width
                                min_border_clearance           : 2.0, the minimum allowable clearance of two borders
                                float_image_ignorable_gap      : 5.0, float image if the intersection exceeds this value
                                float_layout_tolerance         : 0.1, [0,1] the larger of this value, the more tolerable of float layout
                                page_margin_factor_top         : 0.5, [0,1] reduce top margin by factor
                                page_margin_factor_bottom      : 0.5, [0,1] reduce bottom margin by factor
                                shape_merging_threshold        : 0.5, [0,1] merge shape if the intersection exceeds this value
                                shape_min_dimension            : 2.0, ignore shape if both width and height is lower than this value
                                line_overlap_threshold         : 0.9, [0,1] delete line if the intersection to other lines exceeds this value
                                line_merging_threshold         : 2.0, combine two lines if the x-distance is lower than this value
                                line_separate_threshold        : 5.0, two separate lines if the x-distance exceeds this value
                                lines_left_aligned_threshold   : 1.0, left aligned if delta left edge of two lines is lower than this value
                                lines_right_aligned_threshold  : 1.0, right aligned if delta right edge of two lines is lower than this value
                                lines_center_aligned_threshold : 2.0, center aligned if delta center of two lines is lower than this value
                                clip_image_res_ratio           : 3.0, resolution ratio (to 72dpi) when cliping page image
                                curve_path_ratio               : 0.2, clip page bitmap if the component of curve paths exceeds this ratio
        '''
        cv = Converter(pdf_file)
        cv.make_docx(docx_file, start, end, pages, kwargs)
        cv.close()
    

    @staticmethod
    def table(pdf_file, start=0, end=None, pages=None, **kwargs):
        ''' Extract table content from pdf pages.
        
            Args:
                pdf_file (str) : PDF filename to read from
                start (int)    : first page to process, starting from zero
                end (int)      : last page to process, starting from zero
                pages (list)   : range of pages
        '''

        cv = Converter(pdf_file)
        tables = cv.extract_tables(start, end, pages, kwargs)
        cv.close()

        return tables


parse = PDF2DOCX.convert


def main():
    import fire
    fire.Fire(PDF2DOCX)


if __name__ == '__main__':
    main()