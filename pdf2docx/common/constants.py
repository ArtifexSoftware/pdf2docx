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


# default font name and line height ratio
DICT_FONT_LINE_HEIGHT = {
    'SimSun': 1.30,
    'Agency FB': 1.18,
    'Algerian': 1.32,
    'Book Antiqua': 1.21,
    'Arial': 1.15,
    'Arial Narrow': 1.15,
    'Arial Black': 1.41,
    'Arial Rounded MT Bold': 1.16,
    'Bahnschrift': 1.2,
    'Baskerville Old Face': 1.0,
    'Bauhaus 93': 1.46,
    'Bell MT': 1.11,
    'Bernard MT Condensed': 1.19,
    'Bodoni MT': 1.2,
    'Bodoni MT Black': 1.17,
    'Bodoni MT Condensed': 1.18,
    'Bodoni MT Poster Compressed': 1.15,
    'Bookman Old Style': 1.17,
    'Bradley Hand ITC': 1.25,
    'Britannic Bold': 1.0,
    'Berlin Sans FB': 1.1,
    'Berlin Sans FB Demi': 1.13,
    'Broadway': 1.13,
    'Brush Script MT': 1.23,
    'Bookshelf Symbol 7': 1.0,
    'Calibri': 1.22,
    'Calibri Light': 1.22,
    'Californian FB': 1.14,
    'Calisto MT': 1.15,
    'Cambria': 1.17,
    'Candara': 1.22,
    'Candara Light': 1.22,
    'Cascadia Code': 1.16,
    'Cascadia Mono': 1.16,
    'Castellar': 1.2,
    'Century Schoolbook': 1.2,
    'Centaur': 1.14,
    'Century': 1.2,
    'Chiller': 1.15,
    'Colonna MT': 1.06,
    'Comic Sans MS': 1.39,
    'Consolas': 1.17,
    'Constantia': 1.22,
    'Cooper Black': 1.15,
    'Copperplate Gothic Bold': 1.11,
    'Copperplate Gothic Light': 1.1,
    'Corbel': 1.21,
    'Corbel Light': 1.21,
    'Courier New': 1.13,
    'Curlz MT': 1.33,
    'DengXian': 1.35,
    'DengXian Light': 1.35,
    'Dubai': 1.69,
    'Dubai Light': 1.69,
    'Dubai Medium': 1.69,
    'Ebrima': 1.28,
    'Elephant': 1.29,
    'Engravers MT': 1.16,
    'Eras Bold ITC': 1.16,
    'Eras Demi ITC': 1.15,
    'Eras Light ITC': 1.13,
    'Eras Medium ITC': 1.14,
    'Felix Titling': 1.17,
    'Forte': 1.36,
    'Franklin Gothic Book': 1.13,
    'Franklin Gothic Demi': 1.13,
    'Franklin Gothic Demi Cond': 1.13,
    'Franklin Gothic Heavy': 1.13,
    'Franklin Gothic Medium': 1.13,
    'Franklin Gothic Medium Cond': 1.13,
    'Freestyle Script': 1.18,
    'French Script MT': 1.14,
    'Footlight MT Light': 0.92,
    'FZShuTi': 1.37,
    'FZYaoTi': 1.48,
    'Gabriola': 1.7,
    'Gadugi': 1.33,
    'Garamond': 1.12,
    'Georgia': 1.14,
    'Gigi': 1.38,
    'Gill Sans MT': 1.16,
    'Gill Sans MT Condensed': 1.2,
    'Gill Sans Ultra Bold Condensed': 1.25,
    'Gill Sans Ultra Bold': 1.25,
    'Gloucester MT Extra Condensed': 1.16,
    'Gill Sans MT Ext Condensed Bold': 1.2,
    'Century Gothic': 1.23,
    'Goudy Old Style': 1.2,
    'Goudy Stout': 1.37,
    'Harlow Solid Italic': 1.26,
    'Harrington': 1.18,
    'Haettenschweiler': 1.07,
    'Microsoft Himalaya': 1.0,
    'HoloLens MDL2 Assets': 1.0,
    'High Tower Text': 1.16,
    'Impact': 1.22,
    'Imprint MT Shadow': 1.18,
    'Informal Roman': 1.2,
    'Ink Free': 1.24,
    'Blackadder ITC': 1.23,
    'Edwardian Script ITC': 1.18,
    'Kristen ITC': 1.36,
    'Javanese Text': 2.27,
    'Jokerman': 1.51,
    'Juice ITC': 1.19,
    'DFKai': 1.3,
    'Kunstler Script': 1.09,
    'Wide Latin': 1.0,
    'Lucida Bright': 1.18,
    'Lucida Calligraphy': 1.36,
    'Leelawadee UI': 1.33,
    'Leelawadee UI Semilight': 1.33,
    'Lucida Fax': 1.18,
    'Lucida Handwriting': 1.38,
    'Lucida Sans': 1.18,
    'Lucida Sans Typewriter': 1.17,
    'Lucida Console': 1.0,
    'Lucida Sans Unicode': 1.54,
    'Magneto': 1.21,
    'Maiandra GD': 1.2,
    'Malgun Gothic': 1.73,
    'Malgun Gothic Semilight': 1.73,
    'Marlett': 0.94,
    'Matura MT Script Capitals': 1.33,
    'Microsoft Sans Serif': 1.13,
    'Mistral': 1.0,
    'Myanmar Text': 1.9,
    'Modern No. 20': 1.07,
    'Mongolian Baiti': 1.15,
    'Microsoft Yi Baiti': 1.3,
    'Monotype Corsiva': 1.12,
    'MT Extra': 1.01,
    'MV Boli': 1.61,
    'Niagara Engraved': 1.07,
    'Niagara Solid': 1.07,
    'Nirmala UI': 1.33,
    'Nirmala UI Semilight': 1.33,
    'Microsoft New Tai Lue': 1.31,
    'Solid Edge ANSI GDT Symbols': 1.59,
    'NX Constraints': 1.0,
    'Solid Edge ISO GDT Symbols': 1.59,
    'NX Markers': 1.0,
    'OCR A Extended': 1.03,
    'Old English Text MT': 1.0,
    'Onyx': 1.07,
    'MS Outlook': 1.04,
    'Palatino Linotype': 1.35,
    'Palace Script MT': 0.93,
    'Papyrus': 1.57,
    'Parchment': 1.07,
    'Perpetua': 1.15,
    'Perpetua Titling MT': 1.18,
    'Microsoft PhagsPa': 1.52,
    'Playbill': 1.0,
    'Poor Richard': 1.13,
    'Pristina': 1.2,
    'Rage Italic': 1.26,
    'Ravie': 1.33,
    'MS Reference Sans Serif': 1.58,
    'MS Reference Specialty': 1.23,
    'Rockwell Condensed': 1.18,
    'Rockwell': 1.17,
    'Rockwell Extra Bold': 1.17,
    'Script MT Bold': 1.2,
    'Segoe MDL2 Assets': 1.0,
    'Segoe Print': 1.77,
    'Segoe Script': 1.61,
    'Segoe UI': 1.33,
    'Segoe UI Light': 1.33,
    'Segoe UI Semilight': 1.33,
    'Segoe UI Black': 1.33,
    'Segoe UI Emoji': 1.22,
    'Segoe UI Historic': 1.33,
    'Segoe UI Semibold': 1.33,
    'Segoe UI Symbol': 1.73,
    'Showcard Gothic': 1.24,
    'FangSong': 1.3,
    'SimHei': 1.3,
    'KaiTi': 1.3,
    'LiSu': 1.3,
    'SimSun': 1.3,
    'YouYuan': 1.3,
    'Snap ITC': 1.29,
    'STCaiyun': 1.35,
    'Stencil': 1.0,
    'STFangsong': 1.69,
    'STHupo': 1.34,
    'STKaiti': 1.69,
    'STLiti': 1.38,
    'STSong': 1.69,
    'STXihei': 1.79,
    'STXingkai': 1.42,
    'STXinwei': 1.35,
    'STZhongsong': 1.72,
    'Sylfaen': 1.32,
    'Symbol': 1.23,
    'Tahoma': 1.21,
    'Microsoft Tai Le': 1.27,
    'Tw Cen MT': 1.09,
    'Tw Cen MT Condensed': 1.07,
    'Tw Cen MT Condensed Extra Bold': 1.08,
    'TeamViewer14': 0.86,
    'Tempus Sans ITC': 1.3,
    'Times New Roman': 1.15,
    'Trebuchet MS': 1.16,
    'Verdana': 1.22,
    'Viner Hand ITC': 1.61,
    'Vivaldi': 1.22,
    'Vladimir Script': 1.21,
    'Webdings': 1.0,
    'Wingdings': 1.11,
    'Wingdings 2': 1.05,
    'Wingdings 3': 1.14
}