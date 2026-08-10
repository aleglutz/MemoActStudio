"""Reel renderer CLI (P2 local path, SPEC §5.3/§5.5/§5.7).

    python tools/render_reel.py --project projects/demo_en
        [--out <path.mp4>] [--no-subs] [--crf 19]
        [--on-upscale warn|error|allow] [--shots <shots.json>]

Reads  <project>/generated/shots.json, <project>/images/, <project>/narration.*
Writes <project>/out/reel.mp4 plus the .ass/.srt subtitle tracks beside it.

This is the whole pipeline downstream of alignment, in one pass: crop rects ->
frames -> libass burn-in -> H.264 + narration. It supersedes the P1 pair of
run_p1_local.py (chunked graph submission) and assemble_reel.py (concat + mux)
— chunking and concatenation both existed to work around a memory limit that
the streaming renderer removes (GAPS.md #2).

Run tools/generate_shots.py first; this consumes its output. Keeping the two
separate is deliberate (SPEC §4): shots.json is a file a human can read and
edit between the two steps.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from memoacts_core import subs  # noqa: E402
from memoacts_core.project import resolve_media  # noqa: E402
from memoacts_core.effects import PRESETS, preset  # noqa: E402
from memoacts_core.render import ShotRender, render_reel  # noqa: E402
from memoacts_core.schedule import Motion, compute  # noqa: E402


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
    ap.add_argument("--plate", type=float, default=0.55,
                    help="opacity of the box behind the caption; 0 falls back "
                         "to the plain outline style (default: 0.55)")
    ap.add_argument("--on-upscale", default="warn",
                    choices=["warn", "error", "allow"],
                    help="what to do when a source cannot fill the output "
                         "(SPEC §5.2 resolution guard)")
    ap.add_argument("--effects", default="none", choices=sorted(PRESETS),
                    help="effect preset applied to every shot (SPEC §5.4)")
    args = ap.parse_args()

    proj = args.project
    shots_path = args.shots or proj / "generated" / "shots.json"
    if not shots_path.exists():
        print(f"no shots.json at {shots_path} — run tools/generate_shots.py first")
        return 1
    doc = json.loads(shots_path.read_text(encoding="utf-8"))

    narration = proj / doc.get("narration", "")
    if not narration.exists():
        narration = next(iter(proj.glob("narration.*")), None)
        if narration is None:
            print(f"no narration.* in {proj}")
            return 1

    fps = doc["fps"]
    out_w, out_h = doc.get("width", 1080), doc.get("height", 1920)

    shots: list[ShotRender] = []
    for s in doc["shots"]:
        img = resolve_media(proj, s)
        if not img.exists():
            print(f"missing media for shot {s['id']}: {img}")
            return 1
        with Image.open(img) as im:
            src_w, src_h = im.size
        sched = compute(src_w, src_h, s["n_frames"], Motion(**s["motion"]),
                        out_w=out_w)
        # A fresh stack per shot: the pipeline holds decoder state (texture
        # clip position), so sharing one across shots would interleave them.
        fx = preset(args.effects) if args.effects != "none" else None
        shots.append(ShotRender(image=img, schedule=sched, effects=fx))

    out_path = args.out or proj / "out" / "reel.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ass = None
    if not args.no_subs:
        style = subs.SubStyle(plate_opacity=args.plate, size=args.sub_size)
        cues = subs.cues_from_shots(doc["shots"], style, out_w,
                                    segment=not args.no_segment)
        ass, srt = subs.write_tracks(out_path.parent, cues, stem=out_path.stem,
                                     style=style)
        # A wrapped caption stacks two plates and puts a dark bar through the
        # text, so this is a defect report, not a style note.
        for c in subs.check_wrap(cues, style, out_w):
            print(f"  WRAPS (plates will overlap): {c.text!r}")
        print(f"subtitles: {len(cues)} cues from {len(doc['shots'])} blocks "
              f"-> {ass.name}, {srt.name}")

    total = sum(len(s.schedule.ws) for s in shots)
    print(f"rendering {len(shots)} shots, {total} frames "
          f"({total / fps:.3f} s at {fps} fps) -> {out_path.name}")

    render_reel(shots, out_path, fps, narration=narration, ass=ass,
                crf=args.crf, out_w=out_w, out_h=out_h,
                on_upscale=args.on_upscale)

    print(f"wrote {out_path}")
    # The reel is frame-quantised, so it is normally a few ms longer than the
    # narration. A large gap means the shot table and the audio disagree.
    drift = total / fps - doc.get("duration_s", total / fps)
    print(f"video {total / fps:.3f} s vs narration {doc.get('duration_s')} s "
          f"(drift {drift * 1000:+.0f} ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
