"""Text normalisation pre-pass (SPEC §5.1) — alignment-only text.

Digits/dates expand to spoken form BEFORE alignment; the verbatim script is
what reaches the screen. v1 approach (documented per SPEC open item):

- plain integers -> num2words cardinal in the target language;
- RU: nominative cardinal only. Real speech inflects («в … четвёртом году»),
  which a bare num2words cannot produce. Hypothesis, to be checked against the
  Sidur bake-off: whisper-token alignment is tolerant enough that the correct
  *word count and stem* matter more than the case ending. Blocks containing
  digits are therefore flagged so their confidence can be read with care.
- decade forms («1970-е», «1970-х») and other suffixed numbers: expand the
  numeric part, keep no suffix — a deliberate simplification, flagged.
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+")
_LANG_MAP = {"ru": "ru", "en": "en", "de": "de", "fr": "fr"}


def normalize_block(text: str, lang: str) -> tuple[str, bool]:
    """Return (normalised text, had_digits)."""
    from num2words import num2words

    n2w_lang = _LANG_MAP.get(lang, "en")
    had = bool(_NUM_RE.search(text))

    def repl(m: re.Match) -> str:
        try:
            return num2words(int(m.group()), lang=n2w_lang)
        except Exception:
            return m.group()

    out = _NUM_RE.sub(repl, text)
    # strip leftover ordinal/decade suffixes glued to expanded numbers: "…е", "…х"
    out = re.sub(r"(\S)-(е|х|й|м|го|му|ми)\b", r"\1", out) if lang == "ru" else out
    return out, had
