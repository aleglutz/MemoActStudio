"""Render nodes — "the reel is made" (SPEC §5.3, §5.7).

One ffmpeg pass for the whole reel: per-frame crops streamed from PIL, subtitles
burnt once via libass, narration muxed untouched. Memory is constant in reel
length, so there is no chunking here and no concat step — both existed in P1
only to work around the tensor-batch limit (`GAPS.md` #2).

Two nodes, because a workshop machine is shared by eight people. The reel is
minutes; one shot is seconds, and one shot is what you actually look at when
deciding whether a move works. Both report progress frame by frame and show the
frames as they are made, which is the difference between a long step and a
button that appears to have hung.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.effects import COST, PRESETS
from .memoacts_core.pipeline import RenderOptions, render_project
from .nodes_audio import audio_to_numpy
from .nodes_types import Effects, Shots, Subs

#: How often a frame is pushed to the node's preview. Every frame would be a
#: websocket message per 30th of a second of reel; twelve is often enough to
#: read as motion and cheap enough to ignore.
PREVIEW_EVERY = 12

#: Longest edge of a preview frame. The reel is 1080x1920; a node on the canvas
#: is a few hundred pixels wide, and the resize happens server-side anyway.
PREVIEW_PX = 512


def _cost_list() -> str:
    """The presets by what they cost, cheapest first — see `effects.COST`.

    Walks `PRESETS`, not `COST`, so a look added without a measurement shows
    up as unmeasured instead of vanishing from the tooltip: this line is the
    one place SPEC asks the cost decision to be visible on a shared machine.
    """
    named = sorted(((name, COST.get(name)) for name in PRESETS if name != "none"),
                   key=lambda kv: (kv[1] is None, kv[1] or 0.0))
    return ", ".join(f"{name} {mult:.1f}x" if mult is not None
                     else f"{name} (unmeasured)" for name, mult in named)


def _output_path(filename_prefix: str) -> tuple[Path, str]:
    """A numbered file under ComfyUI's output directory, never overwriting.

    A student re-rendering after an edit should be able to compare against the
    previous take rather than lose it.
    """
    import folder_paths
    prefix = Path(filename_prefix)
    subfolder = str(prefix.parent) if str(prefix.parent) != "." else ""
    target = Path(folder_paths.get_output_directory()) / subfolder
    target.mkdir(parents=True, exist_ok=True)
    n = 1
    while (target / f"{prefix.name}_{n:05d}.mp4").exists():
        n += 1
    return target / f"{prefix.name}_{n:05d}.mp4", subfolder


def _reporter():
    """A `pipeline.progress` that drives ComfyUI's progress bar and preview.

    Two things come free with reporting progress this way, and both matter more
    than the bar itself: the hook throws if the user pressed Cancel, so a render
    can be stopped, and it carries a frame, so there is something to watch.
    """
    from comfy.utils import ProgressBar
    state: dict[str, ProgressBar | None] = {"bar": None}

    def progress(stage, done=0, total=0, message="", preview=None):
        if message:
            print(f"[MemoActs] {message}")
        if stage != "render" or not total:
            return
        if state["bar"] is None:
            state["bar"] = ProgressBar(total)
        image = None
        if preview is not None and (done % PREVIEW_EVERY == 0 or done == total):
            image = ("JPEG", preview, PREVIEW_PX)
        state["bar"].update_absolute(done, total, image)

    return progress


class MemoActsRenderReel(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsRenderReel",
            display_name="MemoActs — Render Reel",
            category="memoacts",
            description=(
                "Renders the shot table to a finished vertical MP4: the moves, "
                "the captions burnt in, the narration muxed through untouched. "
                "Minutes for a full reel — try one shot first with Preview Shot."
            ),
            is_output_node=True,
            inputs=[
                Shots.Input("shots"),
                Subs.Input("subtitles", optional=True),
                Effects.Input("effects", optional=True),
                io.Audio.Input(
                    "sfx", optional=True,
                    tooltip="The sound design layer, summed with the narration "
                            "at the mux. Usually SFX Bed; any AUDIO works, so a "
                            "track from a CC0 library loaded with Load Audio "
                            "goes straight in. The narration itself is never "
                            "touched.",
                ),
                io.String.Input("filename_prefix", default="memoacts/reel"),
                io.Combo.Input(
                    "effect_preset", options=["none"] + sorted(set(PRESETS) - {"none"}),
                    default="none",
                    tooltip="The look for every shot that names none of its own "
                            "in the effects column of shots.csv. Measured cost, "
                            "as a multiple of a clean render: "
                            + _cost_list() + ".",
                ),
                io.Int.Input(
                    "crf", default=19, min=0, max=51,
                    tooltip="H.264 quality: lower is better and larger. "
                            "19 is visually near-lossless.",
                ),
                io.Combo.Input(
                    "on_upscale", options=["warn", "error", "allow"],
                    default="warn",
                    tooltip="What to do when a source cannot fill the output. "
                            "The project forbids upscaling silently, so there "
                            "is deliberately no quiet default.",
                ),
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, shots, filename_prefix, effect_preset, crf, on_upscale,
                subtitles=None, effects=None, sfx=None):
        out_path, subfolder = _output_path(filename_prefix)
        opts = _options(subtitles, effect_preset, crf, on_upscale)
        opts.sfx = _sfx_file(Path(shots["project_dir"]), sfx)
        res = render_project(Path(shots["project_dir"]), shots["doc"],
                             out=out_path, opts=opts,
                             stacks=_stacks(shots, effects),
                             progress=_reporter())
        for w in res.warnings:
            print(f"[MemoActs] {w}")
        print(f"[MemoActs] wrote {res.path.name}; video {res.duration_s:.3f}s "
              f"vs narration {shots['doc'].get('duration_s')}s "
              f"(drift {res.drift_s * 1000:+.0f} ms)")

        return io.NodeOutput(ui=ui.PreviewVideo([ui.SavedResult(
            filename=res.path.name,
            subfolder=subfolder,
            type=io.FolderType.output,
        )]))


class MemoActsPreviewShot(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPreviewShot",
            display_name="MemoActs — Preview Shot",
            category="memoacts",
            description=(
                "Renders one shot alone — seconds instead of minutes, which is "
                "how you judge a framing or a move without re-rendering the "
                "reel. No narration and no captions: both are timed from the "
                "head of the reel and would be wrong against a fragment of it."
            ),
            is_output_node=True,
            inputs=[
                Shots.Input("shots"),
                Effects.Input("effects", optional=True),
                io.Int.Input("shot_id", default=1, min=1, max=999,
                             tooltip="1-based shot number, as in the report."),
                io.Combo.Input(
                    "effect_preset", options=["none"] + sorted(set(PRESETS) - {"none"}),
                    default="none",
                    tooltip="Applied unless the shot names a look of its own. "
                            "Measured cost: " + _cost_list() + ".",
                ),
                io.Combo.Input(
                    "on_upscale", options=["warn", "error", "allow"],
                    default="warn",
                ),
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, shots, shot_id, effect_preset, on_upscale, effects=None):
        entries = shots["doc"]["shots"]
        if not any(s["id"] == shot_id for s in entries):
            raise ValueError(
                f"no shot {shot_id}; this table has 1..{len(entries)}")
        out_path, subfolder = _output_path(f"memoacts/shot_{shot_id:02d}")
        # crf 23: a preview is looked at once and thrown away, and the wait is
        # the whole point of the node.
        opts = _options(None, effect_preset, 23, on_upscale)
        res = render_project(Path(shots["project_dir"]), shots["doc"],
                             out=out_path, opts=opts,
                             stacks=_stacks(shots, effects),
                             shot_ids=[shot_id], progress=_reporter())
        for w in res.warnings:
            print(f"[MemoActs] {w}")
        print(f"[MemoActs] shot {shot_id}: {res.frames} frames, "
              f"{res.duration_s:.2f}s -> {res.path.name}")

        return io.NodeOutput(ui=ui.PreviewVideo([ui.SavedResult(
            filename=res.path.name,
            subfolder=subfolder,
            type=io.FolderType.output,
        )]))


def _options(subtitles, effect_preset: str, crf: int,
             on_upscale: str) -> RenderOptions:
    """Caption settings from the Subtitles node, or none at all if unwired."""
    opts = RenderOptions(subs=subtitles is not None, crf=crf,
                         on_upscale=on_upscale, effects=effect_preset)
    if subtitles:
        for field in ("sub_size", "plate", "segment", "min_duration",
                      "labels", "label_hold"):
            if field in subtitles:
                setattr(opts, field, subtitles[field])
    return opts


def _sfx_file(project: Path, audio) -> Path | None:
    """The sound design as a file, because ffmpeg reads files and not tensors.

    Written into `generated/`, which is the folder that exists to be deletable:
    this is a re-derivable copy of whatever was wired in, kept only long enough
    for the mux and left behind on purpose, so a mix that sounds wrong can be
    listened to on its own afterwards.
    """
    if audio is None:
        return None
    from .memoacts_core.sfx import write_wav
    return write_wav(project / "generated" / "sfx_render.wav",
                     audio_to_numpy(audio))


def _stacks(shots, effects):
    """Effect stacks built in the graph, keyed by shot id.

    `MemoActsApplyEffects` attaches them to the table; an `EFFECTS` wired
    straight in applies to every shot, which is the short way to try a look.
    """
    stacks = dict(shots.get("effects") or {})
    if effects is not None:
        for s in shots["doc"]["shots"]:
            stacks.setdefault(s["id"], effects)
    return stacks or None
