"""A camera path across a single still, rendered as a clip (SPEC §5.2).

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru.jpg --name S12_ru_page_move \
        --frames 360 \
        --key 0.00:0.500,0.500,0.774 \
        --key 0.30:0.360,0.600,0.581 \
        --key 0.62:0.640,0.560,0.581 \
        --key 1.00:0.520,0.375,0.581

Writes `<project>/composites/<name>.mp4`.

Why a clip rather than a motion preset: a preset is one gesture, and a shot
boundary starts it again from the beginning. A document being read is one
gesture that outlasts a line of narration — so the path is baked once here, and
the shots that need it read consecutive parts through `shots.csv`'s `in`
column. `memoacts_core.video` already treats footage as a still that changes
every frame, so nothing downstream knows this shot is a photograph.

A key is `t:cx,cy,w`, all fractions of the source: `t` along the clip, `cx`/`cy`
the centre of the window, `w` its width. Between keys the move eases in and out,
which means the camera arrives at each key and settles before leaving it —
reading a page, not sweeping past it.

The window never leaves the image and, unless told otherwise, never falls below
the output width: a path that would enlarge the source is a path the source
cannot support, and the honest fix is a better scan, not a bigger crop.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.project import MEDIA_DIRS  # noqa: E402
from memoacts_core.render import RESAMPLE, encode, load_source  # noqa: E402

OUT_W, OUT_H = 1080, 1920


def parse_key(spec: str) -> tuple[float, float, float, float]:
    """`t:cx,cy,w` -> (t, cx, cy, w), all fractions."""
    try:
        t, rest = spec.split(":", 1)
        cx, cy, w = (float(v) for v in rest.split(","))
        t = float(t)
    except ValueError:
        raise SystemExit(f"key {spec!r}: expected t:cx,cy,w as fractions")
    for name, v in (("t", t), ("cx", cx), ("cy", cy), ("w", w)):
        if not 0.0 <= v <= 1.0:
            raise SystemExit(f"key {spec!r}: {name} is a fraction, got {v}")
    return t, cx, cy, w


def ease(t: float) -> float:
    """Cosine ease, the same curve `memoacts_core.schedule` uses, so a baked
    path and a motion preset feel like the same hand."""
    return (1 - math.cos(math.pi * min(max(t, 0.0), 1.0))) / 2


def resolve(project: Path, name: str) -> Path:
    for folder in MEDIA_DIRS:
        cand = project / folder / name
        if cand.exists():
            return cand
    raise SystemExit(f"{name}: in none of {', '.join(MEDIA_DIRS)}")


def window(keys, t: float, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """The crop box at time `t`, in source pixels, clamped inside the image."""
    W, H = size
    for (t0, x0, y0, w0), (t1, x1, y1, w1) in zip(keys, keys[1:]):
        if t <= t1 or (t1, x1, y1, w1) is keys[-1]:
            span = t1 - t0
            k = ease((t - t0) / span) if span > 0 else 1.0
            cx = x0 + (x1 - x0) * k
            cy = y0 + (y1 - y0) * k
            w = w0 + (w1 - w0) * k
            break
    ww = int(round(w * W))
    hh = int(round(ww * OUT_H / OUT_W))
    if hh > H:                       # taller than the page: fit the height
        hh, ww = H, int(round(H * OUT_W / OUT_H))
    left = int(round(cx * W - ww / 2))
    top = int(round(cy * H - hh / 2))
    left = max(0, min(left, W - ww))
    top = max(0, min(top, H - hh))
    return left, top, left + ww, top + hh


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--key", action="append", default=[],
                    help="t:cx,cy,w in fractions of the source, repeated; "
                         "at least two, ordered by t")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=12)
    ap.add_argument("--on-upscale", default="warn",
                    choices=["warn", "error", "allow"])
    args = ap.parse_args()

    keys = sorted((parse_key(k) for k in args.key), key=lambda k: k[0])
    if len(keys) < 2:
        print("need at least two keys"); return 1

    src = load_source(resolve(args.project, args.image))
    W, H = src.size
    print(f"{args.image} {W}x{H} -> {args.frames} frames at {args.fps} fps")

    narrowest = min(window(keys, i / max(args.frames - 1, 1), src.size)[2]
                    - window(keys, i / max(args.frames - 1, 1), src.size)[0]
                    for i in range(args.frames))
    if narrowest < OUT_W:
        msg = (f"{args.image}: the path reaches {narrowest}px wide for a "
               f"{OUT_W}px output ({OUT_W / narrowest:.2f}x enlargement)")
        if args.on_upscale == "error":
            raise SystemExit(msg)
        if args.on_upscale == "warn":
            print(f"  WARNING {msg}")
    for t, cx, cy, w in keys:
        box = window(keys, t, src.size)
        print(f"  key t={t:.2f}  centre {cx:.3f},{cy:.3f}  width {w:.3f} "
              f"-> crop {box[2] - box[0]}x{box[3] - box[1]} at {box[0]},{box[1]}")

    def frames():
        for i in range(args.frames):
            t = i / max(args.frames - 1, 1)
            yield src.crop(window(keys, t, src.size)).resize(
                (OUT_W, OUT_H), RESAMPLE)

    dest = args.project / "composites" / f"{args.name}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    encode(frames(), dest, args.fps, crf=args.crf,
           out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    print(f"wrote {dest}  {args.frames} frames "
          f"({args.frames / args.fps:.2f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
