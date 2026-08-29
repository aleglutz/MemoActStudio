"""The archivist's number, borrowed from the act rather than drawn (SPEC 5.2b).

    python tools/pencil_layer.py cut  --plate output/plate/act_paper_00001_.png \
        --act projects/legends_of_surrender/sources/images/GIoS_Wehrmacht_Signed_Ru_p1.jpg
    (run docs/workflows/pencil_67_api.json)
    python tools/pencil_layer.py lift --before ../../input/pencil_corner.png \
        --after output/pencil/67_00001_.png --out .../composites/pencil_67.png

`render_page.py` draws its pencil from stroke paths, because no open-licensed
hand exists in `assets/fonts/` and because what reads as indelible pencil is the
break of the stroke over the fibre, which a font cannot give. Stroke paths get
the break right and the *hand* wrong: the paths are regular in a way no one
writing a number in a margin in 1945 was.

A model can have the hand. It cannot have the eleven hundred characters of the
sheet -- which is the whole reason the type is set here and not generated -- but
two numerals against a reference of two other numerals is inside what
Qwen-Image-Edit does reliably, and the reference is on the act itself: the
pencilled "10" in the top corner of `GIoS_Wehrmacht_Signed_Ru_p1.jpg`.

Two subcommands, and the model sits between them:

`cut` writes the two crops the graph loads -- a corner of the finished plate,
which is where the number will go, and the act's own "10" for the hand to copy.

`lift` takes the difference between what went in and what came back. This is
the point of cutting from the plate rather than from a blank: the paper under
the mark is known exactly, so what the model added is recoverable exactly, as
an alpha rather than as a patch. A patch would carry the model's idea of paper
with it, and its idea of this paper is a guess; the alpha carries only the
pigment. Composited back, the mark sits on the sheet's real grain, and the
break of the stroke is the sheet's own.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.page import ACT_PENCIL  # noqa: E402

#: Where the act carries its number, and how much around it to take. Measured,
#: not eyeballed: on `GIoS_Wehrmacht_Signed_Ru_p1.jpg` the pixels where blue
#: runs more than 18 levels over red -- which is the mark and nothing else on
#: that sheet -- box to x 902-961, y 53-107 of 1024x1410. That is a centre of
#: 0.9097,0.0567 and a mark 3.83% of the sheet high, which on a 10240 sheet is
#: 392 px: the number to put in the `pencil` directive's `size`.
REF_AT = (0.910, 0.057)
REF_SIZE = 0.16


#: Qwen-Image-Edit works at about a megapixel. The corner is cut at 1024 and
#: the number placed inside it, so the mark arrives at the sheet at the size the
#: model drew it -- no resampling of pigment, which is what turns a pencil
#: stroke into a smudge.
CUT = 1024


def _crop(im: Image.Image, at: tuple[float, float], size: int) -> Image.Image:
    cx, cy = int(at[0] * im.width), int(at[1] * im.height)
    x, y = min(max(cx - size // 2, 0), im.width - size), min(max(cy - size // 2, 0), im.height - size)
    return im.crop((x, y, x + size, y + size))


def cut(args) -> int:
    plate = Image.open(args.plate).convert("RGB")
    corner = _crop(plate, (args.at[0], args.at[1]), CUT)
    corner.save(args.corner)
    print(f"wrote {args.corner}  {CUT}x{CUT} from the plate at {args.at[0]},{args.at[1]}")

    act = Image.open(args.act).convert("RGB")
    ref = _crop(act, REF_AT, int(min(act.size) * REF_SIZE))
    ref = ref.resize((CUT, CUT), Image.Resampling.LANCZOS)
    ref.save(args.ref)
    print(f"wrote {args.ref}  the act's own pencilled 10, at {REF_AT}")
    print("  check both crops before running the graph -- REF_AT is read off one "
          "scan and a different scan of the same page will not have it there")
    return 0


def lift(args) -> int:
    before = np.asarray(Image.open(args.before).convert("RGB"), dtype=np.float32)
    after = Image.open(args.after).convert("RGB")
    if after.size != (before.shape[1], before.shape[0]):
        after = after.resize((before.shape[1], before.shape[0]), Image.Resampling.LANCZOS)
    after = np.asarray(after, dtype=np.float32)

    # Pigment only darkens. A pixel the model made *brighter* is the model
    # rebuilding paper it had no need to touch, and it is not wanted.
    drop = np.clip(before - after, 0, 255).max(2)
    alpha = np.clip((drop - args.floor) / max(args.gain, 1.0), 0, 1)

    # The colour is what the mark is, not what it sits on: unmix the paper out
    # of it at the alpha found above, which is what compositing will put back.
    a = np.maximum(alpha, 1e-3)[:, :, None]
    rgb = np.clip(before + (after - before) / a, 0, 255)

    out = np.dstack([rgb, alpha[:, :, None] * 255]).astype(np.uint8)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(args.out)
    ink = alpha[alpha > 0.15]
    print(f"wrote {args.out}  mark covers {(alpha > 0.15).mean() * 100:.2f}% of the crop")
    if ink.size:
        px = rgb[alpha > 0.5]
        print(f"  pigment {px.mean(0).round(0) if px.size else '-'}  "
              f"(the act's own core is {ACT_PENCIL})")
    if (alpha > 0.15).mean() > 0.08:
        print("  WARNING more than 8% of the crop changed -- the model repainted "
              "the paper as well as writing on it. Reroll, or raise --floor.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cut", help="write the two crops the graph loads")
    c.add_argument("--plate", type=Path, required=True)
    c.add_argument("--act", type=Path, required=True)
    c.add_argument("--at", type=float, nargs=2, default=(0.910, 0.057),
                   help="where on the plate the number goes, as fractions")
    c.add_argument("--corner", type=Path, default=Path("../../input/pencil_corner.png"))
    c.add_argument("--ref", type=Path, default=Path("../../input/pencil_ref.png"))
    c.set_defaults(func=cut)

    l = sub.add_parser("lift", help="pull the mark out of what came back, as RGBA")
    l.add_argument("--before", type=Path, required=True)
    l.add_argument("--after", type=Path, required=True)
    l.add_argument("--out", type=Path, required=True)
    l.add_argument("--floor", type=float, default=6.0,
                   help="levels of darkening below which a change is the "
                        "codec, not the pencil")
    l.add_argument("--gain", type=float, default=90.0,
                   help="levels of darkening that count as fully opaque")
    l.set_defaults(func=lift)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
