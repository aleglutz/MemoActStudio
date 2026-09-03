"""Reel renderer CLI (P2 local path, SPEC §5.3/§5.5/§5.7).

    python tools/render_reel.py --project projects/demo_en
        [--out <path.mp4>] [--no-subs] [--crf 19]
        [--on-upscale warn|error|allow] [--shots <shots.json>]

Reads  <project>/generated/shots.json and <project>/sources/
Writes <project>/out/reel.mp4 plus the .ass/.srt subtitle tracks beside it.

This is the whole pipeline downstream of alignment, in one pass: crop rects ->
frames -> libass burn-in -> H.264 + narration. It supersedes the P1 pair of
run_p1_local.py (chunked graph submission) and assemble_reel.py (concat + mux)
— chunking and concatenation both existed to work around a memory limit that
the streaming renderer removes (GAPS.md #2).

Run tools/generate_shots.py first; this consumes its output. Keeping the two
separate is deliberate (SPEC §4): shots.json is a file a human can read and
edit between the two steps.

The work is `memoacts_core.pipeline.render_project`, which the Render node
calls with the same options object — the flags below are its fields.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.effects import PRESETS  # noqa: E402
from memoacts_core.pipeline import (ProjectError, RenderOptions,  # noqa: E402
                                    console_progress,
                                    build_sfx_bed, read_sound_design,
                                    render_project)


#: The pipeline's own phrasing, straight to stdout.
printer = console_progress()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--shots", type=Path, default=None,
                    help="default: <project>/generated/shots.json")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <project>/out/reel.mp4")
    ap.add_argument("--no-subs", action="store_true",
                    help="render without burning in the subtitle track")
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--sub-size", type=int, default=56,
                    help="caption font size in output pixels (default: 56)")
    ap.add_argument("--no-segment", action="store_true",
                    help="one caption per narration block, as P1 did, instead "
                         "of cutting blocks into single-line captions at word "
                         "timings")
    ap.add_argument("--plate", type=float, default=None,
                    help="opacity of the box behind the caption; 0 falls back "
                         "to the plain outline style. Default: whatever "
                         "subs.SubStyle carries, which is what the cold open "
                         "renders with — the two must not drift apart")
    ap.add_argument("--no-labels", action="store_true",
                    help="skip the corner tags naming a place or a person")
    ap.add_argument("--label-hold", type=float, default=3.0,
                    help="seconds a corner tag stays up from the shot's start "
                         "(default: 3.0)")
    ap.add_argument("--on-upscale", default="warn",
                    choices=["warn", "error", "allow"],
                    help="what to do when a source cannot fill the output "
                         "(SPEC §5.2 resolution guard)")
    ap.add_argument("--effects", default="none", choices=sorted(PRESETS),
                    help="effect preset for every shot that names none of its "
                         "own in shots.csv (SPEC §5.4)")
    ap.add_argument("--sfx", action="store_true",
                    help="build the sound design bed from <project>/sfx.csv "
                         "and mix it under the narration (SPEC §5.6). The "
                         "recording itself is never re-timed or re-levelled")
    ap.add_argument("--sfx-gain", type=float, default=0.0,
                    help="the whole sound layer up or down, in dB, after the "
                         "per-row gains (default: 0)")
    ap.add_argument("--no-duck", action="store_true",
                    help="do not step the sounds back under the voice — how "
                         "you hear the gains in sfx.csv on their own")
    ap.add_argument("--shot", type=int, action="append", default=None,
                    help="render only this shot, by number; repeatable. A "
                         "preview: no narration and no captions, because both "
                         "are timed from the head of the reel")
    args = ap.parse_args()

    proj = args.project
    shots_path = args.shots or proj / "generated" / "shots.json"
    if not shots_path.exists():
        print(f"no shots.json at {shots_path} — run tools/generate_shots.py first")
        return 1
    doc = json.loads(shots_path.read_text(encoding="utf-8"))

    bed = None
    if args.sfx:
        try:
            design = read_sound_design(proj, doc)
            bed, _ = build_sfx_bed(proj, doc, design.placed,
                                   master_db=args.sfx_gain,
                                   duck=not args.no_duck, progress=printer)
        except ProjectError as exc:
            print(exc)
            return 1
        for w in design.warnings:
            print(f"[MemoActs] {w}")

    opts = RenderOptions(subs=not args.no_subs, sub_size=args.sub_size,
                         segment=not args.no_segment, plate=args.plate,
                         labels=not args.no_labels, label_hold=args.label_hold,
                         crf=args.crf, on_upscale=args.on_upscale,
                         effects=args.effects, sfx=bed)
    try:
        res = render_project(proj, doc, out=args.out, opts=opts,
                             shot_ids=args.shot, progress=printer)
    except ProjectError as exc:
        print(exc)
        return 1

    for w in res.warnings:
        print(f"[MemoActs] {w}")
    print(f"wrote {res.path}")
    if args.shot is None:
        print(f"video {res.duration_s:.3f} s vs narration "
              f"{doc.get('duration_s')} s (drift {res.drift_s * 1000:+.0f} ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
