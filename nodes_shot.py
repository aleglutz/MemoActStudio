"""The shot table — "I decide what is seen" (SPEC §5.2, the interactive heart).

`MemoActsShotTable` turns timings plus edit decisions into the table everything
downstream reads, and prints the shot report so the decisions can be checked
before anything is rendered: confidence per shot, drift against the cue written
in the script, and the resolution guard's verdict on the image chosen for it.

The decisions themselves live in `shots.csv`, and this node re-reads that file
every run, so an edit made anywhere is picked up without re-aligning.

**Where they are made is the Storyline panel**, in ComfyUI's sidebar, not here.
The editor used to be a table inside this node and stopped carrying its job at
34 scenes: a table has no time in it, so the rhythm of the reel was invisible,
and pictures were picked from a dropdown of filenames rather than by looking at
them. `web/memoacts_storyline.js` is the answer to both. This node keeps the
work it actually does — compiling the table, writing `shots.json`, and printing
the report by which the decisions are checked before anything is rendered.

Defaults must produce a decent reel with zero per-shot input, so the creator
edits **by exception**. `MemoActsSetMotion` and `MemoActsSetImage` are that
exception mechanism inside the graph: they override one shot and leave the rest.
"""
from __future__ import annotations

import copy
from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.pipeline import compose_project, read_project
from .memoacts_core.project import MEDIA_DIRS
from .memoacts_core.schedule import PRESETS
from .nodes_types import Alignment, Shots


class MemoActsShotTable(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsShotTable",
            display_name="MemoActs — Shot Table",
            category="memoacts",
            description=(
                "Combines the timings with the edit decisions in shots.csv — "
                "which image, which move, what it is about, what it is called — "
                "and emits the shot table. Cheap: it re-reads the folder every "
                "run, so an edit costs nothing and never re-runs alignment. "
                "Make the decisions in the Storyline panel, in the sidebar; run "
                "this to compile them and read the report."
            ),
            is_output_node=True,
            inputs=[
                Alignment.Input("alignment"),
                io.Int.Input("fps", default=30, min=1, max=120),
                io.Int.Input(
                    "shot_lead_ms", default=100, min=0, max=1000,
                    tooltip="Cuts lead the sentence onset by this much. An "
                            "image arriving slightly early reads as "
                            "intentional; arriving late reads as a mistake.",
                ),
                io.Boolean.Input(
                    "save", default=True,
                    tooltip="Write generated/shots.json and report.txt. Off "
                            "keeps the table in the graph only — the render "
                            "works either way.",
                ),
                io.Int.Input(
                    "max_chunk", default=30, min=1, max=600, optional=True,
                    tooltip="Frames per crop CSV, for the Comfy Cloud path "
                            "only (GAPS.md). Local rendering never chunks.",
                ),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def fingerprint_inputs(cls, alignment, fps, shot_lead_ms, save,
                           max_chunk=30):
        """Re-run when the edit decisions or the media change.

        The alignment upstream is cached on the script and the recording; this
        is the other half — `shots.csv` and the folders it points into. Without
        it a student edits a row, runs, and gets the previous table back.
        """
        folder = Path(alignment["project_dir"])
        stamps = []
        for p in [folder / "shots.csv"] + [folder / d for d in MEDIA_DIRS]:
            try:
                stamps.append(p.stat().st_mtime_ns)
            except OSError:
                stamps.append(0)
        return f"{folder}|{stamps}|{fps}|{shot_lead_ms}|{save}|{max_chunk}"

    @classmethod
    def execute(cls, alignment, fps, shot_lead_ms, save, max_chunk=30):
        folder = Path(alignment["project_dir"])
        read = read_project(folder)
        for w in read.warnings:
            print(f"[MemoActs] warning: {w}")

        comp = compose_project(folder, read, alignment["alignment"], fps=fps,
                               lead_ms=shot_lead_ms, max_chunk=max_chunk,
                               write=save)
        for w in comp.warnings:
            print(f"[MemoActs] warning: {w}")

        report = comp.report
        if read.warnings or comp.warnings:
            report += "\n" + "\n".join(
                f"warning: {w}" for w in read.warnings + comp.warnings)
        return io.NodeOutput({"doc": comp.doc, "project_dir": str(folder)},
                             ui=ui.PreviewText(report))


class MemoActsSetMotion(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSetMotion",
            display_name="MemoActs — Set Motion",
            category="memoacts",
            description=(
                "Overrides the motion preset for one shot, or for every shot. "
                "Chain several to edit by exception. The lasting place for this "
                "decision is the motion column of shots.csv; this is for trying "
                "one out."
            ),
            inputs=[
                Shots.Input("shots"),
                io.Int.Input(
                    "shot_id", default=0, min=0, max=999,
                    tooltip="1-based shot number, or 0 to apply to every shot.",
                ),
                io.Combo.Input("preset", options=list(PRESETS), default="zoom_in"),
                io.Float.Input(
                    "rate", default=0.06, min=0.0, max=0.5, step=0.01,
                    tooltip="Zoom fraction across the shot. ~0.04–0.08 reads as "
                            "a slow drift; higher gets noticeable.",
                ),
                io.Combo.Input("anchor", options=["center", "top"], default="center"),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def execute(cls, shots, shot_id, preset, rate, anchor):
        out = copy.deepcopy(shots)
        entries = out["doc"]["shots"]
        if shot_id and not any(s["id"] == shot_id for s in entries):
            raise ValueError(
                f"no shot {shot_id}; this table has 1..{len(entries)}")
        for s in entries:
            if shot_id in (0, s["id"]):
                # The focus survives a preset change: it says what the shot is
                # about, which changing the direction of travel does not revise.
                # Overwriting the dict wholesale would silently discard it.
                s["motion"] = {"preset": preset, "rate": rate, "anchor": anchor,
                               "focus": s.get("motion", {}).get("focus"),
                               # Same reason as the focus: a path says what the
                               # shot is about, and a change of direction does
                               # not revise that. Overwriting the dict wholesale
                               # would silently discard both.
                               "path": s.get("motion", {}).get("path")}
        return io.NodeOutput(out)


class MemoActsSetImage(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSetImage",
            display_name="MemoActs — Set Shot Image",
            category="memoacts",
            description="Assigns different media to one shot — a still, a map "
                        "plate, a composite or a video fragment.",
            inputs=[
                Shots.Input("shots"),
                io.Int.Input("shot_id", default=1, min=1, max=999),
                io.String.Input(
                    "media_filename",
                    tooltip="A file name in one of " + ", ".join(MEDIA_DIRS),
                ),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def execute(cls, shots, shot_id, media_filename):
        out = copy.deepcopy(shots)
        project = Path(out["project_dir"])
        # All four media folders, in the one search order there is. Looking only
        # in images/ meant a map plate or a stacked composite could not be
        # assigned here at all, though shots.csv has always allowed it.
        found = next((project / d / media_filename for d in MEDIA_DIRS
                      if (project / d / media_filename).exists()), None)
        if found is None:
            raise ValueError(f"{media_filename!r} is in none of "
                             f"{', '.join(MEDIA_DIRS)} under {project}")
        entries = out["doc"]["shots"]
        for s in entries:
            if s["id"] == shot_id:
                s["image"] = media_filename
                # Recorded so the renderer does not have to search again, and
                # so a stale path from the previous media cannot win.
                s["image_path"] = found.relative_to(project).as_posix()
                break
        else:
            raise ValueError(f"no shot {shot_id}; this table has 1..{len(entries)}")
        return io.NodeOutput(out)
