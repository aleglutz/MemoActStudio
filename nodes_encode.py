"""Render/encode node (SPEC §5.3, §5.7) — wraps `memoacts_core.render`.

One ffmpeg pass for the whole reel: per-frame crops streamed from PIL, subtitles
burnt once via libass, narration muxed untouched. Memory is constant in reel
length, so there is no chunking here and no concat step — both existed in P1
only to work around the tensor-batch limit (`GAPS.md` #2).
"""
from __future__ import annotations

import copy
import warnings
from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.render import ShotRender, render_reel
from .memoacts_core.project import resolve_media
from .memoacts_core.schedule import Motion, compute
from .memoacts_core.video import is_video, probe
from .nodes_types import Shots, Subs


class MemoActsRenderReel(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsRenderReel",
            display_name="MemoActs — Render Reel",
            category="memoacts",
            description=(
                "Renders the shot table to a finished vertical MP4 with "
                "narration and optional burnt-in subtitles."
            ),
            is_output_node=True,
            inputs=[
                Shots.Input("shots"),
                Subs.Input("subtitles", optional=True),
                io.String.Input("filename_prefix", default="memoacts/reel"),
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
    def execute(cls, shots, filename_prefix, crf, on_upscale, subtitles=None):
        import folder_paths
        from PIL import Image as PILImage

        doc = shots["doc"]
        project = Path(shots["project_dir"])
        fps = doc["fps"]
        out_w, out_h = doc.get("width", 1080), doc.get("height", 1920)

        narration = project / doc.get("narration", "")
        if not narration.exists():
            narration = next(iter(sorted(project.glob("narration.*"))), None)
        if narration is None:
            raise ValueError(f"no narration audio in {project}")

        stacks = shots.get("effects") or {}
        renders: list[ShotRender] = []
        for s in doc["shots"]:
            img = resolve_media(project, s)
            if not img.exists():
                raise ValueError(f"shot {s['id']}: missing media {img}")
            if is_video(img):
                src_w, src_h = probe(img).size
            else:
                with PILImage.open(img) as im:
                    src_w, src_h = im.size
            # Each shot gets its own copy: the pipeline holds decoder state for
            # a texture clip, so a shared stack would interleave two shots'
            # positions in the same loop.
            stack = stacks.get(s["id"])
            renders.append(ShotRender(
                media=img,
                schedule=compute(src_w, src_h, s["n_frames"],
                                 Motion(**s["motion"]), out_w=out_w),
                effects=copy.deepcopy(stack) if stack is not None else None,
                media_in=s.get("media_in") or 0.0,
                speed=s.get("speed") or 1.0,
            ))

        out_dir = Path(folder_paths.get_output_directory())
        prefix = Path(filename_prefix)
        subfolder = str(prefix.parent) if str(prefix.parent) != "." else ""
        target_dir = out_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        # Never overwrite an earlier take: a student re-rendering after an edit
        # should be able to compare against the previous one.
        n = 1
        while (target_dir / f"{prefix.name}_{n:05d}.mp4").exists():
            n += 1
        out_path = target_dir / f"{prefix.name}_{n:05d}.mp4"

        ass = Path(subtitles["ass"]) if subtitles else None

        total = sum(len(r.schedule.ws) for r in renders)
        print(f"[MemoActs] rendering {len(renders)} shots, {total} frames "
              f"({total / fps:.3f}s at {fps} fps) -> {out_path.name}")

        # Surface the resolution-guard warnings in the ComfyUI log rather than
        # letting Python swallow them into a filtered default.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            render_reel(renders, out_path, fps, narration=narration, ass=ass,
                        crf=crf, out_w=out_w, out_h=out_h,
                        on_upscale=on_upscale)
        for w in caught:
            print(f"[MemoActs] {w.message}")

        drift_ms = (total / fps - doc.get("duration_s", total / fps)) * 1000
        print(f"[MemoActs] wrote {out_path.name}; video {total / fps:.3f}s vs "
              f"narration {doc.get('duration_s')}s (drift {drift_ms:+.0f} ms)")

        return io.NodeOutput(ui=ui.PreviewVideo([ui.SavedResult(
            filename=out_path.name,
            subfolder=subfolder,
            type=io.FolderType.output,
        )]))
