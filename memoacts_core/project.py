"""Project I/O: script parsing, shots.json (frozen schema — docs/SHOTS_SCHEMA.md),
crop CSV files, human-readable report.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import SCHEMA_VERSION
from .align import Span
from .schedule import Motion, ShotSchedule


def parse_script(path: Path) -> list[str]:
    """One shot per blank-line-separated block (SPEC §4)."""
    blocks = [b.strip() for b in path.read_text(encoding="utf-8").split("\n\n")]
    return [" ".join(b.split()) for b in blocks if b]


def list_images(images_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
    return sorted(p for p in images_dir.iterdir() if p.suffix.lower() in exts)


def apply_shot_lead(spans: list[Span], lead_ms: int) -> list[Span]:
    """Cuts lead speech onset (SPEC §5.2): every boundary except t=0 moves
    earlier by lead; spans stay contiguous."""
    lead = lead_ms / 1000
    out = [Span(**asdict(s)) for s in spans]
    for i in range(1, len(out)):
        b = max(out[i].t_start - lead, out[i - 1].t_start + 0.1)
        out[i - 1].t_end = b
        out[i].t_start = b
    return out


def write_outputs(out_dir: Path, *, lang: str, fps: int, narration: str,
                  duration: float, lead_ms: int, blocks: list[str],
                  norm_blocks: list[str], digit_flags: list[bool],
                  spans: list[Span], images: list[Path], motions: list[Motion],
                  schedules: list[ShotSchedule], n_frames: list[int],
                  max_chunk: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    crops = out_dir / "crops"
    crops.mkdir(exist_ok=True)

    shots = []
    report = [f"MemoActs shot report — schema {SCHEMA_VERSION}",
              f"narration: {narration}  duration: {duration:.2f}s  fps: {fps}  "
              f"lang: {lang}  shot_lead: {lead_ms}ms",
              f"total frames: {sum(n_frames)}", ""]
    for i, (text, norm, span, img, mot, sched, nf) in enumerate(
            zip(blocks, norm_blocks, spans, images, motions, schedules, n_frames), 1):
        stem = f"shot_{i:02d}"
        chunk_files = []
        for ci, chunk in enumerate(sched.chunks(max_chunk)):
            suffix = f"_c{ci}" if len(sched.ws) > max_chunk else ""
            for k, v in chunk.csv().items():
                p = crops / f"{stem}{suffix}.{k}.csv"
                p.write_text(v, encoding="ascii")
            chunk_files.append(f"{stem}{suffix}")
        shots.append({
            "id": i, "text": text, "text_normalized": norm,
            "t_start": round(span.t_start, 3), "t_end": round(span.t_end, 3),
            "n_frames": nf, "estimated": span.estimated,
            "confidence": round(span.confidence, 3),
            "had_digits": digit_flags[i - 1],
            "image": img.name,
            "motion": {"preset": mot.preset, "rate": mot.rate, "anchor": mot.anchor},
            "clamped": sched.clamped, "max_zoom": round(sched.max_zoom, 2),
            "crops": chunk_files,
        })
        flags = "".join([
            " [ESTIMATED]" if span.estimated else "",
            " [DIGITS]" if digit_flags[i - 1] else "",
            " [CLAMPED]" if sched.clamped else "",
        ])
        report.append(
            f"shot {i:02d}  {span.t_start:7.2f}–{span.t_end:7.2f}s "
            f"({span.t_end - span.t_start:5.2f}s, {nf} fr)  conf {span.confidence:.2f}  "
            f"{img.name}  {mot.preset}@{mot.rate:.2f}  max_zoom {sched.max_zoom:.2f}x{flags}")
        report.append(f"         {text[:100]}")

    doc = {
        "schema_version": SCHEMA_VERSION, "fps": fps, "width": 1080, "height": 1920,
        "lang": lang, "narration": narration, "duration_s": round(duration, 3),
        "shot_lead_ms": lead_ms, "shots": shots,
    }
    (out_dir / "shots.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    return out_dir / "shots.json"
