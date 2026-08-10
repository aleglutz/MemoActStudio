"""Cutting a narration block into short, single-line captions.

A script block is a unit of writing, not a unit of reading. The longest block
in the current reel is 32 words; at any legible size that is four or five lines
on a 1080-wide frame. Two problems follow, and they are the same problem:

  - a wall of text is not readable in a vertical reel;
  - the caption plate is drawn *per line* (memoacts_core.subs), so stacked lines
    stack their plates too. Where two semi-transparent plates overlap, the alpha
    composites twice and a dark bar cuts straight through the text — measured at
    L=60 against L=116 for a single plate, a 20 px band, exactly 2x the plate
    padding.

So the fix for legibility and the fix for the dark bar are one fix: **never emit
a caption that wraps.** This module guarantees that by measuring, not guessing —
it packs words until the rendered line would exceed the usable width, using the
same font file that libass burns in.

Timings come from the aligner's word times, so a cut lands on a word boundary
that was actually spoken rather than on a proportional guess.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .align import Word

#: Punctuation that ends a thought. Breaking here reads better than breaking
#: at whatever word happened to fill the line.
_STRONG = ".!?…:;"
_WEAK = ",—–-"


@dataclass
class TimedText:
    text: str
    t_start: float
    t_end: float


@lru_cache(maxsize=8)
def _font(font_path: str, size: int):
    from PIL import ImageFont

    return ImageFont.truetype(font_path, size)


def text_width(text: str, size: int, font_path: str | Path) -> float:
    """Rendered width in play-resolution pixels.

    PIL and libass do not share a rasteriser, but they do share the font's
    advance metrics, which is all that matters for deciding where to break. The
    budget below is left deliberately slack to absorb the rest.
    """
    return _font(str(font_path), size).getlength(text)


def usable_width(play_w: int, margin_l: int, margin_r: int,
                 plate_pad: float = 0.0) -> float:
    """Width a caption may occupy. The plate grows past the text on both sides,
    so it is the plate, not the glyphs, that has to fit inside the margins."""
    return max(play_w - margin_l - margin_r - 2 * plate_pad, 1.0)


def _ends_with(tok: str, group: str) -> bool:
    return tok.rstrip('"\')').endswith(tuple(group))


def _sentences(words: list[Word]) -> list[list[Word]]:
    """Split on sentence-ending punctuation.

    Greedy packing alone produces captions that straddle a full stop — the reel
    showed `May. Two dates for the end of`, which reads as one thought and is
    two. Sentences are cut first so that can never happen; only what is left
    over is packed by width.
    """
    out, cur = [], []
    for w in words:
        cur.append(w)
        if _ends_with(w.text, _STRONG):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _split_evenly(sent: list[Word], *, size: int, max_width: float,
                  font_path: str | Path) -> list[list[Word]]:
    """Cut one over-long sentence into the fewest, most even pieces.

    Even matters: filling each line to the brim would leave the last piece a
    one-word flash. Aiming at total/pieces spreads the sentence instead, and a
    weak-punctuation boundary within reach of the target is taken in preference
    to a bare word boundary.
    """
    def width(a: int, b: int) -> float:
        return text_width(" ".join(x.text for x in sent[a:b]), size, font_path)

    out, start = [], 0
    while start < len(sent):
        rest = width(start, len(sent))
        if rest <= max_width:
            out.append(sent[start:])
            break
        # Recomputing the split target from what is *left* rather than once up
        # front keeps the pieces even even when an early one lands short — and,
        # more importantly, means the tail is never handed whatever remains
        # unchecked. Every piece below is width-constrained, so a caption that
        # exceeds the budget cannot come out of this loop.
        target = rest / max(1, -(-int(rest) // int(max_width)))  # ceil
        best, best_cost = start + 1, None
        for end in range(start + 1, len(sent) + 1):
            w = width(start, end)
            if w > max_width and end > start + 1:
                break
            # Distance from the even-share target, discounted where the piece
            # ends on a comma or dash.
            cost = abs(w - target) * (0.6 if _ends_with(sent[end - 1].text,
                                                        _WEAK) else 1.0)
            if best_cost is None or cost < best_cost:
                best, best_cost = end, cost
        out.append(sent[start:best])
        start = best
    return [p for p in out if p]


def segment(words: list[Word], *, size: int, max_width: float,
            font_path: str | Path, min_duration: float = 0.0,
            ) -> list[TimedText]:
    """Cut `words` into captions no wider than `max_width`.

    A word wider than the budget on its own is emitted alone and will overflow —
    the alternative is dropping script text, which is never acceptable here.
    """
    out: list[TimedText] = []
    for sent in _sentences(words):
        for chunk in _split_evenly(sent, size=size, max_width=max_width,
                                   font_path=font_path):
            out.append(TimedText(" ".join(w.text for w in chunk),
                                 chunk[0].t_start, chunk[-1].t_end))

    # A caption that flashes is as unreadable as one that wraps. Where the
    # narration leaves a gap before the next caption, spend it on the short one
    # rather than cutting to black text-less frames.
    if min_duration > 0:
        for k, c in enumerate(out):
            ceiling = out[k + 1].t_start if k + 1 < len(out) else None
            want = c.t_start + min_duration
            c.t_end = max(c.t_end, want if ceiling is None else min(want, ceiling))
    return out


def widest(cues: list[TimedText], size: int, font_path: str | Path) -> float:
    return max((text_width(c.text, size, font_path) for c in cues), default=0.0)
