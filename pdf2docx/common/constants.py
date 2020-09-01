# -*- coding: utf-8 -*-

import fitz

# margin
DM = 1.0

# inch to point
ITP = 72.0

# tolerant rectangle area
DR = fitz.Rect(-DM, -DM, DM, DM) / 2.0

# max/min width of table border in docx
MAX_W_BORDER = 6.0
MIN_W_BORDER = 0.25
HIDDEN_W_BORDER = 0.0 # not show border

# font name mapping
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