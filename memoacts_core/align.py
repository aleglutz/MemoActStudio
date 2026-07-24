"""Known-text alignment behind a swappable interface (SPEC §5.1).

The engine choice (stable-ts) must never leak past this module: swapping
engines touches this file only, never callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Span:
    index: int
    t_start: float
    t_end: float
    confidence: float
    estimated: bool


class Aligner(Protocol):
    def align(self, audio_path: Path, blocks: list[str], lang: str) -> list[Span]: ...


def proportional_spans(blocks: list[str], duration: float) -> list[Span]:
    """Fallback: distribute duration over blocks by word count (SPEC §5.1 —
    never a failed run)."""
    weights = [max(len(b.split()), 1) for b in blocks]
    total = sum(weights)
    spans, t = [], 0.0
    for i, w in enumerate(weights):
        d = duration * w / total
        spans.append(Span(i, t, t + d, 0.0, True))
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

    def align(self, audio_path: Path, blocks: list[str], lang: str) -> list[Span]:
        duration = self.audio_duration(audio_path)
        model = self._load()
        text = "\n".join(blocks)
        try:
            result = model.align(str(audio_path), text, language=lang)
        except Exception:
            return proportional_spans(blocks, duration)

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
                spans.append(Span(i, -1.0, -1.0, 0.0, True))  # filled below
                continue
            conf = sum(getattr(w, "probability", 0.0) or 0.0 for w in timed) / len(timed)
            spans.append(Span(i, timed[0].start, timed[-1].end, conf, False))

        _fill_estimated(spans, duration)
        # spans mark speech; shot boundaries must tile the timeline: each shot
        # runs to the next shot's speech onset (silence belongs to the shot before it)
        for i in range(len(spans) - 1):
            spans[i].t_end = spans[i + 1].t_start
        if spans:
            spans[0].t_start = 0.0
            spans[-1].t_end = duration
        return spans


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
