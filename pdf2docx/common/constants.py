# -*- coding: utf-8 -*-


# -------------------------------------
# basic unit
# -------------------------------------
PT = 1.0   # basic unit
ITP = 72.0 # inch to point

MAJOR_DIST = 5.0 * PT   # significant distance exists between two block lines
MINOR_DIST = 1.0 * PT   # small distance
TINY_DIST  = 0.5 * PT   # very small distance

FACTOR_SAME = 0.99
FACTOR_ALMOST = 0.95
FACTOR_MOST = 0.90
FACTOR_MAJOR = 0.75
FACTOR_A_HALF = 0.5
FACTOR_A_FEW = 0.1

# -------------------------------------
# page parameters
# -------------------------------------
DM_PAGE = 5.0 * PT
FACTOR_PAGE_MARGIN = 0.5     # page margin factor


# -------------------------------------
# path extracting
# -------------------------------------
IGNORE_VEC_GRAPH = False
FACTOR_RES = 3.0             # improve image resolution

# -------------------------------------
# table parsing
# -------------------------------------
# max/min width of table border in docx
MAX_W_BORDER = 6.0
MIN_W_BORDER = 0.25
HIDDEN_W_BORDER = 0.0   # do not show border
DW_BORDER = 2.0         # width difference of two connected borders


# -------------------------------------
# font name mapping
# -------------------------------------
# special process on the key:
# - upper case
# - delete blanks, '-', '_'
DICT_FONTS = {
    'SIMSUN': '宋体', 
    'SIMHEI': '黑体', 
    'MICROSOFTYAHEI': '微软雅黑', 
    'MICROSOFTJHENGHEI': '微软正黑体', 
    'NSIMSUN': '新宋体', 
    'PMINGLIU': '新细明体', 
    'MINGLIU': '细明体', 
    'DFKAISB': '标楷体', # 'DFKAI-SB'
    'FANGSONG': '仿宋', 
    'KAITI': '楷体', 
    'FANGSONGGB2312': '仿宋_GB2312', # FANGSONG_GB2312
    'KAITIGB2312': '楷体_GB2312',   # KAITI_GB2312
    'LISU': '隶书',
    'YOUYUAN': '幼圆',
    'STXIHEI': '华文细黑',
    'STKAITI': '华文楷体',
    'STSONG': '华文宋体',
    'STZHONGSONG': '华文中宋',
    'STFANGSONG': '华文仿宋',
    'FZSHUTI': '方正舒体',
    'FZYAOTI': '方正姚体',
    'STCAIYUN': '华文彩云',
    'STHUPO': '华文琥珀',
    'STLITI': '华文隶书',
    'STXINGKAI': '华文行楷',
    'STXINWEI': '华文新魏',
    'ARIALNARROW': 'Arial Narrow'
}