"""Recombine a generated colour frame with the archival frame it came from.

Qwen-Image-Edit, asked to colourise, does not colourise. At denoise 1.0 it
redraws: the face changes, the medals are re-invented, the film grain is gone
and the room is re-lit. What comes back is a plausible modern photograph that
has replaced the document rather than coloured it.

But its *chroma* is useful even when its luminance is a fabrication. So this
takes the two apart: the L channel comes from the archival frame, untouched, and
only the a/b channels come from the model. Not one pixel of structure moves --
every edge, every face, every grain of the film is the film's own. The model is
demoted from author to colour suggestion.

The chroma is then blurred. Colour in a photograph is low-frequency anyway, and
the model's output does not land pixel-on-pixel with the source (it moved things
while redrawing), so unblurred a/b smears colour past the edges it belongs to.
Four pixels is enough to hide the misregistration without bleeding a shoulder
board onto a collar.

Usage:
    python tools/module03_colorize.py --native <dir-or-video> \
        --generated <dir> --out <dir> [--blur 4]
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image, ImageFilter


def frames_from_video(path, into):
    """Explode a clip to PNG so its frames pair up with the generated ones."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), str(into / "%05d.png")], check=True
    )
    return sorted(into.glob("*.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True, help="source video, or a dir of frames")
    ap.add_argument("--generated", required=True, help="dir of model output frames")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blur", type=float, default=4.0, help="chroma blur radius, px")
    ap.add_argument("--offset", type=int, default=0, help="first native frame index")
    args = ap.parse_args()

    gen = sorted(pathlib.Path(args.generated).glob("*.png"))
    if not gen:
        sys.exit(f"no PNGs in {args.generated}")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        native_path = pathlib.Path(args.native)
        if native_path.is_dir():
            nat = sorted(native_path.glob("*.png"))
        else:
            nat = frames_from_video(native_path, pathlib.Path(tmp))
        nat = nat[args.offset : args.offset + len(gen)]

        if len(nat) != len(gen):
            sys.exit(f"{len(nat)} native frames against {len(gen)} generated")

        for i, (n, g) in enumerate(zip(nat, gen)):
            base = Image.open(n).convert("RGB")
            # The model returns its own size -- it rounds to its latent grid, so
            # 1068 comes back as 1064. Match the document, never the other way.
            colour = Image.open(g).convert("RGB").resize(base.size, Image.LANCZOS)
            luma = base.convert("LAB").split()[0]
            _, a, b = colour.convert("LAB").split()
            if args.blur:
                a = a.filter(ImageFilter.GaussianBlur(args.blur))
                b = b.filter(ImageFilter.GaussianBlur(args.blur))
            Image.merge("LAB", (luma, a, b)).convert("RGB").save(out / f"{i:05d}.png")

    print(f"{len(gen)} frames -> {out}")


if __name__ == "__main__":
    main()
