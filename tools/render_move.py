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
own pixels — `s = 1.0` is one page pixel per output pixel, and above that the
page is magnified, which is reported at every key rather than refused: a scan
too small for the framing a shot needs is an editorial fact, not an error, and
the project's rule is that enlargement is never *silent* (UPSCALE.md).

A page smaller than the frame leaves its edge, and the bed, in shot. The tool
says which keys do that, because usually it is a mistake. A page whose edge
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

`--shutter` opens the frame for part of its own interval and accumulates the
sheet's travel across it, which is the difference between a fast traverse and a
stutter. It is off by default, so every render made before it existed still
comes out identical.

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

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core import subs  # noqa: E402
from memoacts_core.project import MEDIA_DIRS, parse_hook  # noqa: E402
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


def parse_turn(spec: str) -> tuple[float, float, int]:
    """`t0,t1,page` -> the page is turned over between t0 and t1, revealing it."""
    try:
        t0, t1, page = spec.split(",")
        return float(t0), float(t1), int(page)
    except ValueError:
        raise SystemExit(f"turn {spec!r}: expected t0,t1,page as fractions and "
                         "a 1-based page number")


def fold(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    """Page `a` turning off to the left, revealing `b`. `u` runs 0 to 1.

    A cut between two scans says "another page"; it does not say a hand. What
    reads as a hand is the crease: a seam travelling across the frame, the
    lifted part of the sheet folded back over itself and foreshortened, its
    underside catching less light the further it leans, and a shadow thrown
    onto the page underneath. All of that is 2D — the sheet is never modelled,
    only mirrored and squeezed — which is enough at this speed, and keeps the
    turn a compositing step rather than a renderer.
    """
    W, H = a.size
    x_s = int(round((1.0 - u) * W))          # the crease, sweeping right to left
    out = np.asarray(a, dtype=np.float32).copy()
    nb = np.asarray(b, dtype=np.float32)

    if x_s < W:
        out[:, x_s:] = nb[:, x_s:]
        # The lifted sheet throws a shadow on what it uncovers, strongest at
        # the crease. Without it the two pages read as one flat collage.
        shade_w = min(90, W - x_s)
        if shade_w > 1:
            g = np.linspace(0.52, 1.0, shade_w, dtype=np.float32)[None, :, None]
            out[:, x_s:x_s + shade_w] *= g

    lift = W - x_s
    flap_w = int(round(lift * (1.0 - u) ** 0.7))
    if flap_w >= 2 and lift >= 2:
        flap = np.asarray(
            a.crop((x_s, 0, W, H)).transpose(Image.FLIP_LEFT_RIGHT)
             .resize((flap_w, H), RESAMPLE), dtype=np.float32)
        # The underside leans away from the light: darkest at the free edge,
        # nearly unshaded at the crease.
        g = np.linspace(0.44, 0.92, flap_w, dtype=np.float32)[None, :, None]
        flap *= g
        x0 = max(0, x_s - flap_w)
        out[:, x0:x_s] = flap[:, flap_w - (x_s - x0):]
        # A bright line where the sheet folds over itself.
        if 0 < x_s < W:
            out[:, max(0, x_s - 2):x_s] = np.minimum(
                out[:, max(0, x_s - 2):x_s] * 1.35 + 26, 255)

    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def holds(keys) -> list[tuple[float, float]]:
    """Where the camera stops: two consecutive keys that ask for the same frame.

    The move already carries the timing, so a caption written for a beat does
    not need one of its own — and cannot drift from one. Re-time the move and
    the line follows it.
    """
    return [(a[0], b[0]) for a, b in zip(keys, keys[1:])
            if (a[1], a[2], a[3]) == (b[1], b[2], b[3]) and b[0] > a[0]]


def captions(args, keys) -> Path:
    """Write the clip's .ass from the script's HOOK block. -> the file.

    The lines fill the holds from the *last* one backwards. The last hold is
    what a cold open is built to arrive at, and a clip whose opening hold is a
    title card should not have a line over it.
    """
    # The reel captions across the middle of the frame, because its subjects sit
    # centre-frame and a caption at the foot makes the eye travel. A move is the
    # opposite case: the camera *aims* at the beat, so the middle is occupied by
    # construction and a centred caption lands on the one thing being shown.
    style = subs.SubStyle(alignment=2, margin_v=420)
    lines = parse_hook(args.caption_from)
    if not lines:
        raise SystemExit(f"{args.caption_from}: no HOOK block to caption with")
    stops = holds(keys)
    if len(stops) < len(lines):
        raise SystemExit(
            f"{args.name}: the HOOK block has {len(lines)} lines and the move "
            f"has {len(stops)} holds to put them on")
    duration = args.frames / args.fps
    cues = [subs.Cue(t0 * duration, t1 * duration, text)
            for (t0, t1), text in zip(stops[len(stops) - len(lines):], lines)]
    for c in cues:
        print(f"  caption {c.t_start:5.2f}-{c.t_end:5.2f} s  {c.text!r}")
    ass, _ = subs.write_tracks(args.project / "composites", cues,
                               stem=args.name, style=style)
    return ass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--image", action="append", default=[],
                    help="page, repeated; a key's fourth field selects one "
                         "(1-based) and switches to it at that instant")
    ap.add_argument("--name", required=True)
    ap.add_argument("--key", action="append", default=[],
                    help="t:cx,cy,s[,page]; at least two, ordered by t")
    ap.add_argument("--turn", action="append", default=[],
                    help="t0,t1,page — turn the sheet over between t0 and t1, "
                         "revealing that page; repeatable")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=12)
    ap.add_argument("--bed", default=",".join(str(v) for v in BED),
                    help="R,G,B of the surface the page lies on")
    ap.add_argument("--ease", default="cosine", choices=["cosine", "linear"])
    ap.add_argument("--shutter", type=float, default=0.0,
                    help="motion blur, as the fraction of a frame interval the "
                         "shutter stays open (0.5 is the film convention, 180 "
                         "degrees). 0, the default, leaves every existing "
                         "render bit-identical")
    ap.add_argument("--subframes", type=int, default=48,
                    help="ceiling on the samples accumulated per frame; the "
                         "number actually taken follows how far the sheet "
                         "moves during the exposure")
    ap.add_argument("--caption-from", type=Path,
                    help="a script.md whose HOOK block supplies the captions; "
                         "one line per hold, filled from the last hold back, "
                         "because the last hold is what the clip is about")
    ap.add_argument("--on-upscale", default="warn",
                    choices=["warn", "error", "allow"],
                    help="a path may magnify a page past its own pixels; this "
                         "says whether that stops the render. Default warn: it "
                         "is reported and recorded, never silent")
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

    turns = sorted((parse_turn(t) for t in args.turn), key=lambda t: t[0])
    # A turn is a page change, so it belongs in the page timeline before
    # anything reads it. Getting this wrong once cost a run whose coverage
    # report was computed against the wrong scan entirely: the keys after a
    # turn still claimed page 1, which is 1024px wide where the others are
    # 1860, and every one of them was reported as leaving the frame.
    filled2 = []
    for k in keys:
        page = k[4]
        for t0, t1, to in turns:
            if k[0] >= t1:
                page = to
        filled2.append(k[:4] + (page,))
    keys = filled2

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

    gaps: list[float] = []
    for t, cx, cy, s, page in keys:
        W, H = pages[page - 1].size
        pw, ph = int(round(W * s)), int(round(H * s))
        covers = (pw >= OUT_W and ph >= OUT_H
                  and cx * OUT_W - pw / 2 <= 0 and cx * OUT_W + pw / 2 >= OUT_W
                  and cy * OUT_H - ph / 2 <= 0 and cy * OUT_H + ph / 2 >= OUT_H)
        print(f"  key t={t:.3f}  page {page}  centre {cx:.3f},{cy:.3f}  "
              f"s={s:.2f} -> {pw}x{ph} px  "
              f"{'full bleed' if covers else 'EDGE IN FRAME'}")
        if not covers:
            gaps.append(t)

    if gaps:
        print("  WARNING the page leaves the frame at t=" +
              ", ".join(f"{t:.3f}" for t in gaps) +
              " and the bed shows there; raise s at those keys to cover it")

    for t0, t1, page in turns:
        print(f"  turn  {t0:.3f}-{t1:.3f} -> page {page} "
              f"({(t1 - t0) * args.frames / args.fps:.2f} s)")

    def compose(src: Image.Image, cx: float, cy: float, s: float, cache) -> Image.Image:
        pw = max(1, int(round(src.size[0] * s)))
        ph = max(1, int(round(src.size[1] * s)))
        key = (id(src), pw)
        if key not in cache:
            cache.clear()
            cache[key] = src.resize((pw, ph), RESAMPLE)
        frame = Image.new("RGB", (OUT_W, OUT_H), bed)
        frame.paste(cache[key], (int(round(cx * OUT_W - pw / 2)),
                                 int(round(cy * OUT_H - ph / 2))))
        return frame

    cache: dict[tuple[int, int], Image.Image] = {}
    cache_b: dict[tuple[int, int], Image.Image] = {}

    def still(t: float) -> Image.Image:
        """The sheet as it stands at an instant — not necessarily a frame."""
        cx, cy, s, page = at(keys, t, ease)
        # A turn owns the page on both sides of itself: before it ends the
        # sheet on top is the one being turned, after it the one revealed.
        for t0, t1, to in turns:
            if t >= t1:
                page = to
        for t0, t1, to in turns:
            if t0 <= t < t1:
                before = at(keys, max(t0 - 1e-6, 0.0), ease)
                from_page, s_out = before[3], before[2]
                s_in = at(keys, t1, ease)[2]
                # Each sheet keeps its own scale through the turn. They
                # differ because the scans do — 1024px against 1860px for
                # the same sheet of paper — so interpolating between them
                # would shrink the page being turned while it turns, which
                # is the one thing paper does not do.
                return fold(compose(pages[from_page - 1], cx, cy, s_out, cache),
                            compose(pages[to - 1], cx, cy, s_in, cache_b),
                            (t - t0) / (t1 - t0))
        return compose(pages[page - 1], cx, cy, s, cache)

    def travel(t0: float, t1: float) -> float:
        """How far the sheet moves across the frame between two instants, px."""
        a, b = at(keys, t0, ease), at(keys, t1, ease)
        return math.hypot((b[0] - a[0]) * OUT_W, (b[1] - a[1]) * OUT_H)

    def frames():
        step = 1.0 / max(args.frames - 1, 1)
        for i in range(args.frames):
            t = i * step
            if args.shutter <= 0:
                yield still(t)
                continue
            # A frame is an exposure, not an instant. Sampling the path across
            # the time the shutter is open is what stops a fast traverse from
            # strobing: at 30 fps a whip moves a tenth of the frame between
            # frames, and the eye reads that as a stutter rather than as speed.
            # The samples are spaced by *distance*, not by count: a fixed count
            # smears a hold for nothing and leaves a whip as a row of separate
            # ghosts, which is the artefact it was meant to remove. One sample
            # per pixel and a half; a hold costs two. Cheap because nothing is
            # resampled — the sheet runs at s = 1.0 and a sample is one paste.
            half = 0.5 * args.shutter * step
            lo, hi = max(t - half, 0.0), min(t + half, 1.0)
            n = min(max(int(travel(lo, hi) / 1.5) + 2, 2), max(2, args.subframes))
            acc = None
            for j in range(n):
                sub = np.asarray(still(lo + (hi - lo) * j / (n - 1)), dtype=np.float32)
                acc = sub if acc is None else acc + sub
            yield Image.fromarray(np.clip(acc / n, 0, 255).astype(np.uint8))
    dest = args.project / "composites" / f"{args.name}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    ass = captions(args, keys) if args.caption_from else None
    encode(frames(), dest, args.fps, crf=args.crf, ass=ass,
           out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    print(f"wrote {dest}  {args.frames} frames "
          f"({args.frames / args.fps:.2f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
