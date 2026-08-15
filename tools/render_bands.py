"""Stacked 9:16 frames where each band moves on its own (SPEC §5.2).

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S14_three-band --frames 360 \
        --band GIoS_Wehrmacht_Signed_Ru.jpg:0.277:zoom_in:0.08 \
        --band Wehrmacht_in_Karlshorst.jpg:0.482:pan_lr:0.10 \
        --band GIoS_Wehrmacht_Signed_En.jpg:0.530:zoom_out:0.08

Writes `<project>/composites/<name>.mp4`, or `<name>.png` with `--still`.

`docs/THREEBAND_TOOL.md` builds the same frame in ComfyUI and freezes it to a
PNG. That is the right tool for choosing the framing — you drag each band by
eye. This one takes the framing as numbers and makes it move: a band is 1080x636
rather than 9:16, so each one gets its own `schedule.compute` at the band's
aspect and its own preset, and three sources drift independently inside one
still-looking frame.

`--still` and `--mono` exist so that the *whole* set of stacked frames a reel
needs can be rebuilt here. Three of this project's composites were frozen stills
made in ComfyUI with a source-available node whose licence forbids
redistribution (`SURVEY.md §3`), which put them outside anything the repository
could reproduce — and an asset a project cannot rebuild is one nobody can
correct. `--still` renders the opening frame with motion held; `--mono` is a
plain luminance conversion, applied last, after the bands are seated.

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
    ap.add_argument("--frames", type=int, default=None,
                    help="clip length in frames; ignored (and unnecessary) "
                         "with --still")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=12)
    ap.add_argument("--still", action="store_true",
                    help="write one PNG instead of a clip; every band is held "
                         "at its opening framing")
    ap.add_argument("--mono", action="store_true",
                    help="convert the finished frame to black and white")
    args = ap.parse_args()

    if len(args.band) < 2:
        print("need at least two bands"); return 1
    if args.still:
        args.frames = 1
    elif args.frames is None:
        print("--frames is required unless --still"); return 1

    bh = band_height(len(args.band))
    aspect = OUT_W / bh
    print(f"{len(args.band)} bands of {OUT_W}x{bh}, {SEAM}px seams "
          f"-> {bh * len(args.band) + SEAM * (len(args.band) - 1)} of {OUT_H}")

    plans = []
    for spec in args.band:
        name, cy, preset, rate = parse_band(spec)
        path = resolve(args.project, name)
        src = load_source(path)
        if args.still and preset != "static":
            # Say it rather than silently dropping the band's preset: the spec
            # strings are copied between a clip and a still, and a motion that
            # quietly stopped happening is the kind of difference nobody looks
            # for later.
            print(f"  {name}: {preset} held — a still has no motion")
            preset, rate = "static", 0.0
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

    def compose(i: int) -> Image.Image:
        frame = Image.new("RGB", (OUT_W, OUT_H), SEAM_RGB)
        y = 0
        for src, sched, ys in plans:
            box = (sched.xs[i], ys[i],
                   sched.xs[i] + sched.ws[i], ys[i] + sched.hs[i])
            frame.paste(src.crop(box).resize((OUT_W, bh), RESAMPLE), (0, y))
            y += bh + SEAM
        # Last, so the seams and every band desaturate together rather than one
        # band at a time — and so a colour band added later cannot be missed.
        return frame.convert("L").convert("RGB") if args.mono else frame

    dest_dir = args.project / "composites"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if args.still:
        dest = dest_dir / f"{args.name}.png"
        compose(0).save(dest)
        print(f"wrote {dest}  one frame{'  b/w' if args.mono else ''}")
        return 0

    dest = dest_dir / f"{args.name}.mp4"
    encode((compose(i) for i in range(args.frames)), dest, args.fps,
           crf=args.crf, out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    print(f"wrote {dest}  {args.frames} frames{'  b/w' if args.mono else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
