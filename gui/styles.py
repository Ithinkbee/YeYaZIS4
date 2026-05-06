"""
styles.py — цветовая палитра и стили для Tkinter GUI.
"""

# ── Palette ────────────────────────────────────────────────────────────────────
PRIMARY      = '#1565C0'
PRIMARY_DARK = '#003c8f'
PRIMARY_LIGHT= '#5e92f3'
SECONDARY    = '#E3F2FD'
ACCENT       = '#FF8F00'
ACCENT2      = '#00897B'

BG           = '#F5F7FA'
BG_CARD      = '#FFFFFF'
BG_SIDEBAR   = '#1A237E'
BG_SIDEBAR2  = '#283593'

TEXT_PRIMARY = '#212121'
TEXT_SECOND  = '#757575'
TEXT_ON_PRIMARY = '#FFFFFF'

SUCCESS      = '#2E7D32'
WARNING      = '#F57F17'
ERROR        = '#C62828'
NEUTRAL      = '#1565C0'

BORDER       = '#E0E0E0'
HOVER        = '#EEF2FF'

# ── Sentiment colors ───────────────────────────────────────────────────────────
SENTIMENT_COLOR = {
    'positive': SUCCESS,
    'negative': ERROR,
    'neutral':  NEUTRAL,
}

# ── POS colors ─────────────────────────────────────────────────────────────────
POS_COLORS = {
    'NOUN':  ('#E3F2FD', '#1565C0'),
    'VERB':  ('#FFF3E0', '#E65100'),
    'ADJ':   ('#E8F5E9', '#2E7D32'),
    'ADV':   ('#F3E5F5', '#6A1B9A'),
    'PRON':  ('#FCE4EC', '#880E4F'),
    'PROPN': ('#FFF8E1', '#FF6F00'),
    'NUM':   ('#E0F7FA', '#006064'),
    'ADP':   ('#FAFAFA', '#616161'),
    'CCONJ': ('#FAFAFA', '#616161'),
    'SCONJ': ('#FAFAFA', '#616161'),
    'PART':  ('#FAFAFA', '#616161'),
    'PUNCT': ('#FFFFFF', '#BDBDBD'),
    'X':     ('#FAFAFA', '#9E9E9E'),
}

def pos_color(pos: str):
    return POS_COLORS.get(pos, ('#FAFAFA', '#616161'))

# ── Fonts ──────────────────────────────────
FONT_TITLE   = ('Segoe UI', 17, 'bold')
FONT_HEADER  = ('Segoe UI', 13, 'bold')
FONT_BODY    = ('Segoe UI', 12)
FONT_SMALL   = ('Segoe UI', 11)
FONT_MONO    = ('Courier New', 12)
FONT_BIG     = ('Segoe UI', 22, 'bold')
