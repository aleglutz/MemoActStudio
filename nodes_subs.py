"""Subtitle track node (SPEC §5.5) — wraps `memoacts_core.subs`.

Emits the `.ass` used for burn-in plus an `.srt` sidecar. The burn-in itself
happens inside the render pass (`nodes_encode`), drawing each cue once via
libass rather than onto every frame — the GAPS.md #3 fix, measured free against
P1's ~2.6× per-frame cost.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io

from .memoacts_core import subs as core_subs
from .nodes_types import Shots, Subs


class MemoActsSubtitles(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSubtitles",
            display_name="MemoActs — Subtitles",
            category="memoacts",
            description=(
                "Builds the .ass burn-in track and .srt sidecar from the shot "
                "table. Uses the verbatim script text, never the "
                "digits-expanded form fed to the aligner."
            ),
            inputs=[
                Shots.Input("shots"),
                io.Int.Input("size", default=44, min=8, max=200),
                io.Color.Input("color", default="#FFFFFF"),
                io.Int.Input(
                    "margin_v", default=420, min=0, max=1800,
                    tooltip="Gap from the bottom edge, in output pixels. Keeps "
                            "captions clear of the platform's own UI overlay; "
                            "the exact safe-zone figures are still unverified.",
                ),
                io.Float.Input("shadow", default=2.0, min=0.0, max=10.0, step=0.5),
                io.Float.Input("outline", default=0.0, min=0.0, max=10.0, step=0.5),
                io.String.Input("stem", default="subtitles"),
            ],
            outputs=[Subs.Output("SUBS")],
        )

    @classmethod
    def execute(cls, shots, size, color, margin_v, shadow, outline, stem):
        doc = shots["doc"]
        out_dir = Path(shots["project_dir"]) / "out"

        style = core_subs.SubStyle(
            size=size, primary=color, margin_v=margin_v,
            shadow_depth=shadow, outline_width=outline,
        )
        cues = core_subs.cues_from_shots(doc["shots"])
        ass, srt = core_subs.write_tracks(out_dir, cues, stem=stem, style=style)
        return io.NodeOutput({"ass": str(ass), "srt": str(srt), "cues": len(cues)})
