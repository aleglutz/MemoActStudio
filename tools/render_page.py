"""A markdown file typed on a sheet of paper, rendered as a page (SPEC 5.2).

    python tools/render_page.py \
        --page projects/legends_of_surrender/sources/hook_page_2.md \
        --out projects/legends_of_surrender/sources/composites/hook_page.png \
        --paper output/plate/act_paper_00001_.png \
        --pencil-png .../composites/pencil_67.png \
        --anchor "M E M O A C T S" --anchor pencil

The command line over `memoacts_core.page`, which is where the sheet actually
lives -- the file format, the paper, the typing, the pencil and the light are
all documented there, and `nodes_page.py` is the same module behind a graph.

What is here and nowhere else: reading the arguments, opening the two optional
images, and printing. `--anchor` prints, for each thing named, where it sits on
the sheet *and* the `render_move.py` key that centres it, because the framing
of a shot is never measured off the finished image by eye.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.page import (FITS, FONT, FONTS, anchor,  # noqa: E402
                                parse_page, render)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--anchor", action="append", default=[],
                    help="text to locate on the sheet (or 'pencil'); prints the "
                         "render_move.py key that centres it. Repeatable")
    ap.add_argument("--font", type=Path, default=FONT,
                    help=f"a face in {FONTS}, or a path to one")
    ap.add_argument("--paper", type=Path, default=None,
                    help="a scanned blank sheet to type on, at exactly the page "
                         "size. Without it the paper is generated")
    ap.add_argument("--pencil-png", type=Path, default=None,
                    help="an RGBA mark from tools/pencil_layer.py, placed at the "
                         "position and size the `pencil` directive gives. The "
                         "number in the directive is then only a label")
    ap.add_argument("--fit", default=FITS[0], choices=list(FITS),
                    help="what to do when the plate is not the size the page "
                         "directive names. Scaling moves the type, not the plate")
    ap.add_argument("--seed", type=int, default=8945)
    args = ap.parse_args()

    import numpy as np
    Image.MAX_IMAGE_PIXELS = None
    face = args.font if args.font.exists() else FONTS / args.font.name
    cfg, lines = parse_page(args.page)

    plate_rgb = None
    if args.paper:
        plate_rgb = np.asarray(Image.open(args.paper).convert("RGB"), dtype=np.float32)
    pencil = Image.open(args.pencil_png).convert("RGBA") if args.pencil_png else None

    out, info = render(cfg, lines, face=face, seed=args.seed,
                       plate_rgb=plate_rgb, pencil_rgba=pencil, fit=args.fit,
                       warn=lambda m: print(f"  {m}"))

    H, W = out.shape[:2]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out.astype(np.uint8)).save(args.out)
    print(f"wrote {args.out}  {W}x{H}")
    for want in args.anchor:
        print("  " + anchor(want, info, W, H))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
