"""`shots.csv` — the edit decisions, kept out of the script.

The script is what the narrator reads: clean voice-over, nothing else. Which
still goes with which line, where an archival fragment starts, what motion and
what look — those are edit decisions, and they change far more often than the
words do. Keeping them in a separate table means re-timing the edit never risks
touching the text that reaches the screen.

Format — a header row, then one row per shot you want to say something about.
Every column except `shot` is optional, blank cells mean "leave the default",
and a row starting with `#` is a comment:

    shot,media,in,motion,rate,anchor,speed,focus,path,label,credit,effects,notes
    1,Berlin.jpg,,zoom_in,0.05,,,,Berlin,archive_soft,opening
    0:21,MBK_KAPFILM_FINAL.mp4,2:14,static,,,0.4,,,,Tempelhof arrival in slow motion
    0:41,Reims-Signing.jpg,,zoom_in,,,,0.44 0.62 0.30,,,push in to the signature

`fit` as the motion shows the media whole, full width, with bands above and
below — the honest framing for landscape footage, which a 9:16 crop would have
to enlarge.

`in` and `speed` apply to footage only: `in` is where in the fragment the shot
starts, `speed` its playback rate (0.4 is slow motion). How *much* footage gets
used is not stated — the shot's duration comes from the narration, and the
fragment bends to it.

`label` is the tag burnt into the top-right corner — a place or a person, for
the shots where the narration does not say which. It holds a few seconds from
the shot's start, not the whole shot.

`focus` is what the shot is *about*: a point in the image and how much of the
width to end on, all as fractions — `0.44 0.62 0.30` means "centre at 44 % across
and 62 % down, ending on the middle 30 % of the width". Separate with spaces,
commas or slashes. `zoom_in` arrives there, `zoom_out` leaves from there,
`static` holds it; the pans ignore it. It replaces `rate` rather than joining it
— see `schedule.Motion.focus` for why a rate cannot reach a detail.

`path` is several stops instead of one: `t:cx,cy[,w]` separated by spaces, where
`t` is a fraction of the shot. It is what a `focus` cannot say — a shot that
*reads* something, the title of a sheet and then the number in its corner. The
width carries forward from the stop before it, so a move at one scale is short
to write; two stops sharing a `t` hold still between them. A path replaces the
preset, the rate and the focus outright.

The window is a crop **inside** the picture and cannot leave it, so a stop too
near an edge is approached rather than centred, and the shot report says which
and where it landed. A corner genuinely in the middle of the frame needs a
surface behind the paper: that is `tools/render_move.py`, and a composite.

**How tight either may go (changed 2026-09-01).** A window narrower than the
output frame enlarges the picture, and that is now allowed: the panel prints the
factor while the rectangle is drawn, the shot report names it, and the render's
`on_upscale` decides whether it warns, refuses or stays quiet. The project's
rule is that enlargement is never *silent*, not that it never happens — an
editor pulling one face out of a large scan was being refused by a limit written
for a small one. The **upper** bound is different and still holds: past the
whole 9:16 window there is no more picture, which is arithmetic.

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

from .project import MEDIA_DIRS, ScriptShot

#: Media that is a still. Anything else with a known video extension is footage.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

_TIMECODE_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$")
_FOCUS_SEP = re.compile(r"[,\s/]+")


def parse_focus(value: str) -> tuple[float, float, float] | str | None:
    """`"0.44 0.62 0.30"` -> `(0.44, 0.62, 0.30)`. Blank -> None.

    Returns a plain string on bad input — the reason, for the caller to warn
    with. Fractions rather than pixels so the value survives the source being
    re-cropped or re-scaled, which happens to these images repeatedly.
    """
    value = (value or "").strip()
    if not value:
        return None
    parts = [p for p in _FOCUS_SEP.split(value) if p]
    if len(parts) != 3:
        return f"expected three numbers (cx cy w), got {len(parts)}"
    try:
        cx, cy, w = (float(p) for p in parts)
    except ValueError:
        return "expected numbers"
    if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
        return "cx and cy are fractions of the source, so both must be 0..1"
    if not (0.0 < w <= 1.0):
        return "w is a fraction of the source width, so it must be >0 and <=1"
    return cx, cy, w


def parse_path(value: str) -> list[tuple[float, float, float, float]] | str | None:
    """`t:cx,cy[,w]` stops, whitespace-separated. A string back is the complaint.

    Written the way the focus column is written, with a time in front:

        0:0.281,0.137,0.35  0.14:0.281,0.137  0.44:0.891,0.045

    `w` carries forward from the stop before it, because a move at one scale —
    a sheet travelling under a fixed camera — is the ordinary case and should
    not have to repeat itself. Two stops sharing a `t` are a hold.
    """
    value = (value or "").strip()
    if not value:
        return None
    out: list[tuple[float, float, float, float]] = []
    w = None
    for token in value.split():
        head, _, rest = token.partition(":")
        if not rest:
            return f"{token!r} has no time in front of it — write t:cx,cy[,w]"
        parts = rest.split(",")
        if len(parts) not in (2, 3):
            return f"{token!r}: expected t:cx,cy or t:cx,cy,w"
        try:
            t = float(head)
            cx, cy = float(parts[0]), float(parts[1])
            if len(parts) == 3:
                w = float(parts[2])
        except ValueError:
            return f"{token!r} is not numbers"
        if w is None:
            return f"{token!r}: the first stop has to say its width"
        if not 0.0 <= t <= 1.0:
            return f"{token!r}: t is a fraction of the shot, got {t}"
        if not 0.0 < w <= 1.0:
            return f"{token!r}: w is a fraction of the source width, got {w}"
        out.append((t, cx, cy, w))
    if len(out) < 2:
        return "a path needs at least two stops; one stop is a focus"
    return out


def write_path(path: list[tuple[float, float, float, float]] | None) -> str:
    """A path back into its cell, dropping a width that repeats the last one."""
    if not path:
        return ""
    out, last = [], None
    for t, cx, cy, w in path:
        cell = f"{t:g}:{cx:.3f},{cy:.3f}"
        if last is None or abs(w - last) > 1e-9:
            cell += f",{w:.3f}"
        last = w
        out.append(cell)
    return " ".join(out)


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
    speed: float | None = None         # footage playback rate; 1.0 = as shot
    focus: str = ""                    # raw; parsed in apply_shot_list so a bad
    path: str = ""                     # raw too, and for the same reason
    label: str = ""                    # value can warn with its row's key
    credit: str = ""                   # source line, held for the whole shot
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
    speed: float | None = None
    focus: tuple[float, float, float] | None = None
    path: list[tuple[float, float, float, float]] | None = None
    label: str = ""
    credit: str = ""
    effects: str = ""

    @property
    def is_video(self) -> bool:
        return self.media is not None and self.media.suffix.lower() in VIDEO_EXTS


#: The columns `write_template` emits, and the order a file gets when the
#: editor writes one from nothing. A file already on disk keeps its own header.
COLUMNS = ("shot", "media", "in", "motion", "rate", "anchor", "speed",
           "focus", "path", "label", "credit", "effects", "notes")


@dataclass
class ShotTable:
    """`shots.csv` exactly as it sits on disk, so it can be written back.

    `ShotEdit` is the typed view the pipeline consumes; it deliberately drops
    what it does not understand. This keeps the rest: the header as the author
    spelled it, any column this code has never heard of, and the `#` comment
    rows. The table editor writes through here, so a file the author has been
    keeping by hand survives being opened in the GUI and saved untouched.
    """
    fieldnames: list[str] = field(default_factory=lambda: list(COLUMNS))
    rows: list[dict[str, str]] = field(default_factory=list)

    def data_rows(self) -> list[dict[str, str]]:
        """The rows that address a shot — comments and blank keys dropped."""
        return [r for r in self.rows if row_key(r) and not row_key(r).startswith("#")]


def row_key(row: dict[str, str]) -> str:
    """The `shot` cell of a row, whatever case the header was written in.

    Public because the table editor addresses rows too, and a second guess at
    which column names the shot is a second thing to keep in step.
    """
    for k, v in row.items():
        if (k or "").strip().lower() == "shot":
            return (v or "").strip()
    return ""


def read_table(path: Path) -> ShotTable:
    """Read `shots.csv` verbatim. A missing file gives an empty table."""
    if not path.exists():
        return ShotTable()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or COLUMNS)
        rows = [{k: (v if isinstance(v, str) else "") for k, v in raw.items()
                 if k is not None}
                for raw in reader if raw is not None]
    return ShotTable(fieldnames=fieldnames, rows=rows)


def write_table(path: Path, table: ShotTable) -> Path:
    """Write a `ShotTable` back, header and unknown columns intact.

    `\\r\\n` is `csv.writer`'s own default and what every `shots.csv` in this
    repository already uses, so a save with no edits is a no-op to git.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = table.fieldnames or list(COLUMNS)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in table.rows:
                w.writerow({k: row.get(k, "") for k in fieldnames})
        # Replace rather than truncate-and-write: a crash mid-write would
        # otherwise leave the author's edit decisions half gone, and they are
        # not regenerable.
        tmp.replace(path)
    except OSError as exc:
        # The `.tmp` must not survive a failure. One was left behind on
        # 2026-09-01 and sat in the project looking like a half-saved edit.
        tmp.unlink(missing_ok=True)
        raise TableLocked(_why_locked(path, exc)) from exc
    return path


class TableLocked(OSError):
    """`shots.csv` could not be replaced — said in words a person can act on."""


def _why_locked(path: Path, exc: OSError) -> str:
    """Turn a Windows error number into the sentence that names the cure.

    Worth the twenty lines: the raw failure is `[WinError 5] Access is denied`
    on a file the process can demonstrably open for writing, which reads as a
    bug in the tool rather than as a spreadsheet holding the file. It is the
    spreadsheet. LibreOffice leaves its own evidence next to the file, so when
    that is there, say so exactly.
    """
    lock = path.with_name(f".~lock.{path.name}#")
    if lock.exists():
        return (f"{path.name} is open in LibreOffice — its lock file "
                f"{lock.name} is sitting next to it. Close the file there and "
                f"save again; nothing has been lost.")
    if getattr(exc, "winerror", None) in (5, 32):
        return (f"{path.name} is open in another program, which is holding it "
                f"against being replaced — a spreadsheet, usually. Close it "
                f"there and save again; nothing has been lost.")
    return f"{path.name} could not be written: {exc}"


#: A row addressing a scene by the label the script gives it: `S01`, `s 7`.
_LABEL_KEY_RE = re.compile(r"^S\s*(\d+)$", re.IGNORECASE)


def parse_shot_key(key: str) -> tuple[int | None, float | None]:
    """Which shot a row addresses: `(index, cue)`, at most one of them set.

    Three spellings, because three are in use and all three are reasonable:

    * `12` — the shot number, which is what the editor writes.
    * `0:42` — the cue the script wrote for the block, which survives a scene
      being inserted above it where a number does not.
    * `S12` — the label the script gives the scene and the panel shows. Added
      2026-09-01: a person filling the file in by hand copies what they see, and
      what they see is `S12`. Before this it typed to neither an index nor a
      cue, and the row silently addressed nothing.
    """
    key = key.strip()
    if not key:
        return None, None
    if ":" in key:
        return None, parse_timecode(key)
    try:
        return int(key), None
    except ValueError:
        pass
    m = _LABEL_KEY_RE.match(key)
    if m:
        return int(m.group(1)), None
    return None, parse_timecode(key)


def mislabelled_comments(table: ShotTable) -> list[str]:
    """Rows commented out by a `#` that look like they were meant to address a shot.

    `## S01` in the shot column is what a person writes when they copy the
    script's own heading into the spreadsheet — and the file's format says a row
    starting with `#` is a comment, so the whole row is dropped without a word.
    Seen on 2026-09-01: thirty-four rows of a real project, every one of them
    ignored, the panel showing no media for any scene and nobody able to see
    why. The format still wins; it just stops being silent.
    """
    out = []
    for raw in table.rows:
        key = row_key(raw)
        if not key.startswith("#"):
            continue
        bare = key.lstrip("#").strip()
        index, cue = parse_shot_key(bare)
        if index is None and cue is None:
            continue
        decided = any((v or "").strip() for k, v in raw.items()
                      if (k or "").strip().lower() not in ("shot", ""))
        if decided:
            out.append(key)
    return out


def edits_from_table(table: ShotTable) -> list[ShotEdit]:
    """Type the rows of a table. Comments and unaddressed rows are dropped."""
    rows: list[ShotEdit] = []
    for raw in table.rows:
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
            focus=row.get("focus", ""),
            path=row.get("path", ""),
            label=row.get("label", ""),
            credit=row.get("credit", ""),
            effects=row.get("effects", ""),
            notes=row.get("notes", ""),
        )
        edit.index, edit.cue = parse_shot_key(key)
        try:
            edit.rate = float(row["rate"]) if row.get("rate") else None
        except ValueError:
            edit.rate = None
        try:
            edit.speed = float(row["speed"]) if row.get("speed") else None
        except ValueError:
            edit.speed = None
        rows.append(edit)
    return rows


def rows_with_edits(table: ShotTable) -> list[tuple[dict[str, str], ShotEdit]]:
    """Each addressing row paired with its typed form.

    `data_rows` and `edits_from_table` skip the same rows, so zipping them
    happens to line up — but "happens to" is how the two halves of this project
    drifted apart before. Pairing them here makes the guarantee the function's
    job rather than the caller's memory.
    """
    return list(zip(table.data_rows(), edits_from_table(table)))


def read_shot_list(path: Path) -> list[ShotEdit]:
    """Read `shots.csv`. A missing file is not an error — it means no overrides."""
    return edits_from_table(read_table(path))


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

    # A cue is a key, so a repeated one is an ambiguous key. Built by hand
    # rather than as a comprehension because a dict comprehension keeps the
    # LAST duplicate silently: a block pasted twice into script.md moved its
    # shot's media to the copy at the end of the reel and left the real block
    # on a cycled default, with nothing printed anywhere.
    by_cue: dict[float, int] = {}
    for i, s in enumerate(shots):
        if s.cue is None:
            continue
        if s.cue in by_cue:
            warnings.append(
                f"script.md: cue {int(s.cue) // 60}:{int(s.cue) % 60:02d} "
                f"opens more than one block (blocks {by_cue[s.cue] + 1} and "
                f"{i + 1}); shots.csv can only reach the first")
            continue
        by_cue[s.cue] = i

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
            # composites/ holds stacked frames and page moves built outside
            # the renderer. To a shot they are ordinary stills, so they resolve
            # the same way as anything in images/ — one search order, named
            # once in project.MEDIA_DIRS rather than repeated here, which is
            # how this list came to disagree with that one.
            for folder in MEDIA_DIRS:
                cand = project / folder / edit.media
                if cand.exists():
                    found = cand
                    break
            if found is None:
                warnings.append(
                    f"shots.csv: shot {edit.key} names {edit.media!r}, "
                    f"which is in none of {', '.join(MEDIA_DIRS)}")
            else:
                target.media = found
                target.media_in = edit.media_in

        if edit.media_in is not None and not target.is_video:
            warnings.append(
                f"shots.csv: shot {edit.key} has an in-point but its media is "
                f"not footage; the in-point is ignored")

        focus = parse_focus(edit.focus)
        if isinstance(focus, str):
            warnings.append(f"shots.csv: shot {edit.key} focus {edit.focus!r}: "
                            f"{focus}; ignored")
        elif focus is not None:
            target.focus = focus

        path = parse_path(edit.path)
        if isinstance(path, str):
            warnings.append(f"shots.csv: shot {edit.key} path: {path}; ignored")
        elif path is not None:
            target.path = path
            if focus is not None and not isinstance(focus, str):
                warnings.append(
                    f"shots.csv: shot {edit.key} has both a focus and a path; "
                    f"the path wins, and the focus is its first stop")

        target.motion = edit.motion or target.motion
        target.rate = edit.rate if edit.rate is not None else target.rate
        target.anchor = edit.anchor or target.anchor
        target.label = edit.label or target.label
        target.credit = edit.credit or target.credit
        if edit.speed is not None:
            if edit.speed <= 0:
                warnings.append(f"shots.csv: shot {edit.key} speed "
                                f"{edit.speed} must be > 0; ignored")
            elif not target.is_video:
                warnings.append(f"shots.csv: shot {edit.key} sets a speed but "
                                f"its media is not footage; ignored")
            else:
                target.speed = edit.speed
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
        w.writerow(list(COLUMNS))
        for i, s in enumerate(shots, 1):
            cue = ("" if s.cue is None
                   else f"{int(s.cue) // 60}:{int(s.cue) % 60:02d}")
            w.writerow([cue or i, "", "", "", "", "", "", "", "", "",
                        s.text[:60] + ("…" if len(s.text) > 60 else "")])
    return path
