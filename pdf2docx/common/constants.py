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
DEFAULT_LINE_SPACING = 1.02

# punctuation implying end of a sentense
SENTENCE_END_PUNC = '.．。?？!！'

# control characters not supported by lxml
# https://github.com/dothinking/pdf2docx/issues/126#issuecomment-1040034077
INVALID_CHARS = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'


# -------------------------------------
# font parameters
# -------------------------------------

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

DEFAULT_FONT_NAME = 'helv'