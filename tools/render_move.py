"""A page moved under the camera, rendered as a clip (SPEC §5.2).

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 344 --ease linear \
        --key 0.000:0.780,0.460,0.62,1 \
        --key 0.150:0.500,0.500,0.62 \
        --key 0.473:0.620,0.400,0.58,2 \
        --key 1.000:0.466,0.667,1.00

Writes `<project>/composites/<name>.mp4`.

The model is a sheet of paper on a scanner bed, not a camera window over an
image. A key places the *page*: `cx`,`cy` are where its centre sits on the
frame in frame fractions, and `s` is its width as a fraction of the source's
own pixels — `s = 1.0` is one page pixel per output pixel, so anything above it
is enlargement and is refused by default. The page may be smaller than the
frame; then the bed shows around it, which is the point. A page whose edge
never leaves the frame reads as a photograph of a document, and a page whose
edge crosses the frame reads as a document being handled.

Two things follow from that and are worth stating, because they are the reason
this exists rather than a motion preset:

- **Several pages, one movement.** `--image` repeats; a key's fourth field
  switches to that page *at that instant*. A page change is a cut, which is how
  turning a page reads when the camera does not move with it.
- **The movement outlives a shot.** A preset restarts at every shot boundary,
  so a gesture spanning two lines of narration cannot be written in shots.csv
  at all. Here the path is baked once and the shots read consecutive parts of
  it through the `in` column, as `memoacts_core.video` already does for footage.

`--ease linear` holds a constant speed and stops dead at a key, which is what a
sheet shoved across glass does; `cosine` (the default) arrives and settles, and
matches `memoacts_core.schedule` so a baked path and a preset feel like one
hand.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.project import MEDIA_DIRS  # noqa: E402
from memoacts_core.render import RESAMPLE, encode, load_source  # noqa: E402

OUT_W, OUT_H = 1080, 1920

#: Bed colour. The deep tone of the map palette (`render_map.PALETTES["ink"]`),
#: so the surface a document lies on and the sea on the plates are the same
#: colour — the reel has two drawn surfaces and no reason for them to disagree.
BED = (28, 32, 44)


def parse_key(spec: str) -> tuple[float, float, float, float, int | None]:
    """`t:cx,cy,s[,page]` -> (t, cx, cy, s, page or None)."""
    try:
        t, rest = spec.split(":", 1)
        parts = rest.split(",")
        cx, cy, s = (float(v) for v in parts[:3])
        page = int(parts[3]) if len(parts) > 3 and parts[3].strip() else None
        t = float(t)
    except (ValueError, IndexError):
        raise SystemExit(f"key {spec!r}: expected t:cx,cy,s[,page]")
    if not 0.0 <= t <= 1.0:
        raise SystemExit(f"key {spec!r}: t is a fraction of the clip, got {t}")
    if s <= 0:
        raise SystemExit(f"key {spec!r}: s is a width fraction, got {s}")
    return t, cx, cy, s, page


def parse_bed(spec: str) -> tuple[int, int, int]:
    try:
        r, g, b = (int(v) for v in spec.split(","))
        return r, g, b
    except ValueError:
        raise SystemExit(f"--bed {spec!r}: expected R,G,B")


def resolve(project: Path, name: str) -> Path:
    for folder in MEDIA_DIRS:
        cand = project / folder / name
        if cand.exists():
            return cand
    raise SystemExit(f"{name}: in none of {', '.join(MEDIA_DIRS)}")


def ease_cosine(t: float) -> float:
    return (1 - math.cos(math.pi * min(max(t, 0.0), 1.0))) / 2


def at(keys, t: float, ease) -> tuple[float, float, float, int]:
    """Placement at time `t`: page centre, width fraction, and which page.

    The page index does not interpolate — it steps at its key, so a page change
    is a cut on one frame rather than a dissolve nobody asked for.
    """
    prev = keys[0]
    for nxt in keys[1:]:
        if t <= nxt[0]:
            span = nxt[0] - prev[0]
            k = ease((t - prev[0]) / span) if span > 0 else 1.0
            page = nxt[4] if (span == 0 or t >= nxt[0]) and nxt[4] else prev[4]
            return (prev[1] + (nxt[1] - prev[1]) * k,
                    prev[2] + (nxt[2] - prev[2]) * k,
                    prev[3] + (nxt[3] - prev[3]) * k,
                    page)
        prev = nxt
    return prev[1], prev[2], prev[3], prev[4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--image", action="append", default=[],
                    help="page, repeated; a key's fourth field selects one "
                         "(1-based) and switches to it at that instant")
    ap.add_argument("--name", required=True)
    ap.add_argument("--key", action="append", default=[],
                    help="t:cx,cy,s[,page]; at least two, ordered by t")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=12)
    ap.add_argument("--bed", default=",".join(str(v) for v in BED),
                    help="R,G,B of the surface the page lies on")
    ap.add_argument("--ease", default="cosine", choices=["cosine", "linear"])
    ap.add_argument("--on-upscale", default="error",
                    choices=["warn", "error", "allow"])
    args = ap.parse_args()

    if not args.image:
        print("need at least one --image"); return 1
    keys = sorted((parse_key(k) for k in args.key), key=lambda k: k[0])
    if len(keys) < 2:
        print("need at least two keys"); return 1
    if keys[0][4] is None:
        keys[0] = keys[0][:4] + (1,)
    # Carry the page forward, so only the keys that change it name one.
    filled, page = [], keys[0][4]
    for k in keys:
        page = k[4] or page
        filled.append(k[:4] + (page,))
    keys = filled

    pages = [load_source(resolve(args.project, name)) for name in args.image]
    for name, im in zip(args.image, pages):
        print(f"  page {name} {im.size[0]}x{im.size[1]}")
    bed = parse_bed(args.bed)
    ease = ease_cosine if args.ease == "cosine" else (lambda t: t)

    worst = max(k[3] for k in keys)
    if worst > 1.0:
        msg = (f"the path magnifies a page to {worst:.2f}x its own pixels; "
               "a page cannot supply detail it does not have")
        if args.on_upscale == "error":
            raise SystemExit(f"{args.name}: {msg}")
        if args.on_upscale == "warn":
            print(f"  WARNING {msg}")

    for t, cx, cy, s, page in keys:
        W, H = pages[page - 1].size
        pw, ph = int(round(W * s)), int(round(H * s))
        covers = (pw >= OUT_W and ph >= OUT_H
                  and cx * OUT_W - pw / 2 <= 0 and cx * OUT_W + pw / 2 >= OUT_W
                  and cy * OUT_H - ph / 2 <= 0 and cy * OUT_H + ph / 2 >= OUT_H)
        print(f"  key t={t:.3f}  page {page}  centre {cx:.3f},{cy:.3f}  "
              f"s={s:.2f} -> {pw}x{ph} px  "
              f"{'full bleed' if covers else 'bed visible'}")

    def frames():
        cache: dict[tuple[int, int], Image.Image] = {}
        for i in range(args.frames):
            t = i / max(args.frames - 1, 1)
            cx, cy, s, page = at(keys, t, ease)
            src = pages[page - 1]
            pw = max(1, int(round(src.size[0] * s)))
            ph = max(1, int(round(src.size[1] * s)))
            key = (page, pw)
            if key not in cache:
                # One resize per distinct width, not per frame: a slide holds
                # its scale for many frames and the resample is the expensive
                # part. Keyed on the page too, or a page change would inherit
                # the other page's pixels.
                cache.clear()
                cache[key] = src.resize((pw, ph), RESAMPLE)
            frame = Image.new("RGB", (OUT_W, OUT_H), bed)
            frame.paste(cache[key], (int(round(cx * OUT_W - pw / 2)),
                                     int(round(cy * OUT_H - ph / 2))))
            yield frame

    dest = args.project / "composites" / f"{args.name}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    encode(frames(), dest, args.fps, crf=args.crf,
           out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    print(f"wrote {dest}  {args.frames} frames "
          f"({args.frames / args.fps:.2f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
