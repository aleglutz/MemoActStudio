"""Text normalisation pre-pass (SPEC §5.1) — alignment-only text.

Digits and dates expand to spoken form BEFORE alignment; the verbatim script is
what reaches the screen, so nothing here can corrupt a subtitle. That bounds the
stakes: a wrong choice below costs alignment accuracy on one boundary, never
on-screen text.

Years are read in pair form. English says "nineteen seventy-four", not "one
thousand, nine hundred and seventy-four" — and since this is historical material
where roughly every second sentence carries a date, feeding the aligner the
cardinal form is a systematic mismatch against what the narrator actually says.
`num2words(to="year")` handles the pair reading, including "nineteen hundred",
"ten sixty-six" and "twenty twenty-six".

The project is English-only as of SPEC v3.1; other languages are left wired up
but unexercised, since re-adding one should stay a scope decision rather than a
rewrite. Russian in particular needs case and number inflection that a bare
num2words cannot produce — see the git history of this file if that ever
returns.
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+")
_LANG_MAP = {"ru": "ru", "en": "en", "de": "de", "fr": "fr"}

# A 4-digit number in this range is read as a year. Chosen for the material:
# 20th-century history, where bare quantities of this magnitude are rare and
# dates are constant. The failure mode is mild — "1500 people" would become
# "fifteen hundred people", which is also idiomatic English.
_YEAR_MIN, _YEAR_MAX = 1100, 2099


def _looks_like_year(token: str, value: int) -> bool:
    return len(token) == 4 and _YEAR_MIN <= value <= _YEAR_MAX


def normalize_block(text: str, lang: str) -> tuple[str, bool]:
    """Return (normalised text, had_digits)."""
    from num2words import num2words

    n2w_lang = _LANG_MAP.get(lang, "en")
    had = bool(_NUM_RE.search(text))

    def repl(m: re.Match) -> str:
        token = m.group()
        try:
            value = int(token)
            if _looks_like_year(token, value):
                return num2words(value, lang=n2w_lang, to="year")
            return num2words(value, lang=n2w_lang)
        except Exception:
            # Unsupported language/value: leave the digits alone rather than
            # dropping them — the aligner copes better with a token it cannot
            # match than with a silently deleted word.
            return token

    out = _NUM_RE.sub(repl, text)
    # strip leftover ordinal/decade suffixes glued to expanded numbers: "…е", "…х"
    out = re.sub(r"(\S)-(е|х|й|м|го|му|ми)\b", r"\1", out) if lang == "ru" else out
    return out, had
