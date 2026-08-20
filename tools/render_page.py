"""A markdown file typed on a sheet of paper, rendered as a page (SPEC 5.2).

    python tools/render_page.py \
        --page projects/legends_of_surrender/hook_page.md \
        --out projects/legends_of_surrender/composites/hook_page.png \
        --anchor "M E M O A C T S" --anchor "8, 9" --anchor pencil

The reel already has a shot in which a document moves under a static camera
(`REBUILD.md`, "The act, read"). What it does not have is a *document of our
own* to move that way, and a scan cannot be edited into one. So the sheet is
typed here: the source is a markdown file that stays in git, the PNG is an
output like every map plate, and `render_move.py` handles it exactly as it
handles the act.

**The file is typed verbatim.** No markdown is parsed and nothing is styled
away: `**Status:**` reaches the paper as eleven struck characters, because the
joke and the texture both depend on the sheet being the working document rather
than a rendering of it. At this magnification the syntax is what the eye reads.

Layout that a typewriter cannot express is carried in HTML comments, which are
invisible in any markdown reader and so leave the file readable as a file:

    <!-- page 9000x6360 -->     the sheet, in pixels
    <!-- type 68/116 -->        character advance / line pitch
    <!-- margin 500,560 -->     left and top, in pixels
    <!-- center -->             the next line is centred
    <!-- display 3.5 -->        the next line is centred at 3.5x the advance
    <!-- pencil 67 at 0.90,0.11 size 430 -->

Two type sizes on one sheet is a decision, not an oversight. The camera runs at
`s = 1.0` -- one page pixel per frame pixel, the only scale at which nothing is
resampled and the paper keeps its grain -- and at that scale a frame is 1080 px
of the sheet. A wordmark of fifteen character cells fits that frame only at an
advance of about 68 px; a pair of numerals fills it only at about 240. One
sheet cannot serve both beats in one size, and the camera cannot zoom, because
the model is a sheet on a bed and paper does not swell. So the enumeration is
set in display type, as an enumeration on a form would be.

The pencil is a third layer for the same reason it is on the real act: the
number in the corner was not typed with the document, it was written on it
afterwards by whoever filed it. It is drawn from stroke paths rather than a
font because no open-licensed hand exists in `assets/fonts/`, and because what
reads as indelible pencil is the break of the stroke over the paper's fibre,
which a font cannot give at any size.

`--anchor` prints, for each thing named, where it sits on the sheet *and* the
`render_move.py` key that centres it. The framing of a shot is never measured
off the finished image by eye -- `render_map.py` prints its `focus` triple for
the same reason.
"""
from __future__ import annotations

import argparse
import math
import random
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FONT = (Path(__file__).resolve().parents[1] / "assets" / "fonts"
        / "ShareTechMono-Regular.ttf")

OUT_W, OUT_H = 1080, 1920

#: Share Tech Mono, measured rather than assumed: the advance is 0.54 em and
#: the cap height 0.70 em, so an advance of 68 px is a 126 px face.
EM_PER_ADVANCE = 1 / 0.54
CAP_PER_EM = 0.70

#: Sampled from the margins of `GIoS_Wehrmacht_Signed_Ru.jpg` -- 246/238/213
#: with a grain of about seven levels. The same paper the map plates were drawn
#: from (`render_map.PALETTES["paper"]`), taken from the scan rather than
#: chosen, so that a page and a plate in one reel are the same sheet.
PAPER = (246, 237, 212)
GRAIN = 7.0

#: Typescript, from the same scan: a fresh strike, and a worn ribbon.
INK_FRESH = (58, 44, 38)
INK_WORN = (124, 98, 86)

#: Indelible pencil -- the violet of an archivist's mark, and the wet halo it
#: leaves where the pigment dissolves. The act's own pencilled "10" is this
#: colour.
PENCIL = (60, 54, 106)
PENCIL_WET = (116, 100, 156)

DIRECTIVE = re.compile(r"^\s*<!--\s*(.*?)\s*-->\s*$")


# --------------------------------------------------------------------------
# paper


def _noise(w: int, h: int, cell: float, rng: np.random.Generator) -> np.ndarray:
    """Value noise at a given feature size, in 0..1."""
    sw, sh = max(2, int(w / cell)), max(2, int(h / cell))
    small = rng.random((sh, sw), dtype=np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(
        (w, h), Image.Resampling.BICUBIC)
    return np.asarray(im, dtype=np.float32) / 255.0


def paper(w: int, h: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """The sheet, and the fibre field that ink and pencil both sit in.

    The grain is generated at the scale of the *scanner*, not of the page: the
    act scans are 1860 px across and this sheet is five times that, so grain at
    one pixel would be finer than anything the reel has ever shown and would
    read as digital rather than as paper. It is made coarse and upsampled.
    """
    base = np.array(PAPER, dtype=np.float32)
    fibre = _noise(w, h, 2.6, rng)                       # the grain itself
    blotch = _noise(w, h, w / 12, rng)                   # ageing, in patches
    streak = _noise(w, h, w / 3, rng)

    tone = 1.0 - 0.045 * (blotch - 0.5) * 2 - 0.02 * (streak - 0.5) * 2
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs) / (w * 0.14),
                      np.minimum(ys, h - 1 - ys) / (h * 0.14))
    tone *= 0.955 + 0.045 * np.clip(edge, 0, 1)          # the edges are handled

    sheet = base[None, None, :] * tone[:, :, None]
    sheet += (fibre[:, :, None] - 0.5) * (2 * GRAIN)
    return np.clip(sheet, 0, 255), fibre


# --------------------------------------------------------------------------
# the typing


class Typist:
    """Strikes characters into an ink mask, one glyph at a time.

    A line of text set in one call is a line of text; a typewriter is a line of
    single strikes, each landing a little off the last. That jitter is what the
    eye reads as typed, and it costs one paste per character.
    """

    def __init__(self, w: int, h: int, rng: random.Random):
        self.mask = Image.new("L", (w, h), 0)
        self.rng = rng
        self._fonts: dict[int, ImageFont.FreeTypeFont] = {}

    def font(self, advance: float) -> ImageFont.FreeTypeFont:
        size = max(6, int(round(advance * EM_PER_ADVANCE)))
        if size not in self._fonts:
            self._fonts[size] = ImageFont.truetype(str(FONT), size)
        return self._fonts[size]

    def line(self, text: str, x: float, y: float,
             advance: float) -> tuple[int, int, int, int]:
        """Type `text` with its first cell's left edge at `x`, cap top at `y`."""
        font = self.font(advance)
        tile = int(advance * 3)
        wobble = self.rng.uniform(-0.06, 0.06) * advance   # the line sits askew
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            # A weak strike is a key hit softly, not a lighter typeface: same
            # glyph, less ink. Roughly every fifth, which is what a hand does.
            ink = 255 if self.rng.random() > 0.18 else self.rng.randint(120, 190)
            glyph = Image.new("L", (tile, tile), 0)
            ImageDraw.Draw(glyph).text((tile // 3, tile // 3), ch, font=font, fill=ink)
            glyph = glyph.rotate(self.rng.uniform(-0.9, 0.9),
                                 Image.Resampling.BICUBIC, center=(tile / 2, tile / 2))
            px = int(round(x + i * advance - tile // 3
                           + self.rng.uniform(-0.035, 0.035) * advance))
            py = int(round(y + wobble * (i / max(len(text) - 1, 1))
                           - tile // 3 + self.rng.uniform(-0.045, 0.045) * advance))
            region = self.mask.crop((px, py, px + tile, py + tile))
            self.mask.paste(Image.fromarray(np.maximum(np.asarray(region),
                                                       np.asarray(glyph))), (px, py))
        cap = CAP_PER_EM * advance * EM_PER_ADVANCE
        return (int(x), int(y), int(x + len(text) * advance), int(y + cap))


# --------------------------------------------------------------------------
# the pencil


def _bez(p0, p1, p2, n=26):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (i / (n - 1) for i in range(n))]


def _arc(cx, cy, rx, ry, a0, a1, n=34):
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in (a0 + (a1 - a0) * i / (n - 1) for i in range(n))]


#: Numerals as a hand writes them, in a unit box with y running down. The seven
#: is crossed: the mark on a Soviet act was made by a Soviet hand.
DIGITS: dict[str, list[list[tuple[float, float]]]] = {
    "0": [_arc(0.34, 0.50, 0.30, 0.48, -100, 262)],
    "1": [[(0.08, 0.24), (0.36, 0.03)], [(0.36, 0.03), (0.31, 0.98)]],
    "2": [_bez((0.04, 0.22), (0.30, -0.10), (0.62, 0.26)),
          [(0.62, 0.26), (0.05, 0.94)], [(0.05, 0.94), (0.66, 0.88)]],
    "3": [_arc(0.30, 0.26, 0.28, 0.24, -170, 80),
          _arc(0.28, 0.72, 0.32, 0.27, -95, 165)],
    "4": [[(0.54, 0.03), (0.03, 0.69)], [(0.03, 0.69), (0.66, 0.63)],
          [(0.57, 0.30), (0.47, 0.98)]],
    "5": [[(0.62, 0.05), (0.15, 0.08)], [(0.15, 0.08), (0.09, 0.45)],
          _arc(0.34, 0.68, 0.30, 0.30, -105, 150)],
    "6": [_bez((0.68, 0.02), (0.16, 0.16), (0.08, 0.62)),
          _arc(0.36, 0.68, 0.30, 0.30, 175, 535)],
    "7": [[(0.03, 0.11), (0.68, 0.05)], [(0.68, 0.05), (0.28, 0.98)],
          [(0.14, 0.56), (0.54, 0.50)]],
    "8": [_arc(0.34, 0.26, 0.24, 0.24, -90, 272),
          _arc(0.32, 0.74, 0.29, 0.26, -95, 268)],
    "9": [_arc(0.36, 0.28, 0.28, 0.26, -80, 282), [(0.64, 0.26), (0.38, 0.98)]],
}
DIGIT_ADVANCE = 0.78


def pencil_mark(mask: Image.Image, text: str, cx: float, cy: float, height: float,
                rng: random.Random, tilt: float = -5.0) -> tuple[int, int, int, int]:
    """Write `text` centred on (cx, cy), `height` px tall, into an alpha mask.

    The stroke is walked at one pixel and stamped, because a pencil is a width
    that varies with pressure and a line that thins where the hand speeds up.
    Every stroke is written twice, slightly apart: nobody presses once.
    """
    draw = ImageDraw.Draw(mask)
    width = max(3.0, height * 0.030)
    slant, rot = math.radians(9.0), math.radians(tilt)
    span = DIGIT_ADVANCE * height * len(text)
    x0, y0 = cx - span / 2, cy - height / 2

    def place(u: float, v: float, i: int) -> tuple[float, float]:
        px, py = (u + i * DIGIT_ADVANCE) * height, v * height
        px -= (py - height / 2) * math.tan(slant)          # the hand leans right
        dx, dy = px - span / 2, py - height / 2
        return (x0 + span / 2 + dx * math.cos(rot) - dy * math.sin(rot),
                y0 + height / 2 + dx * math.sin(rot) + dy * math.cos(rot))

    for i, ch in enumerate(text):
        for stroke in DIGITS.get(ch, []):
            pts = [place(u, v, i) for u, v in stroke]
            length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) or 1.0
            for pas in range(2):
                jx = rng.uniform(-1, 1) * width * 0.30
                jy = rng.uniform(-1, 1) * width * 0.30
                pressure = rng.uniform(0.85, 1.05)
                walked = 0.0
                for a, b in zip(pts, pts[1:]):
                    steps = max(2, int(math.dist(a, b)))
                    for k in range(steps):
                        t = k / steps
                        x = a[0] + (b[0] - a[0]) * t + jx
                        y = a[1] + (b[1] - a[1]) * t + jy
                        # A stroke is heaviest where the hand sets the pencil
                        # down and lightest where it lifts away. Constant width
                        # is the one thing that reads as a marker, not a pencil.
                        taper = 1.20 - 0.45 * (walked + t * math.dist(a, b)) / length
                        r = (width * pressure * taper * rng.uniform(0.82, 1.18)
                             * (1.0 if pas == 0 else 0.72))
                        v = int(255 * rng.uniform(0.55, 1.0) * (1.0 if pas == 0 else 0.5))
                        draw.ellipse((x - r, y - r, x + r, y + r), fill=v)
                    walked += math.dist(a, b)
    return int(x0), int(y0), int(x0 + span), int(y0 + height)


# --------------------------------------------------------------------------


def parse_page(path: Path) -> tuple[dict, list[tuple[str, str, float]]]:
    """-> settings, and (kind, text, scale) per line. Directives never print."""
    cfg: dict = {"page": (9000, 6360), "type": (68.0, 116.0),
                 "margin": (500, 560), "pencil": None}
    lines: list[tuple[str, str, float]] = []
    pending: tuple[str, float] | None = None
    in_comment = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        # A comment spanning several lines is a note to whoever edits the sheet
        # and never reaches the paper. Only the one-line form is a directive.
        if in_comment:
            in_comment = "-->" not in raw
            continue
        if raw.lstrip().startswith("<!--") and "-->" not in raw:
            in_comment = True
            continue
        m = DIRECTIVE.match(raw)
        if not m:
            kind, scale = pending or ("plain", 1.0)
            lines.append((kind, raw, scale))
            pending = None
            continue
        word, _, rest = m.group(1).partition(" ")
        rest = rest.strip()
        if word == "page":
            w, h = rest.lower().split("x")
            cfg["page"] = (int(w), int(h))
        elif word == "type":
            a, _, pitch = rest.partition("/")
            cfg["type"] = (float(a), float(pitch))
        elif word == "margin":
            x, y = rest.split(",")
            cfg["margin"] = (int(x), int(y))
        elif word == "center":
            pending = ("center", 1.0)
        elif word == "display":
            pending = ("center", float(rest))
        elif word == "pencil":
            t = rest.split()                      # "67 at 0.90,0.11 size 430"
            cfg["pencil"] = (t[0], tuple(float(v) for v in t[2].split(",")), float(t[4]))
        else:
            raise SystemExit(f"{path}: unknown directive {word!r}")
    return cfg, lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--anchor", action="append", default=[],
                    help="text to locate on the sheet (or 'pencil'); prints the "
                         "render_move.py key that centres it. Repeatable")
    ap.add_argument("--seed", type=int, default=8945)
    args = ap.parse_args()

    cfg, lines = parse_page(args.page)
    W, H = cfg["page"]
    advance, pitch = cfg["type"]
    mx, my = cfg["margin"]
    rng, nrng = random.Random(args.seed), np.random.default_rng(args.seed)

    sheet, fibre = paper(W, H, nrng)
    typist = Typist(W, H, rng)

    y = float(my)
    placed: list[tuple[str, float, float, tuple[int, int, int, int]]] = []
    for kind, text, scale in lines:
        adv = advance * scale
        if text.strip():
            width = len(text) * adv
            x = (W - width) / 2 if kind == "center" else float(mx)
            if x < 0 or x + width > W:
                print(f"  WARNING line runs off the sheet: {text[:44]!r}")
            placed.append((text, x, adv, typist.line(text, x, y, adv)))
        y += pitch * scale
    if y > H - my * 0.5:
        print(f"  WARNING the text runs {int(y - H)} px past the foot of the sheet")

    # Ink: struck, then let into the paper. The blur is the fibre drinking it,
    # and the fibre field itself thins a strike where the surface is rough.
    ink = np.asarray(typist.mask.filter(ImageFilter.GaussianBlur(advance * 0.012)),
                     dtype=np.float32) / 255.0
    ink = np.clip(np.clip(ink * 1.18, 0, 1) * (0.78 + 0.34 * fibre), 0, 1)
    worn = _noise(W, H, W / 6, nrng)[:, :, None] * 0.55
    colour = (np.array(INK_FRESH, dtype=np.float32)[None, None, :] * (1 - worn)
              + np.array(INK_WORN, dtype=np.float32)[None, None, :] * worn)
    out = sheet * (1 - ink[:, :, None]) + colour * ink[:, :, None]

    pencil_box = None
    if cfg["pencil"]:
        text, (px, py), height = cfg["pencil"]
        pmask = Image.new("L", (W, H), 0)
        pencil_box = pencil_mark(pmask, text, px * W, py * H, height, rng)
        halo = np.asarray(pmask.filter(ImageFilter.GaussianBlur(height * 0.035)),
                          dtype=np.float32) / 255.0
        core = np.asarray(pmask.filter(ImageFilter.GaussianBlur(height * 0.004)),
                          dtype=np.float32) / 255.0
        # Pencil rides the fibre and skips off it; that break is the whole
        # difference between indelible pencil and a violet outline.
        core = np.clip(np.clip(core * 1.35, 0, 1) * (0.42 + 0.72 * fibre), 0, 1)
        halo = np.clip(halo * 0.55, 0, 1)
        for layer, rgb in ((halo, PENCIL_WET), (core, PENCIL)):
            a = layer[:, :, None]
            out = out * (1 - a) + np.array(rgb, dtype=np.float32)[None, None, :] * a

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(args.out)
    print(f"wrote {args.out}  {W}x{H}")

    # Where the camera has to sit to hold each of these. s = 1.0 throughout:
    # one page pixel per frame pixel, so nothing is resampled anywhere.
    for want in args.anchor:
        if want == "pencil":
            box = pencil_box
            if box is None:
                print("  anchor 'pencil': the sheet carries no pencil mark")
                continue
        else:
            hit = next((p for p in placed if want in p[0]), None)
            if hit is None:
                print(f"  anchor {want!r}: not on the sheet")
                continue
            text, x, adv, box = hit
            i = text.index(want)                  # centre the substring, not its line
            box = (int(x + i * adv), box[1], int(x + (i + len(want)) * adv), box[3])
        fx, fy = (box[0] + box[2]) / 2 / W, (box[1] + box[3]) / 2 / H
        cx = 0.5 + (0.5 - fx) * W / OUT_W
        cy = 0.5 + (0.5 - fy) * H / OUT_H
        print(f"  anchor {want!r:22} page {fx:.4f},{fy:.4f}  "
              f"width {box[2] - box[0]:5} px  ->  --key t:{cx:.3f},{cy:.3f},1.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
