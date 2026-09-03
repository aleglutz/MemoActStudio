"""The pipeline as four calls — one orchestration, two doors.

`tools/` and the ComfyUI node pack were separately re-implementing the same
sequence, and they drifted: the nodes never learned to read `shots.csv`, called
the aligner without the verbatim text, and carried subtitle defaults the core
had since moved on from. Nothing prevented that except attention, which is not
a mechanism. Everything between `argparse` and `print` now lives here, so the
CLI and the graph are demonstrably the same code path and the phrasing of what
they report is written once.

    read = read_project(proj)                  # instant: what is on disk
    al   = align_project(proj, read, lang="en")  # slow: audio against text
    comp = compose_project(proj, read, al)       # instant: the shot table
    res  = render_project(proj, comp.doc)        # long: the reel

The split is not cosmetic. Alignment is the only expensive step and it depends
on nothing but the script and the recording, so composing again after an edit to
`shots.csv` costs nothing — which is what makes the edit loop usable in a
workshop. `read_project` is separate for the same reason from the other side:
the interface has to be able to show what it found before anything slow runs.

Nothing here prints. Informational lines go to a `progress` callback, warnings
come back on the result, and both are already phrased for a human — so the CLI
and the node say the same words about the same fact.
"""
from __future__ import annotations

import json
import warnings as _warnings
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image

from . import sfx as sfxlib
from . import subs
from .align import Aligner, Span, StableTsAligner, proportional_spans
from .effects import EffectStack, PRESETS, preset
from .normalize import normalize_block
from .project import (MEDIA_DIRS, ScriptShot, apply_shot_lead,
                      escaped_headings, find_narration, list_images,
                      parse_script_shots, resolve_media, resolve_shot_images,
                      write_outputs)
from .render import ShotRender, render_reel
from .schedule import FOCUSABLE, Motion, compute, default_motion, frames_for
from .shotlist import (ResolvedShot, apply_shot_list, edits_from_table,
                       mislabelled_comments, parse_shot_key, read_table,
                       row_key, write_table)
from .video import is_video, probe

#: `progress(stage, done, total, message, preview)`.
#:
#: `stage` is one of "align", "compose", "subtitles", "render". `total` of 0
#: means the step cannot report how much is left — alignment is one opaque call
#: into stable-whisper and there is no honest fraction to give. A non-empty
#: `message` is a line meant to be shown as written. `preview` is a frame, sent
#: only where there is one to look at.
Progress = Callable[..., None]


class ProjectError(ValueError):
    """A project cannot be read — no narration, no script, no images."""


def _noop(stage: str, done: int = 0, total: int = 0, message: str = "",
          preview: Image.Image | None = None) -> None:
    pass


def console_progress(prefix: str = "") -> Progress:
    """A `Progress` that prints the lines and drops the counters and frames.

    Every door onto this pipeline wants exactly this, and four of them had
    written it out: two in `tools/`, byte for byte identical, and two in the
    node layer with a `[MemoActs]` prefix. The phrasing is the pipeline's, on
    purpose — two doors describing the same fact differently is the drift this
    module exists to make impossible — so the adapter belongs beside the type
    it adapts.
    """
    def progress(stage: str, done: int = 0, total: int = 0, message: str = "",
                 preview: Image.Image | None = None) -> None:
        if message:
            print(f"{prefix}{message}")
    return progress


@dataclass
class ProjectRead:
    """What is on disk, before anything slow has run.

    This is the Project node's whole job, and the first thing a person wants to
    know: is my recording where the tool looks, did it find my images, and which
    shot got which one.
    """
    project: Path
    narration: Path
    script_shots: list[ScriptShot]
    blocks: list[str]
    images: list[Path]
    picks: list[ResolvedShot]
    media: list[Path]                       # per shot, after shots.csv wins
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Alignment:
    """Timings for a script against a recording. The expensive, stable part.

    Deliberately holds no `fps` and no shot lead: both are cheap to change and
    doing so must not cost another pass over the audio.
    """
    spans: list[Span]                       # raw, before the shot lead
    duration: float
    norm_blocks: list[str]
    digit_flags: list[bool]
    lang: str
    estimated: bool                         # true when the aligner was skipped
                                            # or fell back to proportional
    warnings: list[str] = field(default_factory=list)


@dataclass
class Composition:
    """The shot table: `shots.json`, its report, and where they were written."""
    doc: dict[str, Any]
    report: str
    path: Path | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class SoundDesign:
    """The sound cues, typed and placed against a shot table.

    `is_template` says the project had no `sfx.csv` and this is the starter one
    — every row a comment. It matters because "nothing is planned yet" and "the
    plan is empty" want different things said about them.
    """
    csv: Path
    table: sfxlib.CueTable
    cues: list[sfxlib.Cue]
    placed: list[sfxlib.Placed]
    is_template: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class RenderOptions:
    """Everything `render_reel.py`'s flags decide, with the same defaults."""
    subs: bool = True
    sub_size: int = 56
    segment: bool = True
    plate: float | None = None              # None keeps subs.SubStyle's own
    labels: bool = True
    label_hold: float = 3.0
    min_duration: float = 1.0               # shortest a caption may stay up
    crf: int = 19
    on_upscale: str = "warn"
    effects: str = "none"                   # fallback for shots setting none
    sfx: Path | None = None                 # the sound design layer, summed
                                            # with the narration at the mux


@dataclass
class RenderResult:
    path: Path
    frames: int
    duration_s: float
    drift_s: float
    ass: Path | None = None
    srt: Path | None = None
    cues: int = 0
    wrapped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


#: What a project is before anybody has put anything in it: four folders, the
#: media folders inside one of them, and the two files a person fills in.
#:
#: Named once, here, because there are now two doors onto making one — the
#: `POST /memoacts/project` route and the Set Narration node — and two lists of
#: "what a project is" is one too many. "sources" is named alongside
#: `MEDIA_DIRS` even though it prefixes all of them, so that a project with no
#: pictures yet still has somewhere to put the recording.
PROJECT_DIRS = ("sources", *MEDIA_DIRS, "generated", "out", "archive")


#: Characters a project name may not contain, because a name is a folder name
#: and nothing else. A path separator would let a graph write outside
#: `projects/`, and a leading dot hides the folder from the picker that is
#: supposed to list it.
BAD_NAME_CHARS = ("/", "\\", ":", "*", "?", '"', "<", ">", "|")


def clean_project_name(name: str) -> str:
    """A project name, or a refusal that says which character was the problem.

    One list, for the same reason `create_project` is one function: the node
    and the `POST /memoacts/project` route both answer "is this a folder name",
    and until 2026-09-03 they answered differently — the route allowed
    `: * ? " < > |`, every one of which Windows refuses in a path, so a name
    typed in the panel could be accepted and then fail to become a folder.
    """
    name = (name or "").strip().strip(".")
    if not name:
        raise ProjectError("give the project a name — it becomes the folder "
                           "your script, your recording and your pictures "
                           "live in")
    bad = [c for c in BAD_NAME_CHARS if c in name]
    if bad:
        raise ProjectError(f"{''.join(bad)!r} cannot be in a project name: it "
                           f"is a folder name, not a path")
    return name


def create_project(folder: Path) -> bool:
    """Make an empty project. True if it was made, False if it already existed.

    Idempotent, which is the whole difference between this and a wizard: the
    Set Narration node calls it on every queue, and a second take must not be
    an error. An existing folder is left exactly as it is.

    Deliberately not a template with placeholder shots. An empty `script.md` is
    honest about what has to happen next; a pretend one gets rendered by
    accident and teaches nothing. `shots.csv` gets its header and no rows,
    because the header is the format and rows would be somebody's guesses.
    """
    from .shotlist import ShotTable, write_table

    if folder.is_dir():
        return False
    for d in PROJECT_DIRS:
        (folder / d).mkdir(parents=True, exist_ok=True)
    (folder / "script.md").write_text("", encoding="utf-8")
    write_table(folder / "shots.csv", ShotTable())
    return True


@dataclass
class NarrationWrite:
    """What `set_narration` did, in the terms the report needs."""
    path: Path
    created: bool                   # the project folder was made just now
    changed: bool                   # what is on disk is not what was there
    seconds: float
    channels: int
    sample_rate: int
    superseded: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def set_narration(project: Path, data, sample_rate: int, *,
                  create: bool = True) -> NarrationWrite:
    """Put a recording into a project as `sources/narration.wav`.

    This is the seam between the voice workflow and the reel, and it exists
    because the alternative is a person dragging a file out of ComfyUI's output
    folder into a project — a terminal's job done with a mouse, which is the
    thing the interface is supposed to remove.

    Three things it does that a plain save node cannot, each for a failure that
    has actually happened here:

    **It writes WAV and only WAV.** `find_narration` globs `narration.*` and
    takes the first alphabetically, so a `narration.mp3` left in the folder
    beats a `narration.wav` written after it, silently and for as long as both
    exist. Every other `narration.*` beside it is moved into `archive/` —
    moved, never deleted — and named in the report.

    **It leaves the file alone when the samples are identical.** Alignment is
    cached on this file's mtime, so a re-queued graph that rewrote the same
    audio would cost ninety seconds of Whisper for nothing. That is also why
    the comparison goes through a temporary file: what has to match is the
    encoded form, not the array.

    **It keeps the rate and the channel count it was given.** The sound-design
    bed is resampled to 44.1 kHz stereo because it is being mixed; a narration
    is muxed, not mixed, and the one thing this project asks of the voice is
    that nothing happens to it that nobody asked for.
    """
    import numpy as np

    created = create_project(project) if create else False
    if not project.is_dir():
        raise ProjectError(f"no such project folder: {project}")
    for d in PROJECT_DIRS:          # an older project may predate a folder
        (project / d).mkdir(parents=True, exist_ok=True)

    arr = np.ascontiguousarray(np.asarray(data, dtype=np.float32))
    if arr.ndim == 1:
        arr = arr[None, :]
    if arr.ndim != 2 or not arr.size:
        raise ProjectError("the audio arrived with no samples in it")

    path = project / "sources" / "narration.wav"
    tmp = path.with_suffix(".wav.tmp")
    sfxlib.write_wav(tmp, arr, int(sample_rate))
    changed = not (path.exists() and path.read_bytes() == tmp.read_bytes())
    if changed:
        tmp.replace(path)
    else:
        tmp.unlink()

    superseded: list[Path] = []
    for other in sorted((project / "sources").glob("narration.*")):
        if other == path:
            continue
        dest = project / "archive" / f"superseded_{other.name}"
        n = 2
        while dest.exists():
            dest = (project / "archive"
                    / f"superseded_{other.stem}_{n}{other.suffix}")
            n += 1
        other.replace(dest)
        superseded.append(dest)

    warnings: list[str] = []
    # find_narration reads sources/ first, so one at the project root cannot win
    # any more. But it is still a second recording in the project and somebody
    # put it there on purpose: say so, do not move somebody's file for them.
    stray = sorted(p.name for p in project.glob("narration.*") if p.is_file())
    if stray:
        warnings.append(
            f"there is also {', '.join(stray)} in the project root; sources/ "
            f"is read first, so it is dead weight now rather than a hazard")

    return NarrationWrite(
        path=path, created=created, changed=changed,
        seconds=arr.shape[1] / float(sample_rate), channels=int(arr.shape[0]),
        sample_rate=int(sample_rate), superseded=superseded,
        warnings=warnings)


@dataclass
class SceneEdit:
    """What moving a scene boundary did, in the terms the panel reports."""
    scenes: int                             # how many there are now
    moved_rows: int                         # rows in shots.csv that followed
    note: str = ""
    warnings: list[str] = field(default_factory=list)


def _renumber_rows(project: Path, remap: dict[int, int | None],
                   merge_into: dict[int, int] | None = None) -> tuple[int, list[str]]:
    """Carry `shots.csv` across a change in what the scenes are.

    This is the half of a merge that is easy to forget and expensive to skip.
    A scene boundary moving shifts every scene after it, and a row addressing
    scene 20 by number now names a different line than the one it was written
    for — the exact failure that made `legends_of_surrender`'s table point at
    the wrong pictures when its script was rewritten underneath it, silently,
    for a week.

    `remap` is old 1-based index -> new index, or None for a scene that has
    stopped existing. `merge_into` says which surviving row absorbs a
    disappearing one, cell by cell: the survivor wins, and the absorbed row
    fills only what the survivor left blank. That is what makes "hold this
    picture, then push in" survive being made into one scene — the first row
    has the picture, the second has the focus, and the merged scene wants both.
    """

    path = project / "shots.csv"
    table = read_table(path)
    if not table.rows:
        return 0, []

    shot_col = next((n for n in table.fieldnames
                     if (n or "").strip().lower() == "shot"), "shot")
    by_index: dict[int, dict[str, str]] = {}
    warnings: list[str] = []
    keep: list[dict[str, str]] = []
    for raw in table.rows:
        key = row_key(raw)
        if not key or key.startswith("#"):
            keep.append(raw)
            continue
        index, cue = parse_shot_key(key)
        if index is None:
            keep.append(raw)
            if cue is not None:
                warnings.append(
                    f"shots.csv: the row {key!r} is addressed by its cue, which "
                    f"a scene boundary cannot renumber — check it by hand")
            continue
        by_index[index] = raw

    for old, raw in sorted(by_index.items()):
        if remap.get(old) is None:
            continue                        # absorbed below, or gone
        raw[shot_col] = _spell_key(row_key(raw), remap[old])

    for gone, survivor in (merge_into or {}).items():
        loser, winner = by_index.get(gone), by_index.get(survivor)
        if loser is None:
            continue
        if winner is None:                  # nothing to merge into: promote it
            loser[shot_col] = _spell_key(row_key(loser), remap.get(survivor) or survivor)
            by_index[survivor] = loser
            continue
        for k, v in loser.items():
            if (k or "").strip().lower() == "shot":
                continue
            if not (winner.get(k) or "").strip() and (v or "").strip():
                winner[k] = v

    moved = [raw for old, raw in sorted(by_index.items())
             if remap.get(old) is not None]
    table.rows = keep + moved
    write_table(path, table)
    return len(moved), warnings


def _spell_key(old: str, index: int) -> str:
    """The new number, written the way the row already wrote the old one."""
    old = old.strip()
    if old[:1].upper() == "S":
        return f"S{index:02d}"
    return str(index)


def merge_scene(project: Path, index: int) -> SceneEdit:
    """Fold scene `index` into the one before it. 1-based.

    A scene is a unit of what is seen, so two lines held on one picture with one
    continuous move are one scene — not two that happen to agree. Doing it here,
    in the script, is what makes that true for the renderer as well: two shots
    on one image get two separate motion schedules and `default_motion` cycles
    the preset by shot number, so they do not merely restart, they travel in
    different directions.

    Alignment is keyed on `script.md`'s mtime and will run again. That is
    correct and it is the price: the words did not change, but which words
    belong to which shot did.
    """
    from .project import read_script_file

    sf = read_script_file(project / "script.md")
    if not 2 <= index <= len(sf.scenes):
        raise ProjectError(
            f"scene {index} cannot be merged into the one before it; this "
            f"script has scenes 1..{len(sf.scenes)} and the first has no "
            f"predecessor")
    sf.scenes[index - 2] = sf.scenes[index - 2] + sf.scenes[index - 1]
    del sf.scenes[index - 1]
    (project / "script.md").write_text(sf.render(), encoding="utf-8")

    remap = {i: (i if i < index else None if i == index else i - 1)
             for i in range(1, len(sf.scenes) + 2)}
    moved, warns = _renumber_rows(project, remap, merge_into={index: index - 1})
    return SceneEdit(
        scenes=len(sf.scenes), moved_rows=moved,
        note=f"scenes {index - 1} and {index} are now scene {index - 1}; "
             f"{len(sf.scenes)} scenes. Run Align again — the words are the "
             f"same but which shot they belong to is not",
        warnings=warns)


def split_scene(project: Path, index: int, at_sentence: int) -> SceneEdit:
    """Cut scene `index` in two before sentence `at_sentence` (1-based).

    The new scene inherits the same row, and therefore the same picture — which
    is the point. Splitting is how "hold, then push in" gets made: one picture,
    two scenes, a focus on the second.
    """
    from .project import read_script_file, sentences_of

    sf = read_script_file(project / "script.md")
    if not 1 <= index <= len(sf.scenes):
        raise ProjectError(f"no scene {index}; this script has "
                           f"1..{len(sf.scenes)}")
    parts = sentences_of(sf.scenes[index - 1])
    if not 1 <= at_sentence < len(parts):
        raise ProjectError(
            f"scene {index} has {len(parts)} sentence(s), so there is no "
            f"boundary {at_sentence} to cut at. A scene of one sentence cannot "
            f"be split without rewriting it")
    sf.scenes[index - 1] = [" ".join(parts[:at_sentence])]
    sf.scenes.insert(index, [" ".join(parts[at_sentence:])])
    (project / "script.md").write_text(sf.render(), encoding="utf-8")

    remap = {i: (i if i <= index else i + 1) for i in range(1, len(sf.scenes))}
    moved, warns = _renumber_rows(project, remap)
    # The new scene starts out as a copy of the one it came from, so the picture
    # carries over and only the framing has to be decided.
    _copy_row(project, index, index + 1)
    return SceneEdit(
        scenes=len(sf.scenes), moved_rows=moved,
        note=f"scene {index} is now {index} and {index + 1}, both on the same "
             f"picture; {len(sf.scenes)} scenes. Run Align again",
        warnings=warns)


def _copy_row(project: Path, src: int, dst: int) -> None:
    """Give a newly split scene the row its parent had."""

    path = project / "shots.csv"
    table = read_table(path)
    shot_col = next((n for n in table.fieldnames
                     if (n or "").strip().lower() == "shot"), "shot")
    for i, raw in enumerate(table.rows):
        key = row_key(raw)
        if key.startswith("#"):
            continue
        if parse_shot_key(key)[0] == src:
            clone = dict(raw)
            clone[shot_col] = _spell_key(key, dst)
            # Beside its parent, not at the end: nothing reads the file in
            # order, but a person does, and a row 4 at the bottom of a
            # thirty-five-row table reads as damage.
            table.rows.insert(i + 1, clone)
            write_table(path, table)
            return


def _decisions_in_comments(table) -> int:
    """How many commented rows carry an edit decision rather than a note.

    `words` and `notes` are somebody writing to themselves; every other column
    changes what reaches the screen. A file full of the first kind needs
    tidying; one row of the second kind is a decision that quietly did not
    happen, and the warning should not call them the same thing.
    """
    from .shotlist import row_key

    keep = {"words", "notes"}
    n = 0
    for raw in table.rows:
        if not row_key(raw).startswith("#"):
            continue
        for k, v in raw.items():
            name = (k or "").strip().lower()
            if name in ("shot", *keep) or not (v or "").strip():
                continue
            n += 1
            break
    return n


def read_project(project: Path) -> ProjectRead:
    """Read the script, the media and the shot list. No model, no ffmpeg.

    Raises `ProjectError` for the three things that make a project unusable
    rather than merely incomplete: no recording, no script, no images. Anything
    else — a missing file a shot names, a cue that matches no block — is a
    warning, because a shot list is written while the script is still moving.
    """
    narration = find_narration(project)
    if narration is None:
        raise ProjectError(f"no narration.* in {project / 'sources'} or {project}")

    script_shots = parse_script_shots(project / "script.md")
    if not script_shots:
        raise ProjectError(f"{project / 'script.md'} has no shots")
    blocks = [s.text for s in script_shots]

    images = list_images(project / MEDIA_DIRS[0])
    if not images:
        raise ProjectError(f"{project / MEDIA_DIRS[0]} is empty")

    media, warnings = resolve_shot_images(script_shots, images)

    # Said first, and said in full, because it is the one defect in a script
    # that makes every number downstream wrong while looking like nothing.
    escaped = escaped_headings(project / "script.md")
    if escaped:
        warnings.insert(0, (
            f"script.md has {escaped} scene heading(s) written as '\\## S01' "
            f"rather than '## S01'. A backslash there means 'not a heading', so "
            f"none of them is one: the file is being read as "
            f"{len(script_shots)} blank-line blocks instead of {escaped} scenes, "
            f"and the heading lines themselves will be spoken and subtitled. "
            f"Some editors add that backslash when text is pasted — delete it "
            f"and run this again"))

    # shots.csv wins over the script's own [[refs]] and over cycling: it is the
    # edit decision, made after both. The table is read once here rather than
    # inside a one-line reader, because the rows it *drops* are worth a word too.
    table = read_table(project / "shots.csv")
    picks, edit_warnings = apply_shot_list(
        script_shots, edits_from_table(table), project)
    warnings = list(warnings) + edit_warnings
    # One line, not one per row: a file written this way is written this way
    # throughout, and thirty-four copies of the same sentence is not a louder
    # warning, it is a wall nobody reads to the end of.
    commented = mislabelled_comments(table)
    if commented:
        first = commented[0]
        # Whether anything is actually *lost* is worth checking rather than
        # asserting. Thirty-four rows carrying only the scene's words are old
        # notes and cost nothing; one carrying a picture is a decision that
        # silently did not happen, and those are different sentences.
        decided = _decisions_in_comments(table)
        warnings.append(
            f"shots.csv: {len(commented)} row(s) are commented out and being "
            f"ignored — their shot column starts with '#', which this format "
            f"reads as a comment. "
            + (f"{decided} of them decide something (media, motion, focus…), "
               f"and none of it is happening. " if decided
               else "None of them decides anything, so nothing is lost — they "
                    "are notes. ")
            + f"Write {first!r} as {first.lstrip('#').strip()!r} to bring one "
              f"back")
    for i, p in enumerate(picks):
        if p.media is not None:
            media[i] = p.media

    notes: list[str] = []
    footage = [f"shot {i}" for i, p in enumerate(picks, 1) if p.is_video]
    if footage:
        notes.append(f"footage: {len(footage)} shot(s) use a video fragment "
                     f"({', '.join(footage)})")
    from_csv = sum(1 for p in picks if p.media is not None)
    if from_csv:
        notes.append(f"shots.csv: {from_csv} shot(s) placed by the shot list")
    named = sum(1 for s in script_shots if s.assets)
    notes.append(f"{len(script_shots)} shots — {named} with a storyboard image, "
                 f"{len(script_shots) - named} cycled from {MEDIA_DIRS[0]}/")
    silent = [s.label or f"shot {i}"
              for i, s in enumerate(script_shots, 1) if s.silent]
    if silent:
        # Silent shots get their duration from the pause between neighbours; if
        # the narrator did not pause, they collapse to a single frame.
        notes.append(f"silent shots (no narration): {', '.join(silent)}")

    return ProjectRead(project=project, narration=narration,
                       script_shots=script_shots, blocks=blocks, images=images,
                       picks=picks, media=media, warnings=warnings, notes=notes)


def align_project(project: Path, read: ProjectRead, *, lang: str,
                  model: str = "small", use_aligner: bool = True,
                  aligner: Aligner | None = None,
                  progress: Progress = _noop) -> Alignment:
    """Align the recording to the script. Timings only — nothing is transcribed.

    `use_aligner=False` spreads the shots proportionally instead: no model, no
    download, wrong timings, and every span flagged `estimated`. It is the dry
    run, and it is what makes the rest of the pipeline testable in a second.

    `aligner` exists so an engine swap touches one argument rather than the node
    layer (SPEC §5.1). Left alone it is `StableTsAligner`.
    """
    normed: list[str] = []
    flags: list[bool] = []
    for b in read.blocks:
        n, had = normalize_block(b, lang)
        normed.append(n)
        flags.append(had)

    engine = aligner or StableTsAligner(model)
    duration = engine.audio_duration(read.narration)

    if not use_aligner:
        spans = proportional_spans(read.blocks, duration)
    else:
        progress("align", 0, 0,
                 f"aligning {len(read.blocks)} blocks against "
                 f"{read.narration.name} ({duration:.1f}s, model={model}, "
                 f"lang={lang})…")
        # normed is what the model listens for; blocks is what reaches the
        # screen. Both are needed — see StableTsAligner.align.
        spans = engine.align(read.narration, normed, lang, read.blocks)

    estimated = any(s.estimated for s in spans)
    warnings: list[str] = []
    if use_aligner and estimated:
        # The aligner logs and degrades rather than failing, so without this the
        # only evidence is a confidence of 0.00 in the report.
        warnings.append("alignment fell back to proportional timing; the "
                        "timings below are estimates, not measurements")
    return Alignment(spans=spans, duration=duration, norm_blocks=normed,
                     digit_flags=flags, lang=lang, estimated=estimated,
                     warnings=warnings)


def compose_project(project: Path, read: ProjectRead, alignment: Alignment, *,
                    fps: int = 30, lead_ms: int = 100, max_chunk: int = 30,
                    out: Path | None = None, write: bool = True,
                    progress: Progress = _noop) -> Composition:
    """Turn timings plus edit decisions into the shot table.

    Pure arithmetic and one pass over the media for its pixel dimensions, so it
    is cheap enough to re-run on every edit. That is the point of it being its
    own step.
    """
    spans = apply_shot_lead(alignment.spans, lead_ms)
    n_frames = frames_for([(s.t_start, s.t_end) for s in spans], fps)

    warnings: list[str] = []
    motions: list[Motion] = []
    schedules = []
    for i, (img, nf) in enumerate(zip(read.media, n_frames)):
        progress("compose", i + 1, len(read.media))
        if is_video(img):
            # Footage is measured the same way a still is — the schedule only
            # needs the frame's dimensions, and every motion preset then works
            # on a fragment without knowing it is one.
            src_w, src_h = probe(img).size
        else:
            with Image.open(img) as im:
                src_w, src_h = im.size
        mot = _motion_for(i, read.picks[i])
        if read.picks[i].focus is not None:
            if mot.preset in FOCUSABLE:
                mot.focus = read.picks[i].focus
            else:
                # Silently dropping it would leave a shot list that reads as if
                # the framing had been decided (SPEC §6.2.12: legible failure).
                warnings.append(
                    f"shot {i + 1} sets a focus but its motion is "
                    f"{mot.preset!r}, which traverses rather than arrives; "
                    f"focus ignored. Use one of {', '.join(FOCUSABLE)}.")
        motions.append(mot)
        sched = compute(src_w, src_h, nf, mot)
        # A stop a crop cannot reach is the one way a path quietly does
        # something other than what it says. Named here, per stop, with the
        # number it will actually land on, because "it looks slightly wrong" is
        # not something anybody can act on three scenes later.
        for stop, ax, ay, gx, gy in sched.unreachable:
            warnings.append(
                f"shot {i + 1} path stop {stop} asks for "
                f"({ax:.3f}, {ay:.3f}), which is too near the edge of the "
                f"picture for a window this wide; it lands on "
                f"({gx:.3f}, {gy:.3f}). Widen the stop, move it inward, or "
                f"build the move as a composite, which can show the surface "
                f"behind the paper")
        schedules.append(sched)

    # `write_outputs` is the only thing that knows the schema, so the table is
    # always built through it — even when the caller does not want it on disk,
    # in which case it is built into a temp directory and read back. Two
    # writers is how the node pack and the CLI came to disagree in the first
    # place, and a table the graph holds but never saves is a normal state.
    tmp = None if write else TemporaryDirectory(prefix="memoacts_")
    out_dir = Path(tmp.name) if tmp else (out or project / "generated")
    # Project-relative, like image_path. A bare filename stopped resolving the
    # moment the recording moved into sources/.
    rel = read.narration.relative_to(project).as_posix()
    path = write_outputs(
        out_dir, lang=alignment.lang, fps=fps, narration=rel,
        duration=alignment.duration, lead_ms=lead_ms, blocks=read.blocks,
        norm_blocks=alignment.norm_blocks, digit_flags=alignment.digit_flags,
        spans=spans, images=read.media, motions=motions, schedules=schedules,
        n_frames=n_frames, max_chunk=max_chunk,
        cues=[sh.cue for sh in read.script_shots],
        labels=[p.label for p in read.picks],
        credits=[p.credit for p in read.picks],
        media_ins=[p.media_in for p in read.picks],
        speeds=[p.speed for p in read.picks],
        effects=[p.effects for p in read.picks])
    doc = json.loads(path.read_text(encoding="utf-8"))
    report = (path.parent / "report.txt").read_text(encoding="utf-8")
    if tmp is not None:
        tmp.cleanup()
        return Composition(doc=doc, report=report, path=None, warnings=warnings)
    return Composition(doc=doc, report=report, path=path, warnings=warnings)


def read_sound_design(project: Path, doc: dict[str, Any], *,
                      text: str | None = None,
                      write: bool = False) -> SoundDesign:
    """The sound design, from a typed-in table or from `sfx.csv`.

    `text` is what somebody has in front of them — the Sound Design node's box —
    and it wins over the file, which is the same rule the shot table follows.
    Left as None the file is authoritative; if there is no file either, the
    starter table stands in, and `write=True` puts it on disk so the next run
    has something to read.

    Nothing here is slow and nothing here decodes audio: this is the step that
    has to be able to run on every keystroke.
    """
    path = project / "sfx.csv"
    is_template = False
    if text is not None and text.strip():
        table = sfxlib.parse_text(text)
        # The box wins on every column a person writes, and loses on the two
        # the generator writes back into the file. Without this the seed of a
        # take somebody liked survives exactly until the next run.
        table = sfxlib.carry_generated(table, sfxlib.read_table(path))
    else:
        table = sfxlib.read_table(path)
        if not table.rows:
            table = sfxlib.template(doc)
            is_template = True
    if write:
        sfxlib.write_table(path, table)

    cues, warnings = sfxlib.cues_from_table(table)
    placed, more = sfxlib.resolve(project, doc, cues)
    return SoundDesign(csv=path, table=table, cues=cues, placed=placed,
                       is_template=is_template, warnings=warnings + more)


def build_sfx_bed(project: Path, doc: dict[str, Any],
                  placed: list[sfxlib.Placed], *,
                  master_db: float = 0.0, duck: bool = True,
                  out: Path | None = None,
                  progress: Progress = _noop) -> tuple[Path, list[str]]:
    """Mix the sound design into one track the length of the reel.

    Takes the placed cues rather than the whole `SoundDesign`, because that is
    all it ever read — and asking for the wider type made the SFX Bed node
    build a `SoundDesign` with an empty `CueTable` in it purely to have
    something to pass.

    The narration is opened read-only, to find where the voice is; the only
    signal written is the sound effects layer (SPEC §5.6). The bed lands in
    `generated/`, beside `shots.json`, because it is derived from files the
    project already holds and can be thrown away and remade.
    """
    if not placed:
        raise ProjectError("no sound cues to mix — sfx.csv has no live rows")
    total = float(doc.get("duration_s") or 0.0)
    if total <= 0:
        raise ProjectError("the shot table carries no duration_s to mix against")

    narration = None
    if duck:
        narration = project / doc.get("narration", "")
        if not narration.exists():
            narration = find_narration(project)

    have = sum(1 for p in placed if p.path is not None)
    progress("sfx", 0, 0,
             f"mixing {have} of {len(placed)} sound(s) over "
             f"{total:.2f}s" + (", ducked under the narration" if narration
                                else ", no ducking"))
    bed, notes = sfxlib.render_bed(placed, total, narration=narration,
                                   master_db=master_db)
    path = sfxlib.write_wav(out or project / "generated" / "sfx_bed.wav", bed)
    for n in notes:
        progress("sfx", 0, 0, f"  {n}")
    return path, notes


def _motion_for(index: int, pick: ResolvedShot) -> Motion:
    """The shot's motion: the rotating default, then whatever the table says."""
    mot = default_motion(index)
    if pick.path:
        # A path says everything a preset would have decided — where the window
        # starts, where it goes and how wide it is at each stop — so nothing
        # else on the row can still be true at the same time.
        return Motion(preset="static", rate=mot.rate, anchor=mot.anchor,
                      path=pick.path)
    if pick.motion:
        return Motion(preset=pick.motion,
                      rate=pick.rate if pick.rate is not None else mot.rate,
                      anchor=pick.anchor or mot.anchor)
    if pick.rate is not None or pick.anchor:
        return Motion(preset=mot.preset,
                      rate=pick.rate if pick.rate is not None else mot.rate,
                      anchor=pick.anchor or mot.anchor)
    return mot


def shots_from_doc(project: Path, doc: dict[str, Any], *,
                   default_effects: str = "none",
                   stacks: dict[int, EffectStack] | None = None,
                   shot_ids: list[int] | None = None
                   ) -> tuple[list[ShotRender], list[str]]:
    """Build the renderable shots from a `shots.json` document.

    Three ways to give a shot a look, in decreasing order of specificity: a
    stack built in the graph (`stacks`, keyed by shot id), the preset the shot
    names for itself in `shots.csv` (schema 1.5), and `default_effects` for
    everything else. An unknown preset name warns and leaves the shot plain
    rather than stopping a render that can still show every other shot.
    """
    out_w = doc.get("width", 1080)
    shots: list[ShotRender] = []
    warnings: list[str] = []
    for s in doc["shots"]:
        if shot_ids is not None and s["id"] not in shot_ids:
            continue
        img = resolve_media(project, s)
        if not img.exists():
            raise ProjectError(f"missing media for shot {s['id']}: {img}")
        if is_video(img):
            src_w, src_h = probe(img).size
        else:
            with Image.open(img) as im:
                src_w, src_h = im.size
        sched = compute(src_w, src_h, s["n_frames"], Motion(**s["motion"]),
                        out_w=out_w)
        fx: EffectStack | None = None
        name = s.get("effects") or default_effects
        if stacks and s["id"] in stacks:
            # A fresh copy per shot, for the same reason `preset` is called per
            # shot: the pipeline holds a texture clip's decoder position.
            fx = deepcopy(stacks[s["id"]])
        elif name and name != "none":
            try:
                fx = preset(name)
            except ValueError:
                warnings.append(
                    f"shot {s['id']} asks for effect preset {name!r}, which is "
                    f"not one of {', '.join(sorted(PRESETS))}; rendered plain")
        shots.append(ShotRender(media=img, schedule=sched, effects=fx,
                                media_in=s.get("media_in") or 0.0,
                                speed=s.get("speed") or 1.0))
    return shots, warnings


def render_project(project: Path, doc: dict[str, Any], *,
                   out: Path | None = None,
                   opts: RenderOptions | None = None,
                   stacks: dict[int, EffectStack] | None = None,
                   shot_ids: list[int] | None = None,
                   progress: Progress = _noop) -> RenderResult:
    """Render the shot table to a finished vertical MP4.

    `shot_ids` renders a subset — the preview path. A subset carries neither the
    narration nor the subtitle track, because both are timed from the start of
    the reel and would be wrong against a fragment of it; a preview is for
    judging the framing and the move.
    """
    opts = opts or RenderOptions()
    preview = shot_ids is not None
    fps = doc["fps"]
    out_w, out_h = doc.get("width", 1080), doc.get("height", 1920)

    shots, warnings = shots_from_doc(project, doc,
                                     default_effects=opts.effects,
                                     stacks=stacks, shot_ids=shot_ids)
    if not shots:
        raise ProjectError("no shots to render")

    out_path = out or project / "out" / "reel.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    narration = None
    if not preview:
        narration = project / doc.get("narration", "")
        if not narration.exists():
            narration = find_narration(project)
            if narration is None:
                raise ProjectError(f"no narration.* in {project}")

    sfx_bed = None if preview else opts.sfx
    if sfx_bed is not None:
        if not sfx_bed.exists():
            raise ProjectError(f"no sound design at {sfx_bed}; build the bed "
                               f"before rendering, or clear the option")
        progress("render", 0, 0, f"sound design: {sfx_bed.name} mixed under "
                                 f"the narration")

    ass = srt = None
    cues: list[subs.Cue] = []
    wrapped: list[str] = []
    if opts.subs and not preview:
        style = subs.SubStyle(size=opts.sub_size)
        if opts.plate is not None:
            style = replace(style, plate_opacity=opts.plate)
        cues = subs.cues_from_shots(doc["shots"], style, out_w,
                                    segment=opts.segment,
                                    min_duration=opts.min_duration)
        labels = ([] if not opts.labels
                  else subs.labels_from_shots(doc["shots"], hold=opts.label_hold))
        credit_cues = [] if not opts.labels else subs.credits_from_shots(doc["shots"])
        ass, srt = subs.write_tracks(out_path.parent, cues, stem=out_path.stem,
                                     style=style, labels=labels,
                                     credits=credit_cues)
        if labels:
            progress("subtitles", 0, 0,
                     f"labels: {len(labels)} corner tags, {opts.label_hold:.1f}s each")
        if credit_cues:
            progress("subtitles", 0, 0,
                     f"credits: {len(credit_cues)} source lines, held for the shot")
        # A wrapped caption stacks two plates and puts a dark bar through the
        # text, so this is a defect report, not a style note.
        for c in subs.check_wrap(cues, style, out_w):
            wrapped.append(c.text)
            progress("subtitles", 0, 0, f"  WRAPS (plates will overlap): {c.text!r}")
        progress("subtitles", 0, 0,
                 f"subtitles: {len(cues)} cues from {len(doc['shots'])} blocks "
                 f"-> {ass.name}, {srt.name}")

    total = sum(len(s.schedule.ws) for s in shots)
    progress("render", 0, total,
             f"rendering {len(shots)} shots, {total} frames "
             f"({total / fps:.3f} s at {fps} fps) -> {out_path.name}")

    def on_frame(done: int, count: int, frame: Image.Image) -> None:
        progress("render", done, count, "", frame)

    # The resolution guard warns through `warnings.warn`, which has no caller to
    # print it once the CLI stops being the only door. Collect it instead.
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        render_reel(shots, out_path, fps, narration=narration, ass=ass,
                    sfx=sfx_bed, crf=opts.crf, out_w=out_w, out_h=out_h,
                    on_upscale=opts.on_upscale, on_frame=on_frame)
    warnings += [str(w.message) for w in caught]

    # The reel is frame-quantised, so it is normally a few ms longer than the
    # narration. A large gap means the shot table and the audio disagree.
    duration_s = total / fps
    drift = 0.0 if preview else duration_s - doc.get("duration_s", duration_s)
    return RenderResult(path=out_path, frames=total, duration_s=duration_s,
                        drift_s=drift, ass=ass, srt=srt, cues=len(cues),
                        wrapped=wrapped, warnings=warnings)
