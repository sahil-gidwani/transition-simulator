"""Search-text normalization: case- and diacritic-insensitive matching.

Deliberately NOT the pipeline's club-name normalizer: that one strips stop
tokens ("de", "fc", ...) that are meaningful in player names, and its
German-style transliteration (o-umlaut -> "oe") is wrong for search input
(people type "ozil", not "oezil").
"""

from __future__ import annotations

import re
import unicodedata

# Letters NFKD cannot decompose into ASCII + combining marks.
_FOLD = str.maketrans(
    {
        "ø": "o",
        "Ø": "O",
        "ß": "ss",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ð": "d",
        "Ð": "D",
        "þ": "th",
        "Þ": "Th",
        "ı": "i",  # noqa: RUF001 - dotless i is exactly the character being folded
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_search_text(text: str) -> str:
    """Lowercase ASCII with single spaces: "Søren Müller-Å" -> "soren muller a"."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_FOLD))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", stripped.lower()).strip()
