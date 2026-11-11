"""Persian text normalization (R-164).

Unifies Arabic/Persian characters, digits, diacritics and kashida so that
pg_trgm lexical search performs correctly. This is applied to content for the
lexical index and to query strings for retrieval.
"""

from __future__ import annotations

import re

_KASHIDA = "\u0640"  # tatweel (کشیده)
_ARABIC_YEH = "\u064a"
_PERSIAN_YEH = "\u06cc"
_ARABIC_KAF = "\u0643"
_PERSIAN_KAF = "\u06a9"
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")


def normalize_persian(text: str) -> str:
    s = text.replace(_KASHIDA, "")
    s = s.replace(_ARABIC_YEH, _PERSIAN_YEH).replace(_ARABIC_KAF, _PERSIAN_KAF)
    s = s.translate(_ARABIC_DIGITS).translate(_PERSIAN_DIGITS)
    s = _DIACRITICS_RE.sub("", s)
    return s.strip()
