"""Club-name normalization for ClubElo matching.

Ported from the audit (scripts/explore.py); the mapping ladder in
transforms/elo.py builds on these primitives. Both sides of every match pass
through normalize_club_name.
"""

from __future__ import annotations

import re
import unicodedata

# Corporate/legal tokens dropped when normalizing club names for Elo matching.
# NB: no token that is itself a distinguishing club name ("sporting", "sg" in
# "Paris SG") - dropping those creates collisions between distinct clubs.
STOP_TOKENS = frozenset(
    {
        # abbreviations of club/association legal forms
        "fc",
        "cf",
        "afc",
        "ac",
        "as",
        "sc",
        "ssc",
        "sv",
        "bsc",
        "vfb",
        "vfl",
        "tsg",
        "fk",
        "nk",
        "if",
        "bk",
        "sk",
        "cd",
        "ud",
        "rcd",
        "ogc",
        "aj",
        "rc",
        "us",
        "sd",
        "ca",
        "kaa",
        "krc",
        "rsc",
        "kv",
        "sl",
        "gd",
        "cs",
        "fsv",
        "spvgg",
        "tsv",
        "cfr",
        "acf",
        "cp",
        "ab",
        "bsk",
        "fak",
        "spvg",
        "ag",
        "ev",
        "sad",
        "pfk",
        # spelled-out legal/generic words
        "club",
        "clube",
        "de",
        "futbol",
        "futebol",
        "calcio",
        "football",
        "fussball",
        "koninklijke",
        "voetbalvereniging",
        "vereniging",
        "sportvereniging",
        "sportverein",
        "spielvereinigung",
        "idraetsforening",
        "boldklub",
        "fodbold",
        "balompie",
        "sport",
        "esporte",
        "esportiva",
        "sociedade",
        "regatas",
    }
)

# Characters NFKD/ASCII would mangle; both sides of every match pass through this.
TRANSLIT = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "ø": "oe",
        "æ": "ae",
        "å": "aa",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "œ": "oe",
        "ı": "i",  # noqa: RUF001 - Turkish dotless i, intentional
    }
)


def normalize_club_name(name: str) -> str:
    lowered = name.lower().translate(TRANSLIT)
    ascii_name = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^a-z0-9 ]", " ", ascii_name)
    tokens = [t for t in ascii_name.split() if t not in STOP_TOKENS and not t.isdigit()]
    return " ".join(tokens)


def tokens_prefix_match(elo_tokens: frozenset[str], tm_tokens: frozenset[str]) -> bool:
    """True when every Elo token matches a TM token exactly or as a >=3-char prefix."""

    def hit(elo_tok: str) -> bool:
        return any(
            elo_tok == tm_tok
            or (len(elo_tok) >= 3 and tm_tok.startswith(elo_tok))
            or (len(tm_tok) >= 3 and elo_tok.startswith(tm_tok))
            for tm_tok in tm_tokens
        )

    return bool(elo_tokens) and all(hit(tok) for tok in elo_tokens)


def acronyms(tokens: list[str]) -> set[str]:
    """First-letter acronyms of every contiguous token run of length >= 2."""
    return {
        "".join(tok[0] for tok in tokens[i:j])
        for i in range(len(tokens))
        for j in range(i + 2, len(tokens) + 1)
    }
