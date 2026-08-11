"""Schedule generator CLI (P1 prepared-inputs model, SPEC §4).

    python tools/generate_shots.py --project projects/sidur --lang ru
        [--model small] [--fps 30] [--lead-ms 100] [--max-chunk 30]
        [--out projects/sidur/generated]

Reads  <project>/narration.mp3, <project>/script.md, <project>/images/
Writes <out>/shots.json, <out>/crops/*.csv, <out>/report.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.align import StableTsAligner, proportional_spans
from memoacts_core.normalize import normalize_block
from memoacts_core.project import (apply_shot_lead, list_images,
                                   parse_script_shots, resolve_shot_images,
                                   write_outputs)
from memoacts_core.schedule import (FOCUSABLE, Motion, compute, default_motion,
                                    frames_for)
from memoacts_core.shotlist import apply_shot_list, read_shot_list


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--lang", required=True, choices=["ru", "en"])
    ap.add_argument("--model", default="small")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--lead-ms", type=int, default=100)
    # 30, not 60: Comfy Cloud kills a job whose execution passes somewhere
    # between ~21 s and ~44 s (GAPS.md, 2026-07-28). At the measured 0.35-0.54 s
    # per frame, 60-frame chunks land at 44-49 s and die; 30 frames stays around
    # 16 s even on the slowest source measured. The old 60 came from local RAM
    # headroom (GAPS #2) and is unrelated to this limit -- raise it only for
    # local rendering, where tools/render_reel.py does not chunk at all.
    ap.add_argument("--max-chunk", type=int, default=30)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-align", action="store_true",
                    help="proportional timing only (no model, for dry runs)")
    args = ap.parse_args()

    proj = args.project
    narration = proj / "narration.mp3"
    if not narration.exists():
        narration = next(iter(proj.glob("narration.*")), None)
        if narration is None:
            print("no narration.* in", proj); return 1
    script_shots = parse_script_shots(proj / "script.md")
    blocks = [s.text for s in script_shots]
    images = list_images(proj / "images")
    if not script_shots:
        print("script.md has no shots"); return 1
    if not images:
        print("images/ is empty"); return 1

    imgs, warnings = resolve_shot_images(script_shots, images)

    # shots.csv wins over the script's own [[refs]] and over cycling: it is the
    # edit decision, made after both.
    edits = read_shot_list(proj / "shots.csv")
    picks, edit_warnings = apply_shot_list(script_shots, edits, proj)
    warnings += edit_warnings
    footage = [f"shot {i}" for i, p in enumerate(picks, 1) if p.is_video]
    if footage:
        print(f"error: {len(footage)} shot(s) reference footage "
              f"({', '.join(footage)}), which this pipeline cannot render yet — "
              f"video fragments are SPEC §0 'Won't' for September and the "
              f"cutting model is still undecided. Use a still for now.")
        return 1
    for i, p in enumerate(picks):
        if p.media is not None:
            imgs[i] = p.media

    for w in warnings:
        print(f"warning: {w}")
    from_csv = sum(1 for p in picks if p.media is not None)
    if from_csv:
        print(f"shots.csv: {from_csv} shot(s) placed by the shot list")
    named = sum(1 for s in script_shots if s.assets)
    silent = [s.label or f"shot {i}" for i, s in enumerate(script_shots, 1) if s.silent]
    print(f"{len(script_shots)} shots — {named} with a storyboard image, "
          f"{len(script_shots) - named} cycled from images/")
    if silent:
        # Silent shots get their duration from the pause between neighbours; if
        # the narrator did not pause, they collapse to a single frame.
        print(f"silent shots (no narration): {', '.join(silent)}")

    normed, flags = [], []
    for b in blocks:
        n, had = normalize_block(b, args.lang)
        normed.append(n)
        flags.append(had)

    aligner = StableTsAligner(args.model)
    duration = aligner.audio_duration(narration)
    if args.no_align:
        spans = proportional_spans(blocks, duration)
    else:
        print(f"aligning {len(blocks)} blocks against {narration.name} "
              f"({duration:.1f}s, model={args.model}, lang={args.lang})…")
        # normed is what the model listens for; blocks is what reaches the
        # screen. Both are needed — see StableTsAligner.align.
        spans = aligner.align(narration, normed, args.lang, blocks)
    spans = apply_shot_lead(spans, args.lead_ms)

    n_frames = frames_for([(s.t_start, s.t_end) for s in spans], args.fps)

    from PIL import Image
    motions, schedules = [], []
    for i, (img, nf) in enumerate(zip(imgs, n_frames)):
        with Image.open(img) as im:
            src_w, src_h = im.size
        mot = default_motion(i)
        pick = picks[i]
        if pick.motion:
            mot = Motion(preset=pick.motion,
                         rate=pick.rate if pick.rate is not None else mot.rate,
                         anchor=pick.anchor or mot.anchor)
        elif pick.rate is not None or pick.anchor:
            mot = Motion(preset=mot.preset,
                         rate=pick.rate if pick.rate is not None else mot.rate,
                         anchor=pick.anchor or mot.anchor)
        if pick.focus is not None:
            if mot.preset in FOCUSABLE:
                mot.focus = pick.focus
            else:
                # Silently dropping it would leave a shot list that reads as if
                # the framing had been decided (SPEC §6.2.12: legible failure).
                print(f"warning: shot {i + 1} sets a focus but its motion is "
                      f"{mot.preset!r}, which traverses rather than arrives; "
                      f"focus ignored. Use one of {', '.join(FOCUSABLE)}.")
        motions.append(mot)
        schedules.append(compute(src_w, src_h, nf, mot))

    out = args.out or proj / "generated"
    path = write_outputs(out, lang=args.lang, fps=args.fps, narration=narration.name,
                         duration=duration, lead_ms=args.lead_ms, blocks=blocks,
                         norm_blocks=normed, digit_flags=flags, spans=spans,
                         images=imgs, motions=motions, schedules=schedules,
                         n_frames=n_frames, max_chunk=args.max_chunk,
                         cues=[sh.cue for sh in script_shots],
                         labels=[p.label for p in picks])
    print("wrote", path)
    print((out / "report.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
