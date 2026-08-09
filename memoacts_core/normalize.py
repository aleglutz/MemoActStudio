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

_MONTHS = ("January|February|March|April|May|June|July|August|September|"
           "October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
           "Oct|Nov|Dec")

#: "May 7" / "7 May" — a day number, which English reads as an ordinal.
_DATE_MD_RE = re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}})\b(?!\s*[:.]\d)", re.I)
_DATE_DM_RE = re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS})\b", re.I)

#: "1950s", "1970s" — a decade, read as a plural year.
_DECADE_RE = re.compile(r"\b(\d{4})s\b")

#: "0.45", "23.45" — a decimal or clock reading. The point is not spoken.
_DOTTED_RE = re.compile(r"\b(\d+)\.(\d+)\b")

#: "23:01" — an unambiguous clock reading; the colon is never spoken.
_COLON_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")

# A 4-digit number in this range is read as a year. Chosen for the material:
# 20th-century history, where bare quantities of this magnitude are rare and
# dates are constant. The failure mode is mild — "1500 people" would become
# "fifteen hundred people", which is also idiomatic English.
_YEAR_MIN, _YEAR_MAX = 1100, 2099


def _looks_like_year(token: str, value: int) -> bool:
    return len(token) == 4 and _YEAR_MIN <= value <= _YEAR_MAX


def _pluralise(word: str) -> str:
    """"nineteen fifty" -> "nineteen fifties"; "nineteen hundred" -> "hundreds"."""
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


def normalize_block(text: str, lang: str) -> tuple[str, bool]:
    """Return (normalised text, had_digits)."""
    from num2words import num2words

    n2w_lang = _LANG_MAP.get(lang, "en")
    had = bool(_NUM_RE.search(text))

    def card(value: int) -> str:
        return num2words(value, lang=n2w_lang)

    def repl(m: re.Match) -> str:
        token = m.group()
        try:
            value = int(token)
            if _looks_like_year(token, value):
                return num2words(value, lang=n2w_lang, to="year")
            return card(value)
        except Exception:
            # Unsupported language/value: leave the digits alone rather than
            # dropping them — the aligner copes better with a token it cannot
            # match than with a silently deleted word.
            return token

    out = text

    if n2w_lang == "en":
        # Order matters: each pass consumes a pattern the plain-number pass
        # below would otherwise mangle.

        # "23:01" -> "twenty-three oh one". Unlike the dotted form this is
        # unambiguously a clock, so it needs no guessing — but English reads a
        # minute below ten as "oh one", not "one", and the colon is silent.
        def colon_time(m: re.Match) -> str:
            try:
                hh, mm = int(m.group(1)), int(m.group(2))
                if mm == 0:
                    tail = "o'clock" if hh <= 12 else "hundred"
                elif mm < 10:
                    tail = f"oh {card(mm)}"
                else:
                    tail = card(mm)
                return f"{card(hh)} {tail}"
            except Exception:
                return m.group()
        out = _COLON_TIME_RE.sub(colon_time, out)

        # "1950s" -> "nineteen fifties". Without this the trailing s survives
        # the year expansion and yields "nineteen fiftys".
        def decade(m: re.Match) -> str:
            try:
                return _pluralise(num2words(int(m.group(1)), lang="en", to="year"))
            except Exception:
                return m.group()
        out = _DECADE_RE.sub(decade, out)

        # "0.45 a.m." -> "zero forty-five", but "3.14" -> "three point fourteen".
        # Leaving the point in produced "zero.forty-five", a token the aligner
        # can never match against speech — but silently dropping it everywhere
        # would swallow the spoken "point" of a real decimal.
        #
        # `HH.MM` is read as a clock; anything else keeps "point". The two are
        # not distinguishable by syntax — "3.14" is a valid clock reading too —
        # so this is a bet on the material, which is a historical documentary
        # full of times and free of decimals. To force either reading, write it
        # out in the script; the screen text is unaffected either way.
        def dotted(m: re.Match) -> str:
            whole, frac = m.group(1), m.group(2)
            try:
                is_clock = (len(frac) == 2 and int(frac) <= 59
                            and len(whole) <= 2 and int(whole) <= 23)
                joiner = " " if is_clock else " point "
                return f"{card(int(whole))}{joiner}{card(int(frac))}"
            except Exception:
                return m.group()
        out = _DOTTED_RE.sub(dotted, out)

        # "May 7" -> "May seventh". A day number is read as an ordinal, and in
        # this material dates sit on exactly the boundaries alignment drifts on.
        def ordinal(value: str) -> str:
            return num2words(int(value), lang="en", to="ordinal")

        out = _DATE_MD_RE.sub(
            lambda m: f"{m.group(1)} {ordinal(m.group(2))}", out)
        out = _DATE_DM_RE.sub(
            lambda m: f"{ordinal(m.group(1))} {m.group(2)}", out)

    out = _NUM_RE.sub(repl, out)
    # strip leftover ordinal/decade suffixes glued to expanded numbers: "…е", "…х"
    out = re.sub(r"(\S)-(е|х|й|м|го|му|ми)\b", r"\1", out) if lang == "ru" else out
    return out, had
