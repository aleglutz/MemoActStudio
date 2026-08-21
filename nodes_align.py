"""Alignment node — "my words become timings" (SPEC §5.1).

Wraps `memoacts_core.pipeline.align_project`. The script is ground truth:
alignment computes *timings only*, never text, so the CapCut error class — dates
and names mangled by transcription — cannot occur here.

This is the one slow step, and it is on its own node for that reason. Its cache
key is the script and the recording, so every later edit to the shot table is
free; only re-recording or rewriting costs another pass over the audio.

This node runs locally only. Comfy Cloud has no aligner, which is why P1 used
the prepared-inputs model (SPEC §4) and shipped `shots.json` as an asset.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io

from .memoacts_core.pipeline import align_project, read_project
from .memoacts_core.project import find_narration
from .nodes_types import Alignment, Project


class MemoActsAlign(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAlign",
            display_name="MemoActs — Align",
            category="memoacts",
            description=(
                "Aligns the recording to the script and emits the timings. "
                "Nothing is transcribed — the words on screen are the ones you "
                "wrote, and only their timing is computed. The slow step: it "
                "runs once and is cached until the script or the recording "
                "changes."
            ),
            inputs=[
                Project.Input("project"),
                io.Combo.Input(
                    "lang", options=["en"], default="en",
                    tooltip="English only, by project scope (SPEC v3.1). "
                            "Translation happens outside this workflow.",
                ),
                io.Combo.Input(
                    "model",
                    options=["tiny", "base", "small", "medium"],
                    default="small",
                    tooltip="Whisper model used for alignment only, never for "
                            "transcription. Larger is slower, not necessarily "
                            "more accurate for timings.",
                ),
                io.Boolean.Input(
                    "skip_alignment", default=False,
                    tooltip="Spread the shots evenly instead of listening to "
                            "the recording. No model, instant, and the timings "
                            "are wrong — for trying the rest of the graph out.",
                ),
            ],
            outputs=[Alignment.Output("ALIGNMENT")],
        )

    @classmethod
    def fingerprint_inputs(cls, project, lang, model, skip_alignment):
        """Re-run when the script or the recording changes on disk — only then.

        Deliberately blind to `shots.csv` and to the media: those belong to the
        shot table, and a student who moves a picture must not pay for another
        alignment to see it.
        """
        folder = Path(project["project_dir"])
        stamps = []
        for p in (folder / "script.md", find_narration(folder)):
            try:
                stamps.append(p.stat().st_mtime_ns if p else 0)
            except OSError:
                stamps.append(0)
        return f"{folder}|{stamps}|{lang}|{model}|{skip_alignment}"

    @classmethod
    def execute(cls, project, lang, model, skip_alignment):
        folder = Path(project["project_dir"])
        read = read_project(folder)
        alignment = align_project(folder, read, lang=lang, model=model,
                                  use_aligner=not skip_alignment,
                                  progress=_progress)
        for w in alignment.warnings:
            print(f"[MemoActs] warning: {w}")
        return io.NodeOutput({"alignment": alignment,
                              "project_dir": str(folder)})


def _progress(stage, done=0, total=0, message="", preview=None):
    """Say what is happening, since nothing else can.

    `align()` is one opaque call into stable-whisper: no callback, no chunks,
    no fraction to report. A line before it starts is the honest maximum, and
    it matters because the first run also downloads the model.
    """
    if message:
        print(f"[MemoActs] {message}")
