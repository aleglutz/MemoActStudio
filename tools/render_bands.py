"""Stacked 9:16 frames where each band moves on its own (SPEC §5.2).

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S14_three-band --frames 360 \
        --band GIoS_Wehrmacht_Signed_Ru.jpg:0.277:zoom_in:0.08 \
        --band Wehrmacht_in_Karlshorst.jpg:0.482:pan_lr:0.10 \
        --band GIoS_Wehrmacht_Signed_En.jpg:0.530:zoom_out:0.08

Writes `<project>/composites/<name>.mp4`.

`docs/THREEBAND_TOOL.md` builds the same frame in ComfyUI and freezes it to a
PNG. That is the right tool for choosing the framing — you drag each band by
eye. This one takes the framing as numbers and makes it move: a band is 1080x636
rather than 9:16, so each one gets its own `schedule.compute` at the band's
aspect and its own preset, and three sources drift independently inside one
still-looking frame.

The output is a clip because `memoacts_core.video` already makes footage
indistinguishable from a still to the rest of the reel — same as the animated
map plates. Nothing in the render path knows this shot is assembled.

A band's spec is `file[:cy[:preset[:rate]]]`, where `cy` is the vertical centre
of the band's window as a fraction of its source — the one framing decision the
DragCrop node exists to make, carried over as a number.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.project import MEDIA_DIRS  # noqa: E402
from memoacts_core.render import RESAMPLE, encode, load_source  # noqa: E402
from memoacts_core.schedule import Motion, PRESETS, compute  # noqa: E402

OUT_W, OUT_H = 1080, 1920
SEAM = 6                      # black rule between bands, as in the ComfyUI tool
SEAM_RGB = (0, 0, 0)


def band_height(n: int) -> int:
    """Band height for `n` bands, seams included: 636 for three, 957 for two."""
    return (OUT_H - SEAM * (n - 1)) // n


def parse_band(spec: str) -> tuple[str, float, str, float]:
    """`file[:cy[:preset[:rate]]]` -> (file, cy, preset, rate)."""
    parts = spec.split(":")
    name = parts[0]
    cy = float(parts[1]) if len(parts) > 1 and parts[1] else 0.5
    preset = parts[2] if len(parts) > 2 and parts[2] else "static"
    rate = float(parts[3]) if len(parts) > 3 and parts[3] else 0.06
    if preset not in PRESETS:
        raise SystemExit(f"band {name}: unknown preset {preset!r}; "
                         f"choose from {', '.join(PRESETS)}")
    if not 0.0 <= cy <= 1.0:
        raise SystemExit(f"band {name}: cy is a fraction of the source, got {cy}")
    return name, cy, preset, rate


def resolve(project: Path, name: str) -> Path:
    for folder in MEDIA_DIRS:
        cand = project / folder / name
        if cand.exists():
            return cand
    raise SystemExit(f"{name}: in none of {', '.join(MEDIA_DIRS)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--band", action="append", default=[],
                    help="file[:cy[:preset[:rate]]], repeated per band, top first")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=12)
    args = ap.parse_args()

    if len(args.band) < 2:
        print("need at least two bands"); return 1

    bh = band_height(len(args.band))
    aspect = OUT_W / bh
    print(f"{len(args.band)} bands of {OUT_W}x{bh}, {SEAM}px seams "
          f"-> {bh * len(args.band) + SEAM * (len(args.band) - 1)} of {OUT_H}")

    plans = []
    for spec in args.band:
        name, cy, preset, rate = parse_band(spec)
        path = resolve(args.project, name)
        src = load_source(path)
        sched = compute(*src.size, args.frames, Motion(preset=preset, rate=rate),
                        out_w=OUT_W, aspect=aspect)
        # Re-seat the window on the band's chosen centre. `compute` frames
        # vertically on the source's middle; the operator picked something else
        # when they dragged this band, and that choice has to survive every zoom
        # level rather than being reasserted only at the start.
        shift = round(cy * src.size[1] - src.size[1] / 2)
        ys = [min(max(y + shift, 0), max(src.size[1] - h, 0))
              for y, h in zip(sched.ys, sched.hs)]
        narrowest = min(sched.ws)
        print(f"  {name:36s} {str(src.size):12s} {preset}@{rate:.2f} "
              f"cy={cy:.3f}  crop {narrowest}px "
              f"{'-> x%.2f ENLARGES' % (OUT_W / narrowest) if narrowest < OUT_W else 'ok'}")
        plans.append((src, sched, ys))

    def frames():
        for i in range(args.frames):
            frame = Image.new("RGB", (OUT_W, OUT_H), SEAM_RGB)
            y = 0
            for src, sched, ys in plans:
                box = (sched.xs[i], ys[i],
                       sched.xs[i] + sched.ws[i], ys[i] + sched.hs[i])
                frame.paste(src.crop(box).resize((OUT_W, bh), RESAMPLE), (0, y))
                y += bh + SEAM
            yield frame

    dest = args.project / "composites" / f"{args.name}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    encode(frames(), dest, args.fps, crf=args.crf,
           out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    print(f"wrote {dest}  {args.frames} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
