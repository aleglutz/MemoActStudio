"""The blank sheet, taken off the act instead of invented (SPEC 5.2a).

    python tools/paper_plate.py \
        --scan projects/legends_of_surrender/sources/images/GIoS_Wehrmacht_Signed_Ru.jpg \
        --out ../../input/plate_mask.png

`render_page.py` builds its paper out of value noise, and the constants in it
were fitted to this same scan -- `PAPER` is within four levels of the blank
margin, `GRAIN` and `SWELL` were read off `S12_ru_page_move.mp4`. Fitted noise
is still noise: it has the right statistics and none of the sheet's history.
The punch holes, the crease down the left third, the darkening at the trimmed
edge and the way the tone drifts from one corner to the other are not a
distribution, they are one particular sheet that sat in one particular file.

So the plate is the act's own paper with the act taken off it: this tool writes
the mask, `docs/workflows/paper_plate_api.json` hands mask and scan to big-lama
and brings the result up to 4x on Remacri, and `render_page.py --paper` types on
what comes back.

**The mask is thin on purpose.** LaMa reconstructs a hole from its rim, and a
typed line is two hundred small holes with paper between them -- it fills those
almost perfectly. Give it a block covering a whole paragraph and it has nothing
to reconstruct from and will smear. So this marks strokes, not regions, and the
growth that a stroke needs to lose its halo is left to the node's own
`gaussblur_radius`, which dilates before it thresholds.

**What is not masked is the point.** Foxing, the punch holes, the trimmed edge
and the scanner's vignette all read darker than paper and all of them stay:
they are the difference between a sheet from an archive and a sheet of paper.
Hence `--keep-border`, which fences off the band where the holes and the edge
live, and a threshold set to catch a ribbon strike rather than a rust speck.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.page import BLUE, INK, ink_mask  # noqa: E402

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ink", type=float, default=INK,
                    help="levels below the local paper tone that count as ink")
    ap.add_argument("--blue", type=float, default=BLUE,
                    help="blue-over-red rise that counts as a pen")
    ap.add_argument("--grow", type=int, default=3,
                    help="px the mask is dilated here; the node dilates further")
    ap.add_argument("--preview", type=Path, default=None,
                    help="also write a stand-in plate, filled by diffusion of "
                         "the surrounding tone rather than by big-lama. Good "
                         "enough to check a layout and to fall back on if LaMa "
                         "will not fit; it reconstructs tone, not paper.")
    ap.add_argument("--keep-border", type=float, default=0.02,
                    help="rim at the top, right and foot that is never masked, "
                         "so the trimmed "
                         "edge and the scanner's vignette live. Thin: on this "
                         "scan the typing runs to within 4%% of the right edge, "
                         "and a rim wide enough to be comfortable keeps a "
                         "column of half-letters on the plate")
    ap.add_argument("--keep-left", type=str, default="0.03,0.12",
                    help="band down the binding edge that is never masked, as "
                         "from,to. The punch holes live in it and read darker "
                         "than any ribbon strike, so a threshold cannot tell "
                         "them from a letter. It starts inboard of the edge on "
                         "purpose: outside 3%% this scan is not paper at all "
                         "but the scanner's backing and a strip of yellow "
                         "fringing, and the one thing to do with those is let "
                         "LaMa put paper there. Masking them is also what keeps "
                         "the plate at the scan\'s own 1:1.3763 -- trimming "
                         "them off would change the ratio of the sheet")
    args = ap.parse_args()

    rgb = np.asarray(Image.open(args.scan).convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    lo, _, hi = args.keep_left.partition(",")
    im = ink_mask(rgb, ink=args.ink, blue=args.blue, grow=args.grow,
                  border=args.keep_border,
                  left=(float(lo), float(hi)) if hi else (0.0, 0.0))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    im.save(args.out)
    cov = np.asarray(im).mean() / 255
    print(f"wrote {args.out}  {w}x{h}  mask covers {cov * 100:.2f}% of the sheet")
    if cov > 0.12:
        print("  WARNING over 12% masked -- LaMa reconstructs from the rim and "
              "will smear a hole this size. Raise --ink.")
    if cov < 0.01:
        print("  WARNING under 1% masked -- typing will survive into the plate. "
              "Lower --ink.")
    print(f"  plate at 4x will be {w * 4}x{h * 4}  (ratio 1:{h / w:.4f})")

    if args.preview:
        _preview(rgb, np.asarray(im, dtype=np.float32) / 255.0, args.preview)
    return 0


def _preview(rgb: np.ndarray, mask: np.ndarray, out: Path) -> None:
    """The plate without the model: every hole filled with the tone around it.

    A weighted blur of the kept pixels, divided by the same blur of the keep
    mask, is the tone the paper would have had there -- it is what LaMa would
    settle to if it had no idea what paper looks like. Which is the limit of it:
    the fill is smooth where the sheet is not, so the grain is put back at the
    amplitude measured off the kept pixels, and no crease or hole crosses a
    filled region because nothing here knows those exist. Use it to check that a
    layout lands; do not ship a sheet made this way.
    """
    keep = 1.0 - mask
    src = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    num = np.stack([np.asarray(Image.fromarray(
        np.clip(rgb[:, :, c] * keep, 0, 255).astype(np.uint8))
        .filter(ImageFilter.GaussianBlur(26.0)), dtype=np.float32) for c in range(3)], 2)
    den = np.asarray(Image.fromarray((keep * 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(26.0)), dtype=np.float32) / 255.0
    fill = num / np.maximum(den, 1e-3)[:, :, None]

    lum = rgb.mean(2)
    low = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(9.0)), dtype=np.float32)
    sd = float((lum - low)[keep > 0.5].std())
    rng = np.random.default_rng(8945)
    grain = rng.normal(0.0, sd, lum.shape).astype(np.float32)[:, :, None]

    a = mask[:, :, None]
    plate = rgb * (1 - a) + (fill + grain) * a
    Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).save(out)
    print(f"  wrote stand-in plate {out}  (tone only -- not the deliverable)")


if __name__ == "__main__":
    raise SystemExit(main())
