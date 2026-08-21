"""Schedule generator CLI (P1 prepared-inputs model, SPEC §4).

    python tools/generate_shots.py --project projects/sidur --lang ru
        [--model small] [--fps 30] [--lead-ms 100] [--max-chunk 30]
        [--out projects/sidur/generated]

Reads  <project>/sources/narration.*, <project>/script.md, <project>/sources/images/
Writes <out>/shots.json, <out>/crops/*.csv, <out>/report.txt

The work is `memoacts_core.pipeline`; this file is the argument surface and the
printing. The ComfyUI nodes call the same three functions in the same order, so
what a student runs and what is written here cannot drift apart.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.pipeline import (ProjectError, align_project,  # noqa: E402
                                    compose_project, read_project)


def printer(stage: str, done: int = 0, total: int = 0, message: str = "",
            preview=None) -> None:
    """Show the lines the pipeline phrases; ignore the counters and frames."""
    if message:
        print(message)


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

    try:
        read = read_project(args.project)
    except ProjectError as exc:
        print(exc)
        return 1

    for note in read.notes:
        print(note)
    for w in read.warnings:
        print(f"warning: {w}")

    alignment = align_project(args.project, read, lang=args.lang,
                              model=args.model, use_aligner=not args.no_align,
                              progress=printer)
    for w in alignment.warnings:
        print(f"warning: {w}")

    comp = compose_project(args.project, read, alignment, fps=args.fps,
                           lead_ms=args.lead_ms, max_chunk=args.max_chunk,
                           out=args.out)
    for w in comp.warnings:
        print(f"warning: {w}")

    print("wrote", comp.path)
    print(comp.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
