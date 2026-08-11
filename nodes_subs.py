"""Subtitle track node (SPEC §5.5) — wraps `memoacts_core.subs`.

Emits the `.ass` used for burn-in plus an `.srt` sidecar. The burn-in itself
happens inside the render pass (`nodes_encode`), drawing each cue once via
libass rather than onto every frame — the GAPS.md #3 fix, measured free against
P1's ~2.6× per-frame cost.
"""
from __future__ import annotations

import logging
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
                io.Int.Input("size", default=56, min=8, max=200),
                io.Color.Input("color", default="#FFFFFF"),
                io.Int.Input(
                    "margin_v", default=420, min=0, max=1800,
                    tooltip="Gap from the bottom edge, in output pixels. Keeps "
                            "captions clear of the platform's own UI overlay; "
                            "the exact safe-zone figures are still unverified.",
                ),
                io.Float.Input("shadow", default=2.0, min=0.0, max=10.0, step=0.5),
                io.Float.Input("outline", default=0.0, min=0.0, max=10.0, step=0.5),
                io.Float.Input(
                    "plate_opacity", default=0.55, min=0.0, max=1.0, step=0.05,
                    tooltip="Opacity of the box drawn behind the caption. "
                            "Archival stills run from near-black to bare paper, "
                            "and no single text colour stays readable over both; "
                            "the plate makes the caption independent of the "
                            "image under it. 0 disables it and falls back to "
                            "the outline/shadow style.",
                ),
                io.Color.Input("plate_color", default="#000000"),
                io.Float.Input(
                    "plate_pad", default=10.0, min=0.0, max=40.0, step=1.0,
                    tooltip="How far the plate extends past the text.",
                ),
                io.Boolean.Input(
                    "segment", default=True,
                    tooltip="Cut each narration block into captions that fit "
                            "on one line, at the aligner's word timings. Off "
                            "gives one caption per block, as P1 did — long "
                            "blocks then wrap, and wrapped lines stack their "
                            "plates into a dark bar through the text.",
                ),
                io.Float.Input(
                    "min_duration", default=1.0, min=0.0, max=5.0, step=0.1,
                    tooltip="Shortest a caption may stay up, in seconds. Only "
                            "spends silence that follows it; never overlaps "
                            "the next caption.",
                ),
                io.Float.Input(
                    "label_hold", default=3.0, min=0.0, max=30.0, step=0.5,
                    tooltip="Seconds a corner tag stays up from its shot's "
                            "start — the `label` column of shots.csv, naming a "
                            "place or a person. 0 leaves them out. It rides in "
                            "the same .ass as the captions, so it costs "
                            "nothing per frame.",
                ),
                io.Int.Input("label_size", default=40, min=8, max=200),
                io.Int.Input(
                    "label_margin_v", default=220, min=0, max=1800,
                    tooltip="Gap from the *top* edge, in output pixels: the tag "
                            "is anchored top-right, so its margin runs the "
                            "other way from the caption's.",
                ),
                io.String.Input("stem", default="subtitles"),
            ],
            outputs=[Subs.Output("SUBS")],
        )

    @classmethod
    def execute(cls, shots, size, color, margin_v, shadow, outline,
                plate_opacity, plate_color, plate_pad, segment, min_duration,
                label_hold, label_size, label_margin_v, stem):
        doc = shots["doc"]
        out_dir = Path(shots["project_dir"]) / "out"

        style = core_subs.SubStyle(
            size=size, primary=color, margin_v=margin_v,
            shadow_depth=shadow, outline_width=outline,
            plate_opacity=plate_opacity, plate_colour=plate_color,
            plate_pad=plate_pad,
        )
        play_w = doc.get("width", core_subs.PLAY_W)
        cues = core_subs.cues_from_shots(doc["shots"], style, play_w,
                                         segment=segment,
                                         min_duration=min_duration)
        label_st = core_subs.label_style(size=label_size,
                                         margin_v=label_margin_v,
                                         plate_opacity=plate_opacity,
                                         plate_colour=plate_color)
        labels = ([] if label_hold <= 0 else
                  core_subs.labels_from_shots(doc["shots"], hold=label_hold))
        ass, srt = core_subs.write_tracks(out_dir, cues, stem=stem, style=style,
                                          labels=labels, label_st=label_st)
        wrapped = core_subs.check_wrap(cues, style, play_w)
        for c in wrapped:
            logging.warning("MemoActsSubtitles: caption wraps, its plate will "
                            "overlap the next line: %r", c.text)
        for c in core_subs.check_wrap(labels, label_st, play_w):
            logging.warning("MemoActsSubtitles: label is too wide for one "
                            "line: %r", c.text)
        return io.NodeOutput({"ass": str(ass), "srt": str(srt),
                              "cues": len(cues), "wrapped": len(wrapped),
                              "labels": len(labels)})
