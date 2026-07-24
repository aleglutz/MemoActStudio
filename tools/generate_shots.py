"""Schedule generator CLI (P1 prepared-inputs model, SPEC §4).

    python tools/generate_shots.py --project projects/sidur --lang ru
        [--model small] [--fps 30] [--lead-ms 100] [--max-chunk 60]
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
from memoacts_core.project import (apply_shot_lead, list_images, parse_script,
                                   write_outputs)
from memoacts_core.schedule import Motion, compute, default_motion, frames_for


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--lang", required=True, choices=["ru", "en"])
    ap.add_argument("--model", default="small")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--lead-ms", type=int, default=100)
    ap.add_argument("--max-chunk", type=int, default=60)
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
    blocks = parse_script(proj / "script.md")
    images = list_images(proj / "images")
    if not blocks:
        print("script.md has no blocks"); return 1
    if not images:
        print("images/ is empty"); return 1
    if len(images) < len(blocks):
        print(f"note: {len(blocks)} shots but {len(images)} images — cycling images")
    imgs = [images[i % len(images)] for i in range(len(blocks))]

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
        spans = aligner.align(narration, normed, args.lang)
    spans = apply_shot_lead(spans, args.lead_ms)

    n_frames = frames_for([(s.t_start, s.t_end) for s in spans], args.fps)

    from PIL import Image
    motions, schedules = [], []
    for i, (img, nf) in enumerate(zip(imgs, n_frames)):
        with Image.open(img) as im:
            src_w, src_h = im.size
        mot = default_motion(i)
        motions.append(mot)
        schedules.append(compute(src_w, src_h, nf, mot))

    out = args.out or proj / "generated"
    path = write_outputs(out, lang=args.lang, fps=args.fps, narration=narration.name,
                         duration=duration, lead_ms=args.lead_ms, blocks=blocks,
                         norm_blocks=normed, digit_flags=flags, spans=spans,
                         images=imgs, motions=motions, schedules=schedules,
                         n_frames=n_frames, max_chunk=args.max_chunk)
    print("wrote", path)
    print((out / "report.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
