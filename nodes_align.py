"""Alignment node — narration + script → editable shot table (SPEC §5.1).

Wraps `memoacts_core.align`. The script is ground truth: alignment computes
*timings only*, never text, so the CapCut error class (dates and names mangled
by transcription) cannot occur here.

This node runs locally only. Comfy Cloud has no aligner, which is why P1 used
the prepared-inputs model (SPEC §4) and shipped `shots.json` as an asset.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io

from .memoacts_core import SCHEMA_VERSION
from .memoacts_core.align import StableTsAligner, proportional_spans
from .memoacts_core.normalize import normalize_block
from .memoacts_core.project import (apply_shot_lead, list_images,
                                    parse_script_shots, resolve_shot_images)
from .memoacts_core.schedule import default_motion, frames_for
from .nodes_types import Shots


def _find_narration(project: Path) -> Path | None:
    return next(iter(sorted(project.glob("narration.*"))), None)


class MemoActsAlignShots(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAlignShots",
            display_name="MemoActs — Align Shots",
            category="memoacts",
            description=(
                "Aligns narration audio to a known script and emits the shot "
                "table. Reads <project>/script.md, <project>/narration.*, "
                "<project>/images/. Timings only — the script text is never "
                "altered."
            ),
            inputs=[
                io.String.Input(
                    "project_dir",
                    tooltip="Folder holding script.md, narration.*, images/",
                ),
                io.Combo.Input("lang", options=["en"], default="en"),
                io.Combo.Input(
                    "model",
                    options=["tiny", "base", "small", "medium"],
                    default="small",
                    tooltip="Whisper model used for alignment only, never for "
                            "transcription. Larger is slower, not necessarily "
                            "more accurate for timings.",
                ),
                io.Int.Input("fps", default=30, min=1, max=120),
                io.Int.Input(
                    "shot_lead_ms", default=100, min=0, max=1000,
                    tooltip="Cuts lead the sentence onset by this much. An "
                            "image arriving slightly early reads as "
                            "intentional; arriving late reads as a mistake.",
                ),
                io.Boolean.Input(
                    "skip_alignment", default=False,
                    tooltip="Spread shots proportionally instead of aligning. "
                            "Fast, for dry runs — timings will be wrong.",
                ),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def fingerprint_inputs(cls, project_dir, lang, model, fps, shot_lead_ms,
                           skip_alignment):
        """Re-run when the script or the narration changes on disk.

        Without this a student edits script.md, re-runs, and silently gets the
        previous shot table back — the widgets did not change, so ComfyUI would
        consider the node cached.
        """
        project = Path(project_dir)
        stamps = []
        for p in (project / "script.md", _find_narration(project)):
            try:
                stamps.append(p.stat().st_mtime_ns if p else 0)
            except OSError:
                stamps.append(0)
        return f"{stamps}|{lang}|{model}|{fps}|{shot_lead_ms}|{skip_alignment}"

    @classmethod
    def execute(cls, project_dir, lang, model, fps, shot_lead_ms,
                skip_alignment):
        project = Path(project_dir)
        if not project.is_dir():
            raise ValueError(f"project_dir is not a folder: {project}")

        script = project / "script.md"
        if not script.exists():
            raise ValueError(f"no script.md in {project}")
        script_shots = parse_script_shots(script)
        blocks = [s.text for s in script_shots]
        if not script_shots:
            raise ValueError(f"{script} has no shots")

        narration = _find_narration(project)
        if narration is None:
            raise ValueError(f"no narration.* audio file in {project}")

        images = list_images(project / "images")
        if not images:
            raise ValueError(f"no images in {project / 'images'}")

        imgs, warns = resolve_shot_images(script_shots, images)
        for w in warns:
            print(f"[MemoActs] warning: {w}")
        named = sum(1 for s in script_shots if s.assets)
        print(f"[MemoActs] {len(script_shots)} shots — {named} with a "
              f"storyboard image, {len(script_shots) - named} cycled")
        silent = [s.label or str(i)
                  for i, s in enumerate(script_shots, 1) if s.silent]
        if silent:
            # Duration comes from the pause between neighbours; no pause means
            # the shot collapses to one frame.
            print(f"[MemoActs] silent shots (no narration): {', '.join(silent)}")

        normed, had_digits = [], []
        for b in blocks:
            n, had = normalize_block(b, lang)
            normed.append(n)
            had_digits.append(had)

        aligner = StableTsAligner(model)
        duration = aligner.audio_duration(narration)
        if skip_alignment:
            spans = proportional_spans(blocks, duration)
        else:
            spans = aligner.align(narration, normed, lang)
        spans = apply_shot_lead(spans, shot_lead_ms)

        n_frames = frames_for([(s.t_start, s.t_end) for s in spans], fps)

        shots = []
        for i, (text, norm, span, img, nf) in enumerate(
                zip(blocks, normed, spans, imgs, n_frames)):
            m = default_motion(i)
            shots.append({
                "id": i + 1,
                "text": text,                    # verbatim — reaches the screen
                "text_normalized": norm,         # alignment only
                "t_start": round(span.t_start, 3),
                "t_end": round(span.t_end, 3),
                "n_frames": nf,
                "estimated": span.estimated,
                "confidence": round(span.confidence, 3),
                "had_digits": had_digits[i],
                "image": img.name,
                "motion": {"preset": m.preset, "rate": m.rate, "anchor": m.anchor},
            })

        doc = {
            "schema_version": SCHEMA_VERSION, "fps": fps,
            "width": 1080, "height": 1920, "lang": lang,
            "narration": narration.name, "duration_s": round(duration, 3),
            "shot_lead_ms": shot_lead_ms, "shots": shots,
        }
        return io.NodeOutput({"doc": doc, "project_dir": str(project)})
