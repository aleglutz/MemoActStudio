"""`shots.csv` — the edit decisions, kept out of the script.

The script is what the narrator reads: clean voice-over, nothing else. Which
still goes with which line, where an archival fragment starts, what motion and
what look — those are edit decisions, and they change far more often than the
words do. Keeping them in a separate table means re-timing the edit never risks
touching the text that reaches the screen.

Format — a header row, then one row per shot you want to say something about.
Every column except `shot` is optional, blank cells mean "leave the default",
and a row starting with `#` is a comment:

    shot,media,in,motion,rate,anchor,effects,notes
    1,Berlin.jpg,,zoom_in,0.05,,archive_soft,opening
    0:21,MBK_KAPFILM_FINAL.mp4,2:14,static,,,,Tempelhof arrival

`shot` addresses the shot either by **number** (1-based, as in the shot report)
or by the **cue timecode** written in the script. Cues are the safer handle:
inserting a line renumbers every shot after it, but a cue still points at the
line it was written for. A value that matches nothing is a warning, never a
crash — a shot list is edited while the script is still moving.

Shots absent from the table keep every default, so the table stays as short as
the number of decisions actually made.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from .project import ScriptShot

#: Media that is a still. Anything else with a known video extension is footage.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

_TIMECODE_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$")


def parse_timecode(value: str) -> float | None:
    """"2:14" -> 134.0, "1:02:33" -> 3753.0, "7.5" -> 7.5. Blank -> None."""
    value = (value or "").strip()
    if not value:
        return None
    m = _TIMECODE_RE.match(value)
    if m:
        h, mnt, sec = m.group(1), m.group(2), m.group(3)
        return (int(h) * 3600 if h else 0) + int(mnt) * 60 + float(sec)
    try:
        return float(value)
    except ValueError:
        return None


@dataclass
class ShotEdit:
    """One row of `shots.csv`, already typed."""
    key: str = ""                      # as written, for error messages
    index: int | None = None           # 1-based shot number, if given that way
    cue: float | None = None           # cue timecode, if given that way
    media: str = ""
    media_in: float | None = None      # in-point for footage
    motion: str = ""
    rate: float | None = None
    anchor: str = ""
    effects: str = ""
    notes: str = ""

    @property
    def is_video(self) -> bool:
        return Path(self.media).suffix.lower() in VIDEO_EXTS


@dataclass
class ResolvedShot:
    """What a shot ends up with once script and shot list are combined."""
    media: Path | None = None
    media_in: float | None = None
    motion: str = ""
    rate: float | None = None
    anchor: str = ""
    effects: str = ""

    @property
    def is_video(self) -> bool:
        return self.media is not None and self.media.suffix.lower() in VIDEO_EXTS


def read_shot_list(path: Path) -> list[ShotEdit]:
    """Read `shots.csv`. A missing file is not an error — it means no overrides."""
    if not path.exists():
        return []

    rows: list[ShotEdit] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for raw in csv.DictReader(fh):
            if raw is None:
                continue
            # Normalise headers once: users type "Shot", " media ", "IN".
            row = {(k or "").strip().lower(): (v or "").strip()
                   for k, v in raw.items() if k}
            key = row.get("shot", "")
            if not key or key.startswith("#"):
                continue

            edit = ShotEdit(
                key=key,
                media=row.get("media", ""),
                media_in=parse_timecode(row.get("in", "")),
                motion=row.get("motion", ""),
                anchor=row.get("anchor", ""),
                effects=row.get("effects", ""),
                notes=row.get("notes", ""),
            )
            if ":" in key:
                edit.cue = parse_timecode(key)
            else:
                try:
                    edit.index = int(key)
                except ValueError:
                    edit.cue = parse_timecode(key)
            try:
                edit.rate = float(row["rate"]) if row.get("rate") else None
            except ValueError:
                edit.rate = None
            rows.append(edit)
    return rows


def apply_shot_list(shots: list[ScriptShot], edits: list[ShotEdit],
                    project: Path) -> tuple[list[ResolvedShot], list[str]]:
    """Combine the script with the shot list.

    Media is looked up in `images/` then `video/`, so the table carries a bare
    filename and never a path. A named file that is missing warns and leaves the
    shot on its default — a shot list is written before the assets are gathered,
    and one typo should not stop a run that can still show every other shot.
    """
    resolved = [ResolvedShot() for _ in shots]
    warnings: list[str] = []

    by_cue: dict[float, int] = {
        s.cue: i for i, s in enumerate(shots) if s.cue is not None}

    for edit in edits:
        idx: int | None = None
        if edit.index is not None:
            if 1 <= edit.index <= len(shots):
                idx = edit.index - 1
            else:
                warnings.append(
                    f"shots.csv: shot {edit.key} is out of range 1..{len(shots)}")
        elif edit.cue is not None:
            idx = by_cue.get(edit.cue)
            if idx is None:
                warnings.append(
                    f"shots.csv: cue {edit.key} matches no block in script.md")
        else:
            warnings.append(f"shots.csv: cannot read shot key {edit.key!r}")
        if idx is None:
            continue

        target = resolved[idx]
        if edit.media:
            found = None
            for folder in ("images", "video"):
                cand = project / folder / edit.media
                if cand.exists():
                    found = cand
                    break
            if found is None:
                warnings.append(
                    f"shots.csv: shot {edit.key} names {edit.media!r}, "
                    f"which is in neither images/ nor video/")
            else:
                target.media = found
                target.media_in = edit.media_in

        if edit.media_in is not None and not target.is_video:
            warnings.append(
                f"shots.csv: shot {edit.key} has an in-point but its media is "
                f"not footage; the in-point is ignored")

        target.motion = edit.motion or target.motion
        target.rate = edit.rate if edit.rate is not None else target.rate
        target.anchor = edit.anchor or target.anchor
        target.effects = edit.effects or target.effects

    return resolved, warnings


def write_template(path: Path, shots: list[ScriptShot]) -> Path:
    """Write a shot list pre-filled with one row per shot, media left blank.

    Starting from the script's own cues means the operator fills in decisions
    rather than transcribing timings, and a cue typo becomes impossible.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "media", "in", "motion", "rate", "anchor",
                    "effects", "notes"])
        for i, s in enumerate(shots, 1):
            cue = ("" if s.cue is None
                   else f"{int(s.cue) // 60}:{int(s.cue) % 60:02d}")
            w.writerow([cue or i, "", "", "", "", "", "",
                        s.text[:60] + ("…" if len(s.text) > 60 else "")])
    return path
