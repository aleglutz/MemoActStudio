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
from dataclasses import dataclass, field, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image

from . import subs
from .align import Aligner, Span, StableTsAligner, proportional_spans
from .effects import EffectStack, PRESETS, preset
from .normalize import normalize_block
from .project import (MEDIA_DIRS, ScriptShot, apply_shot_lead, find_narration,
                      list_images, parse_script_shots, resolve_media,
                      resolve_shot_images, write_outputs)
from .render import ShotRender, render_reel
from .schedule import FOCUSABLE, Motion, compute, default_motion, frames_for
from .shotlist import ResolvedShot, apply_shot_list, read_shot_list
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
class RenderOptions:
    """Everything `render_reel.py`'s flags decide, with the same defaults."""
    subs: bool = True
    sub_size: int = 56
    segment: bool = True
    plate: float | None = None              # None keeps subs.SubStyle's own
    labels: bool = True
    label_hold: float = 3.0
    crf: int = 19
    on_upscale: str = "warn"
    effects: str = "none"                   # fallback for shots setting none


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

    # shots.csv wins over the script's own [[refs]] and over cycling: it is the
    # edit decision, made after both.
    picks, edit_warnings = apply_shot_list(script_shots, read_shot_list(
        project / "shots.csv"), project)
    warnings = list(warnings) + edit_warnings
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
        schedules.append(compute(src_w, src_h, nf, mot))

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


def _motion_for(index: int, pick: ResolvedShot) -> Motion:
    """The shot's motion: the rotating default, then whatever the table says."""
    mot = default_motion(index)
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
                   shot_ids: list[int] | None = None
                   ) -> tuple[list[ShotRender], list[str]]:
    """Build the renderable shots from a `shots.json` document.

    Per-shot `effects` (schema 1.5) wins over `default_effects`; an unknown
    preset name warns and leaves the shot plain rather than stopping a render
    that can still show every other shot.
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
        name = s.get("effects") or default_effects
        fx: EffectStack | None = None
        if name and name != "none":
            try:
                # A fresh stack per shot: the pipeline holds decoder state
                # (texture clip position), so sharing one across shots would
                # interleave them.
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
                                     shot_ids=shot_ids)
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

    ass = srt = None
    cues: list[subs.Cue] = []
    wrapped: list[str] = []
    if opts.subs and not preview:
        style = subs.SubStyle(size=opts.sub_size)
        if opts.plate is not None:
            style = replace(style, plate_opacity=opts.plate)
        cues = subs.cues_from_shots(doc["shots"], style, out_w,
                                    segment=opts.segment)
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
                    crf=opts.crf, out_w=out_w, out_h=out_h,
                    on_upscale=opts.on_upscale, on_frame=on_frame)
    warnings += [str(w.message) for w in caught]

    # The reel is frame-quantised, so it is normally a few ms longer than the
    # narration. A large gap means the shot table and the audio disagree.
    duration_s = total / fps
    drift = 0.0 if preview else duration_s - doc.get("duration_s", duration_s)
    return RenderResult(path=out_path, frames=total, duration_s=duration_s,
                        drift_s=drift, ass=ass, srt=srt, cues=len(cues),
                        wrapped=wrapped, warnings=warnings)
