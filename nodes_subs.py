"""Subtitles node — "the words become captions" (SPEC §5.5).

Two things happen here, and only one of them is settings.

The settings travel on to the render, which writes the `.ass` and burns it in
one pass; a node that wrote its own track would be a second writer of the same
file, which is how the pack drifted from the CLI in the first place.

The other thing is the preview, and it is the reason this is a node rather than
four widgets on the render. Cutting captions is pure string work — no frames,
no ffmpeg — so the exact cues, at their real word timings, can be shown
instantly. That is also where a caption too wide for one line is caught, which
matters because a wrapped caption stacks two plates and puts a dark bar through
its own text: a defect, not a style note.

The text is the script, verbatim. Never the digits-expanded form the aligner
listens to, and never a transcription.
"""
from __future__ import annotations

from dataclasses import replace

from comfy_api.latest import io, ui

from .memoacts_core import caption, subs as core_subs
from .nodes_types import Shots, Subs

#: Defaults come from `subs.SubStyle` itself rather than being restated here.
#: They used to be restated, and drifted: the node offered margin_v 420 and a
#: plate at 0.55 while the reel was rendering at 530 and 0.68.
_STYLE = core_subs.SubStyle()


class MemoActsSubtitles(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSubtitles",
            display_name="MemoActs — Subtitles",
            category="memoacts",
            description=(
                "How the captions look, and what they will say. Shows the cues "
                "it would burn — cut from your own words at the timings the "
                "aligner measured — without rendering anything."
            ),
            is_output_node=True,
            inputs=[
                Shots.Input("shots"),
                io.Int.Input("size", default=_STYLE.size, min=8, max=200),
                io.Float.Input(
                    "plate_opacity", default=_STYLE.plate_opacity,
                    min=0.0, max=1.0, step=0.05,
                    tooltip="Opacity of the box behind the caption. Archival "
                            "stills run from near-black to bare paper, and no "
                            "single text colour stays readable over both; the "
                            "plate makes the caption independent of the image "
                            "under it. 0 disables it and falls back to the "
                            "outline/shadow style.",
                ),
                io.Boolean.Input(
                    "segment", default=True,
                    tooltip="Cut each block into captions that fit on one line, "
                            "at the aligner's word timings. Off gives one "
                            "caption per block, as P1 did — long blocks then "
                            "wrap, and wrapped lines stack their plates into a "
                            "dark bar through the text.",
                ),
                io.Float.Input(
                    "min_duration", default=1.0, min=0.0, max=5.0, step=0.1,
                    tooltip="Shortest a caption may stay up, in seconds. Only "
                            "spends silence that follows it; never overlaps the "
                            "next caption.",
                ),
                io.Float.Input(
                    "label_hold", default=3.0, min=0.0, max=30.0, step=0.5,
                    tooltip="Seconds a corner tag stays up from its shot's "
                            "start — the label column of shots.csv, naming a "
                            "place or a person. 0 leaves them out, along with "
                            "the credit lines. It rides in the same .ass as the "
                            "captions, so it costs nothing per frame.",
                ),
            ],
            outputs=[Subs.Output("SUBS")],
        )

    @classmethod
    def execute(cls, shots, size, plate_opacity, segment, min_duration,
                label_hold):
        doc = shots["doc"]
        play_w = doc.get("width", core_subs.PLAY_W)
        style = replace(_STYLE, size=size, plate_opacity=plate_opacity)

        cues = core_subs.cues_from_shots(doc["shots"], style, play_w,
                                         segment=segment,
                                         min_duration=min_duration)
        labels = ([] if label_hold <= 0
                  else core_subs.labels_from_shots(doc["shots"], hold=label_hold))
        credits = [] if label_hold <= 0 else core_subs.credits_from_shots(doc["shots"])
        wrapped = core_subs.check_wrap(cues, style, play_w)

        widest = caption.widest(cues, size, core_subs.font_path())
        usable = caption.usable_width(
            play_w, style.margin_l, style.margin_r,
            style.plate_pad if style.plate_opacity > 0 else 0.0)
        lines = [
            f"{len(cues)} captions from {len(doc['shots'])} blocks, "
            f"{len(labels)} corner tags, {len(credits)} credits",
            f"widest caption {widest:.0f} px of {usable:.0f} usable at size {size}",
            "",
        ]
        for c in cues:
            lines.append(f"{c.t_start:7.2f}–{c.t_end:6.2f}  {c.text}")
        if wrapped:
            lines.append("")
            lines.append("WRAPS — these stack two plates and bar their own text:")
            lines += [f"  {c.text!r}" for c in wrapped]
            for c in wrapped:
                print(f"[MemoActs] WRAPS (plates will overlap): {c.text!r}")

        return io.NodeOutput(
            {"sub_size": size, "plate": plate_opacity, "segment": segment,
             "min_duration": min_duration, "labels": label_hold > 0,
             "label_hold": label_hold},
            ui=ui.PreviewText("\n".join(lines)))
