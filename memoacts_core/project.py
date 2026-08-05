"""Project I/O: script parsing, shots.json (frozen schema — docs/SHOTS_SCHEMA.md),
crop CSV files, human-readable report.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import SCHEMA_VERSION
from .align import Span
from .schedule import Motion, ShotSchedule


#: A heading that names a shot: "### S14", "## S 3", "# s07".
_SHOT_HEADING_RE = re.compile(r"^#{1,6}\s*S\s*(\d+)\b", re.IGNORECASE)

#: An asset reference inside the storyboard: "[[Reims-Signing.jpg]]".
_ASSET_REF_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class ScriptShot:
    """One shot as written: what is spoken, and what the storyboard asks for."""
    text: str = ""                                  # verbatim narration
    label: str = ""                                 # "S14", "" in plain mode
    assets: list[str] = field(default_factory=list)  # [[refs]], in order

    @property
    def silent(self) -> bool:
        return not self.text.strip()


def _harvest(line: str, shot: ScriptShot) -> str:
    """Pull [[asset]] refs out of a line and return the line without them."""
    for ref in _ASSET_REF_RE.findall(line):
        ref = ref.strip()
        if ref and ref not in shot.assets:
            shot.assets.append(ref)
    return _ASSET_REF_RE.sub("", line)


def parse_script_shots(path: Path) -> list[ScriptShot]:
    """Parse a script into shots, in either of two layouts.

    **Storyboard layout** — used when the file contains shot headings like
    ``### S14``. A heading opens a shot; plain lines are its narration; lines
    starting with ``>`` are storyboard directions, which are *not* spoken.
    Anything before the first shot heading is a document title and is dropped.

    **Plain layout** (SPEC §4, unchanged) — no shot headings, so one shot per
    blank-line-separated block, exactly as before.

    Both layouts harvest ``[[asset.jpg]]`` references and strip them from the
    narration, so a filename written into the text can never be spoken or burnt
    into a subtitle.

    A shot whose narration is empty is kept as a **silent shot**: it holds
    screen time without a line, which the alignment fills from the pause
    between its neighbours. Dropping it instead would shift every later shot.
    """
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    has_headings = any(_SHOT_HEADING_RE.match(ln) for ln in lines)

    shots: list[ScriptShot] = []

    if has_headings:
        current: ScriptShot | None = None
        buf: list[str] = []

        def close() -> None:
            if current is not None:
                current.text = " ".join(" ".join(buf).split())
                shots.append(current)

        for ln in lines:
            m = _SHOT_HEADING_RE.match(ln)
            if m:
                close()
                current = ScriptShot(label=f"S{int(m.group(1)):02d}")
                buf = []
                continue
            if current is None:
                continue                      # preamble / document title
            stripped = ln.strip()
            if not stripped:
                continue
            body = _harvest(ln, current)
            if stripped.startswith("#"):
                continue                      # sub-heading, not narration
            if body.lstrip().startswith(">"):
                continue                      # storyboard direction
            buf.append(body)
        close()
    else:
        for block in raw.split("\n\n"):
            shot = ScriptShot()
            kept = []
            for ln in block.splitlines():
                body = _harvest(ln, shot)
                s = body.strip()
                if not s or s.startswith("#") or s.startswith(">"):
                    continue
                kept.append(body)
            shot.text = " ".join(" ".join(kept).split())
            if shot.text or shot.assets:
                shots.append(shot)

    return shots


def parse_script(path: Path) -> list[str]:
    """Narration text per shot (SPEC §4). See `parse_script_shots` for layouts."""
    return [s.text for s in parse_script_shots(path)]


def list_images(images_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
    return sorted(p for p in images_dir.iterdir() if p.suffix.lower() in exts)


def resolve_shot_images(shots: list[ScriptShot], images: list[Path]
                        ) -> tuple[list[Path], list[str]]:
    """Pick one still per shot, preferring what the storyboard asked for.

    A shot naming ``[[Reims-Signing.jpg]]`` gets that file. A shot naming
    nothing falls back to cycling the folder alphabetically, which is the
    zero-input behaviour SPEC §5.2 wants — defaults must produce a reel with no
    per-shot work.

    Returns `(one path per shot, warnings)`. A named file that does not exist is
    a warning and a fallback, never an exception: a storyboard is written before
    the assets are gathered, and a typo should not stop a run that can still
    show every other shot.
    """
    by_name = {p.name: p for p in images}
    lowered = {p.name.lower(): p for p in images}
    picked: list[Path] = []
    warnings: list[str] = []
    cycle = 0

    for i, shot in enumerate(shots, 1):
        chosen: Path | None = None
        for ref in shot.assets:
            hit = by_name.get(ref) or lowered.get(ref.lower())
            if hit is not None:
                chosen = hit
                break
            warnings.append(
                f"{shot.label or f'shot {i}'}: storyboard names {ref!r}, "
                f"which is not in images/")
        if chosen is None:
            chosen = images[cycle % len(images)]
            cycle += 1
        picked.append(chosen)

    return picked, warnings


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
