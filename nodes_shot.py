"""Per-shot editing nodes (SPEC §5.2 — "the interactive heart").

Defaults must produce a decent reel with zero per-shot input, so the creator
edits **by exception**. `MemoActsSetMotion` is that exception mechanism: it
overrides one shot (or all of them) and leaves the rest alone.

The resolution guard lives here too, surfaced as an inspectable report rather
than only as a render-time warning — by the time `render` warns, the image has
already been assigned to the shot (`GAPS.md`).
"""
from __future__ import annotations

import copy
from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.project import MEDIA_DIRS, resolve_media
from .memoacts_core.schedule import PRESETS, Motion, compute
from .nodes_types import Shots


class MemoActsSetMotion(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSetMotion",
            display_name="MemoActs — Set Motion",
            category="memoacts",
            description=(
                "Overrides the motion preset for one shot, or for every shot. "
                "Chain several to edit by exception."
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
                               "focus": s.get("motion", {}).get("focus")}
        return io.NodeOutput(out)


class MemoActsSetImage(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSetImage",
            display_name="MemoActs — Set Shot Image",
            category="memoacts",
            description="Assigns a different image from the project's images/ "
                        "folder to one shot.",
            inputs=[
                Shots.Input("shots"),
                io.Int.Input("shot_id", default=1, min=1, max=999),
                io.String.Input("image_filename",
                                tooltip="File name inside <project>/images/"),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def execute(cls, shots, shot_id, image_filename):
        out = copy.deepcopy(shots)
        target = Path(out["project_dir"]) / MEDIA_DIRS[0] / image_filename
        if not target.exists():
            raise ValueError(f"no such image: {target}")
        for s in out["doc"]["shots"]:
            if s["id"] == shot_id:
                s["image"] = image_filename
                break
        else:
            raise ValueError(f"no shot {shot_id} in this table")
        return io.NodeOutput(out)


class MemoActsShotReport(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsShotReport",
            display_name="MemoActs — Shot Report",
            category="memoacts",
            description=(
                "Human-readable shot table: timings, alignment confidence, "
                "motion, and the resolution guard's verdict per shot."
            ),
            is_output_node=True,
            inputs=[Shots.Input("shots")],
            outputs=[],
        )

    @classmethod
    def execute(cls, shots):
        from PIL import Image as PILImage

        doc = shots["doc"]
        project = Path(shots["project_dir"])
        fps, out_w = doc["fps"], doc.get("width", 1080)

        lines = [
            f"{doc['narration']}  {doc['duration_s']:.2f}s  {fps} fps  "
            f"lang {doc['lang']}  lead {doc['shot_lead_ms']}ms",
            f"{len(doc['shots'])} shots, {sum(s['n_frames'] for s in doc['shots'])} frames",
            "",
        ]
        for s in doc["shots"]:
            img = resolve_media(project, s)
            try:
                with PILImage.open(img) as im:
                    src_w, src_h = im.size
                sched = compute(src_w, src_h, s["n_frames"],
                                Motion(**s["motion"]), out_w=out_w)
                widest = max(sched.ws, default=out_w)
                # Two distinct warnings: CLAMPED means the zoom was reduced to
                # stay legal; UPSCALED means even the widest frame cannot fill
                # the output, which no amount of clamping fixes.
                flags = []
                if s.get("estimated"):
                    flags.append("ESTIMATED")
                if sched.clamped:
                    flags.append("CLAMPED")
                if widest < out_w:
                    flags.append(f"UPSCALED {out_w / widest:.2f}x")
                guard = f"max_zoom {sched.max_zoom:.2f}x"
            except Exception as exc:                       # noqa: BLE001
                flags, guard = ["IMAGE ERROR"], str(exc)[:60]

            lines.append(
                f"shot {s['id']:02d}  {s['t_start']:6.2f}–{s['t_end']:6.2f}s "
                f"({s['n_frames']:4d} fr)  conf {s.get('confidence', 0):.2f}  "
                f"{s['image']}  {s['motion']['preset']}@{s['motion']['rate']:.2f}  "
                f"{guard}" + (f"  [{', '.join(flags)}]" if flags else ""))
            lines.append(f"          {s['text'][:96]}")

        return io.NodeOutput(ui=ui.PreviewText("\n".join(lines)))
