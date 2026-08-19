"""Recombine a generated colour frame with the archival frame it came from.

Qwen-Image-Edit, asked to colourise, does not colourise. At denoise 1.0 it
redraws: the face changes, the medals are re-invented, the film grain is gone
and the room is re-lit. What comes back is a plausible modern photograph that
has replaced the document rather than coloured it. And there is no setting in
between -- at denoise 0.6 and below the frame survives but almost no colour
arrives (see projects/module03/workflows/README.md).

So the model is demoted rather than tuned. The L channel comes from the archival
frame, untouched, and only a/b come from the generation. Not one pixel of
structure moves: every edge, every face, every grain of the film is the film's
own, and the model drops from author to colour suggestion.

The chroma still has to be conditioned, because the generation does not land
pixel-on-pixel with its source -- the model moved things while redrawing, so raw
a/b puts a shoulder board's red on the collar beside it. Two ways to do that:

    --method guided  (default)  a guided filter that makes the chroma follow the
                    *document's* luminance edges, so colour stops where the film
                    says an edge is rather than where the generation thought.
    --method blur    a plain Gaussian, which hides misregistration by smearing
                    everything. Kept because the comparison is instructive.

Guided wins clearly where the generation stayed roughly registered: on a frame
where a plain blur left a pink cast across a face and the document in his hands,
the guided version returns natural skin and white paper. It does NOT fix a
colour that landed on the wrong object -- where the model recomposed a crowd, it
simply renders the wrong colours with crisper edges. Bleeding is fixable;
misplacement is not, and that is the method's honest limit.

Usage:
    python tools/module03_colorize.py --native <dir-or-video> \
        --generated <dir> --out <dir> [--method guided|blur] [--offset N]
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import uniform_filter


def guided_filter(guide, src, radius=12, eps=1e-3):
    """He et al.'s guided filter: let `src` follow the edges of `guide`.

    Chroma is fitted to luminance as a local linear function, so a flat region
    keeps a flat colour while a real edge in the film forces the colour to break
    there too. eps sets how much luminance contrast counts as an edge worth
    respecting; 1e-3 on 0..1 data keeps film grain from being treated as one.
    """
    I = guide.astype(np.float64) / 255.0
    p = src.astype(np.float64) / 255.0
    mean_I = uniform_filter(I, radius)
    mean_p = uniform_filter(p, radius)
    cov_Ip = uniform_filter(I * p, radius) - mean_I * mean_p
    var_I = uniform_filter(I * I, radius) - mean_I * mean_I
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I
    q = uniform_filter(a, radius) * I + uniform_filter(b, radius)
    return np.clip(q * 255.0, 0, 255).astype(np.uint8)


def frames_from_video(path, into):
    """Explode a clip to PNG so its frames pair up with the generated ones."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), str(into / "%05d.png")], check=True
    )
    return sorted(into.glob("*.png"))


def recombine(base, colour, method, blur, radius):
    """Archival luminance, generated chroma, conditioned by `method`."""
    luma = base.convert("LAB").split()[0]
    _, a, b = colour.convert("LAB").split()
    if method == "guided":
        g = np.array(luma)
        a = Image.fromarray(guided_filter(g, np.array(a), radius))
        b = Image.fromarray(guided_filter(g, np.array(b), radius))
    elif blur:
        a = a.filter(ImageFilter.GaussianBlur(blur))
        b = b.filter(ImageFilter.GaussianBlur(blur))
    return Image.merge("LAB", (luma, a, b)).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", required=True, help="source video, or a dir of frames")
    ap.add_argument("--generated", required=True, help="dir of model output frames")
    ap.add_argument("--out", required=True)
    ap.add_argument("--method", choices=("guided", "blur"), default="guided")
    ap.add_argument("--blur", type=float, default=4.0, help="radius for --method blur")
    ap.add_argument("--radius", type=int, default=12, help="window for --method guided")
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
            frame = recombine(base, colour, args.method, args.blur, args.radius)
            frame.save(out / f"{i:05d}.png")

    print(f"{len(gen)} frames -> {out}  ({args.method})")


if __name__ == "__main__":
    main()
