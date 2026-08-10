"""Known-text alignment behind a swappable interface (SPEC §5.1).

The engine choice (stable-ts) must never leak past this module: swapping
engines touches this file only, never callers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Word:
    """One word of the script with its own timing.

    The engine computes these anyway; keeping them is what lets a long block be
    cut into short captions at real word boundaries instead of by guessing
    proportionally (memoacts_core.caption). `text` is verbatim script — the
    digits-expanded form must never travel here.
    """
    text: str
    t_start: float
    t_end: float


@dataclass
class Span:
    index: int
    t_start: float
    t_end: float
    confidence: float
    estimated: bool
    words: list[Word] = field(default_factory=list)


class Aligner(Protocol):
    def align(self, audio_path: Path, blocks: list[str], lang: str,
              display_blocks: list[str] | None = None) -> list[Span]: ...


def proportional_spans(blocks: list[str], duration: float) -> list[Span]:
    """Fallback: distribute duration over blocks by word count (SPEC §5.1 —
    never a failed run)."""
    weights = [max(len(b.split()), 1) for b in blocks]
    total = sum(weights)
    spans, t = [], 0.0
    for i, w in enumerate(weights):
        d = duration * w / total
        # Synthesise word timings too, so captions still segment on this path.
        # They are guesses — `estimated` says so — but a fallback that produced
        # no captions at all would be worse than approximate ones.
        toks = blocks[i].split() or [blocks[i]]
        step = d / len(toks)
        words = [Word(tok, t + k * step, t + (k + 1) * step)
                 for k, tok in enumerate(toks)]
        spans.append(Span(i, t, t + d, 0.0, True, words))
        t += d
    if spans:
        spans[-1].t_end = duration
    return spans


class StableTsAligner:
    """Primary engine (ALIGNERS.md decision): stable-ts ``align()`` aligns the
    known text directly — no transcription, no sequence matching.

    Blocks are joined and aligned in one pass; word timings are sliced back to
    blocks by word count (we built the joined text, so order is exact).
    """

    def __init__(self, model_name: str = "small", device: str | None = None):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load(self):
        if self._model is None:
            import stable_whisper

            self._model = stable_whisper.load_model(self.model_name, device=self.device)
        return self._model

    def audio_duration(self, audio_path: Path) -> float:
        import torchaudio

        info = torchaudio.info(str(audio_path))
        return info.num_frames / info.sample_rate

    def align(self, audio_path: Path, blocks: list[str], lang: str,
              display_blocks: list[str] | None = None) -> list[Span]:
        """`blocks` is what the aligner listens for — normalised, digits spoken.
        `display_blocks` is the verbatim script, and is what `Span.words` carry.

        They are different strings on purpose: "2015" has to be *heard* as "two
        thousand and fifteen" and *shown* as "2015". Reading word text off the
        aligner's input would put the spoken form on screen, which the project
        forbids outright.
        """
        display = display_blocks if display_blocks is not None else blocks
        duration = self.audio_duration(audio_path)
        model = self._load()
        text = "\n".join(blocks)
        try:
            result = model.align(str(audio_path), text, language=lang)
        except Exception:
            # Falling back silently once cost a full set of real timings: the
            # run looked successful and every span came out [ESTIMATED]. The
            # fallback stays — a failed alignment must never fail the render —
            # but it announces itself now.
            logging.exception("alignment failed, falling back to proportional "
                              "timing — every span will be [ESTIMATED]")
            return proportional_spans(display, duration)

        words = [w for seg in result.segments for w in seg.words]
        counts = [len(b.split()) for b in blocks]
        # slice the word stream back into blocks
        spans: list[Span] = []
        pos = 0
        for i, n in enumerate(counts):
            chunk = words[pos:pos + n]
            pos += n
            timed = [w for w in chunk if w.end > w.start >= 0]
            if not timed:
                # Untimed for now; the span gets its slice below, and the words
                # get theirs once the span has one.
                spans.append(Span(i, -1.0, -1.0, 0.0, True,
                                  [Word(t, -1.0, -1.0)
                                   for t in display[i].split()]))
                continue
            conf = sum(getattr(w, "probability", 0.0) or 0.0 for w in timed) / len(timed)
            # Text comes from the script, timings come from the engine. Pairing
            # positionally rather than reading the engine's own strings is what
            # keeps the caption verbatim: stable-ts re-tokenises — it moves
            # punctuation and splits contractions — and none of that may reach
            # the screen.
            #
            # Positional pairing only holds while normalisation left the token
            # count alone, which is every block without digits. "2015" becomes
            # three spoken words, so in those blocks (flagged `had_digits` in
            # shots.json) the two streams cannot be zipped, and the verbatim
            # words are spread evenly across the block's measured span instead.
            # Block boundaries stay exact either way; only word placement inside
            # a digit-bearing block is approximate.
            toks = display[i].split()
            if len(toks) == len(chunk):
                block_words = [Word(tok, w.start, w.end) if w.end > w.start >= 0
                               else Word(tok, -1.0, -1.0)
                               for tok, w in zip(toks, chunk)]
                _fill_word_gaps(block_words, timed[0].start, timed[-1].end)
            else:
                step = (timed[-1].end - timed[0].start) / max(len(toks), 1)
                block_words = [Word(tok, timed[0].start + k * step,
                                    timed[0].start + (k + 1) * step)
                               for k, tok in enumerate(toks)]
            spans.append(Span(i, timed[0].start, timed[-1].end, conf, False,
                              block_words))

        _fill_estimated(spans, duration)
        for s in spans:
            if any(w.t_start < 0 for w in s.words):
                _fill_word_gaps(s.words, s.t_start, s.t_end)
        # spans mark speech; shot boundaries must tile the timeline: each shot
        # runs to the next shot's speech onset (silence belongs to the shot before it)
        for i in range(len(spans) - 1):
            spans[i].t_end = spans[i + 1].t_start
        if spans:
            spans[0].t_start = 0.0
            spans[-1].t_end = duration
        return spans


def _fill_word_gaps(words: list[Word], t_start: float, t_end: float) -> None:
    """Give untimed words (t_start < 0) a share of the hole around them.

    Same shape as _fill_estimated, one level down. A word the engine could not
    place still has to carry *some* time, or the caption segmenter would emit a
    cue with no duration.
    """
    n = len(words)
    i = 0
    while i < n:
        if words[i].t_start >= 0:
            i += 1
            continue
        run_start = i
        while i < n and words[i].t_start < 0:
            i += 1
        run_end = i  # exclusive
        prev = words[run_start - 1].t_end if run_start > 0 else t_start
        nxt = words[run_end].t_start if run_end < n else t_end
        width = max(nxt - prev, 0.0) / (run_end - run_start)
        for k, j in enumerate(range(run_start, run_end)):
            words[j].t_start = prev + k * width
            words[j].t_end = words[j].t_start + width


def _fill_estimated(spans: list[Span], duration: float) -> None:
    """Fill unaligned spans (t_start < 0) by splitting the hole between their
    timed neighbours evenly — contiguous runs share the gap."""
    n = len(spans)
    i = 0
    while i < n:
        if spans[i].t_start >= 0:
            i += 1
            continue
        run_start = i
        while i < n and spans[i].t_start < 0:
            i += 1
        run_end = i  # exclusive
        prev_end = spans[run_start - 1].t_end if run_start > 0 else 0.0
        next_start = spans[run_end].t_start if run_end < n else duration
        width = max(next_start - prev_end, 0.0) / (run_end - run_start)
        for k, j in enumerate(range(run_start, run_end)):
            spans[j].t_start = prev_end + k * width
            spans[j].t_end = spans[j].t_start + width
            spans[j].estimated = True
