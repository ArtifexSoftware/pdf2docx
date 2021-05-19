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
FACTOR_FEW = 0.01


# -------------------------------------
# docx
# -------------------------------------
HIDDEN_W_BORDER = 0.0   # do not show border
MIN_LINE_SPACING = 0.7  # minimum line spacing available in MS word


# punctuation implying end of a sentense
SENTENSE_END_PUNC = '.．。?？!！'


# -------------------------------------
# font parameters
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

DICT_FONT_LINE_HEIGHT = {
    'Arial': 1.15,
    'SimSun': 1.30
}


# CJK font definition parameters
CJK_CODEPAGE_BITS = {
    "JIS/Japan": 17,
    "Chinese: Simplified chars—PRC and Singapore": 18,
    "Korean Wansung": 19,
    "Chinese: Traditional chars—Taiwan and Hong Kong": 20,
    "Korean Johab": 21
}

CJK_UNICODE_RANGE_BITS = {
    'Hangul Jamo': 28,
    'Hiragana': 49,
    'Katakana': 50,
    'Bopomofo': 51,
    'Hangul Compatibility Jamo': 52,
    'Enclosed CJK Letters And Months': 54,
    'CJK Compatibility': 55,
    'Hangul Syllables': 56,
    'CJK Unified Ideographs': 59,
    'CJK Strokes': 61,
    'Yi Syllables': 83
}

CJK_UNICODE_RANGES = [
    [0x1100, 0x11FF],  # Hangul Jamo
    [0x3040, 0x309F],  # Hiragana
    [0x30A0, 0x30FF],  # Katakana
    [0x31F0, 0x31FF],  # Katakana Phonetic Extensions
    [0x3100, 0x312F],  # Bopomofo
    [0x31A0, 0x31BF],  # Bopomofo Extended (Bopomofo)
    [0x3130, 0x318F],  # Hangul Compatibility Jamo
    [0x3200, 0x32FF],  # Enclosed CJK Letters and Months
    [0x3300, 0x33FF],  # CJK Compatibility
    [0xAC00, 0xD7AF],  # Hangul Syllables
    [0x4E00, 0x9FFF],  # CJK Unified Ideographs
    [0x2E80, 0x2EFF],  # CJK Radicals Supplement (CJK Unified Ideographs)
    [0x2F00, 0x2FDF],  # Kangxi Radicals (CJK Unified Ideographs)
    [0x2FF0, 0x2FFF],  # Ideographic Description Characters (CJK Unified Ideographs)
    [0x3400, 0x4DBF],  # CJK Unified Ideographs Extension A (CJK Unified Ideographs)
    [0x20000, 0x2A6DF],  # CJK Unified Ideographs Extension B (CJK Unified Ideographs)
    [0x3190, 0x319F],  # Kanbun (CJK Unified Ideographs)
    [0x31C0, 0x31EF],  # CJK Strokes
    [0xF900, 0xFAFF],  # CJK Compatibility Ideographs (CJK Strokes)
    [0x2F800, 0x2FA1F],  # CJK Compatibility Ideographs Supplement (CJK Strokes)
    [0xA000, 0xA48F],  # Yi Syllables
    [0xA490, 0xA4CF],  # Yi Radicals
]