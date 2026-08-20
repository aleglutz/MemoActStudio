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
    <!-- type 64/110 -->        character advance / line pitch
    <!-- margin 500,560 -->     left and top, in pixels
    <!-- center -->             the next line is centred
    <!-- display 3.9 -->        the next line is centred at 3.9x the advance
    <!-- pencil 67 at 0.90,0.16 size 470 -->

The face is Special Elite (`--font` overrides it), drawn from typed impressions
rather than from outlines, so the edge of a letter is where the ribbon hit the
paper. Apache 2.0, and the licence travels with it in `assets/fonts/`.

Two type sizes on one sheet is a decision, not an oversight. The camera runs at
`s = 1.0` -- one page pixel per frame pixel, the only scale at which nothing is
resampled and the paper keeps its grain -- and at that scale a frame is 1080 px
of the sheet. A wordmark of fifteen character cells fits that frame only at an
advance of about 64 px; two numerals and the comma between them fill it at
250, and no wider, or the first of them is cut off the left edge. One sheet
cannot serve both beats in one size, and the camera cannot zoom, because the
model is a sheet on a bed and paper does not swell. So the enumeration is set
in display type, as an enumeration on a form would be.

**The sheet is not flat, and the type is not clean.** Both were fitted to the
act itself rather than imagined -- `S12_ru_page_move.mp4` is the real document
at this same magnification, and it settles two things an invented paper always
gets wrong. Archive paper photographs *smooth*: no fibre, no stipple, only the
swell of the sheet and the ripple inside it, lying in horizontal bands, all of
it within about two levels of grey. And a struck letter has no clean edge: it
carries a halo, its weight wanders by the region rather than by the letter, and
the ribbon skips, so parts of a stroke are simply missing.

The light in `raked` is applied last and lights the sheet's own shape. Nothing
written on the page is in the height field: a key does dent paper, but the dent
does not survive being photographed, and drawn in anyway it reads as an emboss
filter -- which is exactly how an earlier pass of this tool looked.

The pencil is a third layer for the same reason it is on the real act: the
number in the corner was not typed with the document, it was written on it
afterwards by whoever filed it. It is drawn from stroke paths rather than a
font because no open-licensed hand exists in `assets/fonts/`, and because what
reads as indelible pencil is the break of the stroke over the paper's fibre,
which a font cannot give at any size.

`--anchor` prints, for each thing named, where it sits on the sheet *and* the
`render_move.py` key that centres it. The framing of a shot is never measured
off the finished image by eye -- `render_map.py` prints its `focus` triple for
the same reason. It aims at the *ink*, not at the cells the escapement advanced
through: the two differ by a side bearing at every edge, and by a whole cell
when the phrase ends in a space, which is enough to push a numeral off a 1080 px
frame.
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

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT = FONTS / "SpecialElite-Regular.ttf"

OUT_W, OUT_H = 1080, 1920


def metrics(path: Path) -> tuple[float, float]:
    """-> em per advance, cap height in em. Measured off the face, not assumed.

    A typewriter is monospaced, so one advance sets every cell. Special Elite is
    drawn from typed impressions rather than from a grid and its glyphs differ
    by a fifth; set on the widest of them, it spaces exactly as the escapement
    did -- a narrow letter sits in a wide cell, which is what a typed sheet
    looks like. A truly monospaced face is unaffected, the widest being all of
    them.
    """
    face = ImageFont.truetype(str(path), 1000)
    advance = max(face.getlength(c) for c in "MW08m")
    cap = face.getbbox("H")
    return 1000 / advance, (cap[3] - cap[1]) / 1000

#: Sampled from the margins of `GIoS_Wehrmacht_Signed_Ru.jpg` -- 243-247 red,
#: 234-238 green, 208-211 blue, warm by 35 levels of red over blue. The same
#: paper the map plates were drawn from (`render_map.PALETTES["paper"]`), taken
#: from the scan rather than chosen, so that a page and a plate in one reel are
#: the same sheet.
PAPER = (246, 237, 212)

#: Measured off `S12_ru_page_move.mp4`, which is the real act at this same
#: magnification, on three blank patches of margin. Split by feature size, the
#: scan varies by (levels of grey, standard deviation):
#:
#:     coarser than 56 px   2.3 - 2.6      the swell of the sheet
#:     12 to 56 px          1.8 - 2.4      the ripple inside it
#:     finer than 12 px     2.1 - 3.1      scanner grain, and that is all
#:
#: Which is the whole lesson: archive paper photographs *smooth*. It has no
#: visible fibre and no stipple — an earlier pass gave this sheet a grain of 9
#: and it read as plaster. The mid band also runs 1.2 to 1.5 times steeper down
#: the frame than across it, so the ripple lies in horizontal bands.
GRAIN = 5.5


#: Typescript, from the same scan: a fresh strike, and a worn ribbon.
INK_FRESH = (58, 44, 38)
INK_WORN = (124, 98, 86)

#: Indelible pencil -- the violet of an archivist's mark, and the wet halo it
#: leaves where the pigment dissolves. The act's own pencilled "10" is this
#: colour.
PENCIL = (60, 54, 106)
PENCIL_WET = (116, 100, 156)

#: The sheet's own shape, in arbitrary depth units and in *pixels* -- the sizes
#: are absolute, not fractions of the sheet, because they were read off a frame
#: of the act and the camera holds this page at the same 1:1. Both waves are one
#: pass of value noise; the amplitudes were fitted to the three figures above
#: rather than chosen, and a run that comes out at (2.1, 1.8, 2.1) is the sheet
#: agreeing with the scan.
SWELL = 1.50         # the slow rise and fall of a sheet that has been damp
SWELL_PX = 220
RIPPLE = 0.62        # the shorter wave inside a swell
RIPPLE_PX = 34
BAND = 1.6           # how far both are drawn out across the sheet
CREASES = 22         # micro-creases over a 9000x6360 sheet
CREASE_Z = 0.70      # and how far each lifts the paper
STAIN = 0.017        # ageing at frame scale, as a fraction of the paper's tone
STAIN_PX = 190
LIGHT = 3            # px the light is sampled across -- a low, raking sun
GLARE = 0.62         # how hard it rakes
FOXING = 34          # rust specks over a 9000x6360 sheet; 1945 paper has them

#: The type is not printed, it is *struck through a ribbon onto a soft surface*
#: and then photographed. Nothing about that edge is crisp: in the scan a letter
#: carries a halo a couple of pixels wide, and its weight wanders — inside one
#: word some letters are near black and others are grey and broken, in patches
#: rather than letter by letter. These are the range of that wander.
#: The halo and the skips are in *pixels*, not in fractions of the type size:
#: ink spreading into paper is a distance, and so is a gap in a ribbon. Scaled
#: with the type instead, a display numeral comes out fogged and the same
#: numeral in body type comes out clean, which is backwards.
WEAR_INK = (0.60, 1.05)     # strike weight across the sheet, worn to fresh
WEAR_BLUR = (3.2, 1.2)      # and the halo it spreads into, in px
SKIP_PX = 10                # how coarsely the ribbon skips

DIRECTIVE = re.compile(r"^\s*<!--\s*(.*?)\s*-->\s*$")


# --------------------------------------------------------------------------
# paper


def _noise(w: int, h: int, cell: float, rng: np.random.Generator,
           band: float = 1.0) -> np.ndarray:
    """Value noise at a given feature size, in 0..1.

    `band` draws the features out across the sheet: at 3.4 a patch is three
    times wider than it is tall, which is how the ripple lies on the act.
    """
    sw = max(2, int(w / (cell * band)))
    sh = max(2, int(h / cell))
    small = rng.random((sh, sw), dtype=np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8)).resize(
        (w, h), Image.Resampling.BICUBIC)
    return np.asarray(im, dtype=np.float32) / 255.0


def paper(w: int, h: int,
          rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The sheet, the fibre field that ink and pencil sit in, and its depth.

    The grain is generated at the scale of the *scanner*, not of the page: the
    act scans are 1860 px across and this sheet is five times that, so grain at
    one pixel would be finer than anything the reel has ever shown and would
    read as digital rather than as paper. It is made coarse and upsampled.

    Nothing here is lit. The light comes last, in `raked`, so that what the eye
    reads as paper is the *sheet's own* shape -- and only that. Type is not in
    the height field: a typewriter does dent the page, but a dent that small
    disappears in a scan of it, and drawn in it reads as an emboss effect.
    """
    base = np.array(PAPER, dtype=np.float32)
    fibre = _noise(w, h, 2.6, rng)                       # scanner grain
    blotch = _noise(w, h, w / 12, rng, BAND)             # ageing, in patches
    streak = _noise(w, h, w / 3, rng, BAND)
    # And ageing at the scale of a frame rather than of the sheet. This is what
    # carries the coarse band of the measurement, not the shape of the paper:
    # a raking light is a difference, so by construction it says almost nothing
    # about a wave 200 px across. What varies there is the *stain*.
    stain = _noise(w, h, STAIN_PX, rng, BAND)

    tone = 1.0 - 0.045 * (blotch - 0.5) * 2 - 0.02 * (streak - 0.5) * 2
    tone -= STAIN * (stain - 0.5) * 2
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum(np.minimum(xs, w - 1 - xs) / (w * 0.14),
                      np.minimum(ys, h - 1 - ys) / (h * 0.14))
    tone *= 0.955 + 0.045 * np.clip(edge, 0, 1)          # the edges are handled

    sheet = base[None, None, :] * tone[:, :, None]
    sheet += (fibre[:, :, None] - 0.5) * (2 * GRAIN)
    _foxing(sheet, rng)

    # Depth: a swell, the ripple inside it, and the small creases a sheet picks
    # up from being handled. Both waves are drawn out sideways, because on the
    # act they run in horizontal bands -- the sheet was rolled or stacked, not
    # crumpled. Nothing here is finer than a few dozen pixels; paper that has
    # been photographed has no texture at grain scale, only shape.
    z = SWELL * (_noise(w, h, SWELL_PX, rng, BAND) - 0.5)
    # Two ripples rather than one: a single pass of value noise upsampled from
    # its grid keeps the grid, and a quilted lattice is not what paper does.
    z += 0.62 * RIPPLE * (_noise(w, h, RIPPLE_PX, rng, BAND) - 0.5)
    z += 0.48 * RIPPLE * (_noise(w, h, RIPPLE_PX * 1.6, rng, BAND * 0.9) - 0.5)
    z += _creases(w, h, rng)
    return np.clip(sheet, 0, 255), fibre, z


def _creases(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    """The short creases a handled sheet carries, as depth.

    Not the fold of a sheet put in an envelope -- the act has none of those. It
    has a couple of dozen short lifts, most of them running with the bands and
    none of them crossing the page. Drawn small and enlarged, so a crease is
    soft at the scale the camera sees it: paper creases into a lifted ridge, not
    into a scratch.
    """
    sw, sh = max(8, w // 4), max(8, h // 4)
    small = Image.new("L", (sw, sh), 128)
    draw = ImageDraw.Draw(small)
    for _ in range(max(3, round(CREASES * w * h / (9000 * 6360)))):
        x, y = rng.integers(0, sw), rng.integers(0, sh)
        length = float(rng.uniform(sw / 22, sw / 5))
        # Mostly along the bands, and never far off them.
        angle = math.radians(float(rng.normal(0.0, 14.0)) + (180 if rng.random() < 0.5 else 0))
        lift = int(rng.integers(24, 62)) * (1 if rng.random() < 0.7 else -1)
        draw.line([(x, y), (x + length * math.cos(angle), y + length * math.sin(angle))],
                  fill=128 + lift, width=int(rng.integers(1, 4)))
    small = small.filter(ImageFilter.GaussianBlur(2.2))
    grown = small.resize((w, h), Image.Resampling.BICUBIC)
    return CREASE_Z * (np.asarray(grown, dtype=np.float32) / 255.0 - 0.5) * 2


def _foxing(sheet: np.ndarray, rng: np.random.Generator) -> None:
    """Rust specks, in place. Iron in the pulp oxidises; every archive sheet in
    `images/` has them, and a page without any is a page printed yesterday."""
    h, w, _ = sheet.shape
    for _ in range(max(3, round(FOXING * w * h / (9000 * 6360)))):
        r = int(rng.integers(7, 26))          # px, and so px of frame at s = 1
        cx, cy = int(rng.integers(r, w - r)), int(rng.integers(r, h - r))
        ys, xs = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
        d = np.sqrt(xs * xs + ys * ys) / r
        spot = np.clip(1.0 - d, 0, 1) ** 2 * float(rng.uniform(0.06, 0.20))
        patch = sheet[cy - r:cy + r + 1, cx - r:cx + r + 1]
        # Foxing is warm: it takes the blue out of the page before the red.
        patch *= 1.0 - spot[:, :, None] * np.array([0.35, 0.62, 1.0], np.float32)


def raked(z: np.ndarray) -> np.ndarray:
    """Shading from a light held low over the sheet, coming from the top left.

    A normal map and a dot product would be the textbook way. For a surface this
    shallow the difference of the height field along the light's own direction
    is the same thing, and costs one temporary array rather than three -- which
    at 9000x6360 is the difference between rendering and swapping.
    """
    slope = z - np.roll(np.roll(z, LIGHT, 0), LIGHT, 1)
    return np.clip(1.0 + GLARE * slope, 0.45, 1.7)


# --------------------------------------------------------------------------
# the typing


class Typist:
    """Strikes characters into an ink mask, one glyph at a time.

    A line of text set in one call is a line of text; a typewriter is a line of
    single strikes, each landing a little off the last. That jitter is what the
    eye reads as typed, and it costs one paste per character.
    """

    def __init__(self, w: int, h: int, rng: random.Random, face: Path = FONT,
                 wear: np.ndarray | None = None):
        self.mask = Image.new("L", (w, h), 0)
        self.size = (w, h)
        self.rng = rng
        self.nrng = np.random.default_rng(rng.randrange(2 ** 32))
        self.wear = wear
        self.face = face
        self.em_per_advance, self.cap_per_em = metrics(face)
        self._fonts: dict[int, ImageFont.FreeTypeFont] = {}

    def worn(self, x: float, y: float) -> float:
        """How tired the ribbon is over this part of the sheet, 0 to 1.

        A ribbon does not wear letter by letter, it wears in passes: on the act
        whole regions come out grey and soft while a neighbouring line is nearly
        black. So the wander is sampled from a field, not rolled per glyph.
        """
        if self.wear is None:
            return 1.0
        h, w = self.wear.shape
        i = min(max(int(y / self.size[1] * h), 0), h - 1)
        j = min(max(int(x / self.size[0] * w), 0), w - 1)
        return float(self.wear[i, j])

    def font(self, advance: float) -> ImageFont.FreeTypeFont:
        size = max(6, int(round(advance * self.em_per_advance)))
        if size not in self._fonts:
            self._fonts[size] = ImageFont.truetype(str(self.face), size)
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
            worn = self.worn(x + i * advance, y)
            # A weak strike is a key hit softly, not a lighter typeface: same
            # glyph, less ink. Roughly every sixth, which is what a hand does.
            # Biased towards a full strike: on the act most letters are near
            # black and a minority are grey, not the other way about.
            weight = WEAR_INK[0] + (WEAR_INK[1] - WEAR_INK[0]) * worn ** 0.55
            weight *= self.rng.uniform(0.86, 1.10)
            if self.rng.random() < 0.13:
                weight *= self.rng.uniform(0.55, 0.85)
            ink = int(255 * min(weight, 1.0))
            glyph = Image.new("L", (tile, tile), 0)
            ImageDraw.Draw(glyph).text((tile // 3, tile // 3), ch, font=font, fill=ink)
            glyph = glyph.rotate(self.rng.uniform(-0.9, 0.9),
                                 Image.Resampling.BICUBIC, center=(tile / 2, tile / 2))
            glyph = self.press(glyph, advance, worn)
            px = int(round(x + i * advance - tile // 3
                           + self.rng.uniform(-0.035, 0.035) * advance))
            py = int(round(y + wobble * (i / max(len(text) - 1, 1))
                           - tile // 3 + self.rng.uniform(-0.045, 0.045) * advance))
            region = self.mask.crop((px, py, px + tile, py + tile))
            self.mask.paste(Image.fromarray(np.maximum(np.asarray(region),
                                                       np.asarray(glyph))), (px, py))
        cap = self.cap_per_em * advance * self.em_per_advance
        return (int(x), int(y), int(x + len(text) * advance), int(y + cap))

    def press(self, glyph: Image.Image, advance: float, worn: float) -> Image.Image:
        """One character as the paper received it, and the scanner returned it.

        Two things happen to a struck letter and neither leaves a clean edge.
        The ribbon lays ink into a soft surface, which spreads it — a halo of a
        couple of pixels at the scale the camera holds this sheet, wider where
        the ribbon is tired. And the ribbon *skips*: on the act whole parts of a
        stroke simply are not there. A vector outline gives neither, which is
        why an unretouched glyph reads as set rather than as typed.
        """
        blur = WEAR_BLUR[0] + (WEAR_BLUR[1] - WEAR_BLUR[0]) * worn
        glyph = glyph.filter(ImageFilter.GaussianBlur(blur * self.rng.uniform(0.8, 1.35)))
        if self.rng.random() < 0.5 + 0.35 * (1 - worn):
            # A gap in a stroke is the same size on a display numeral as in
            # body type. Sized off the glyph instead, it turned the numerals
            # into lace.
            n = max(2, glyph.size[0] // SKIP_PX)
            skip = Image.fromarray(
                (self.nrng.random((n, n), dtype=np.float32) * 255).astype(np.uint8)
            ).resize(glyph.size, Image.Resampling.BICUBIC)
            thin = np.clip(0.55 + 0.85 * np.asarray(skip, np.float32) / 255.0, 0, 1)
            glyph = Image.fromarray(
                (np.asarray(glyph, np.float32) * thin).astype(np.uint8))
        # The halo cost the strike some of its weight; a struck letter keeps it.
        return glyph.point(lambda v: min(255, int(v * 1.18)))


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


def _struck(mask: Image.Image,
            box: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    """Tighten a box of cells onto the ink actually inside it.

    A cell is what the escapement advanced. The ink is what the eye centres on,
    and the two differ by a side bearing at every edge -- by a whole cell when
    the phrase ends in a space, which is enough to push a numeral against the
    edge of a 1080 px frame. Aim the camera at the ink.
    """
    pad = int((box[3] - box[1]) * 0.6)                   # commas hang below
    win = (box[0], max(box[1] - pad, 0), box[2], box[3] + pad)
    hit = mask.crop(win).getbbox()
    if hit is None:
        return None
    return (win[0] + hit[0], win[1] + hit[1], win[0] + hit[2], win[1] + hit[3])


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
    ap.add_argument("--font", type=Path, default=FONT,
                    help=f"a face in {FONTS}, or a path to one")
    ap.add_argument("--seed", type=int, default=8945)
    args = ap.parse_args()
    face = args.font if args.font.exists() else FONTS / args.font.name

    cfg, lines = parse_page(args.page)
    W, H = cfg["page"]
    advance, pitch = cfg["type"]
    mx, my = cfg["margin"]
    rng, nrng = random.Random(args.seed), np.random.default_rng(args.seed)

    sheet, fibre, z = paper(W, H, nrng)
    # Where the ribbon is tired. Coarse and drawn out sideways, like everything
    # else on this sheet: a typist works across the page, so wear arrives in
    # passes rather than in spots.
    typist = Typist(W, H, rng, face, wear=_noise(96, 72, 7.0, nrng, BAND))

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

    # Ink. Every glyph already carries its own halo and its own skips, laid on
    # in `Typist.press`; what is left to do here is let the paper's own texture
    # thin a strike where the surface took less of it, and pick the colour --
    # a fresh strike is near black, a tired one browner.
    ink = np.asarray(typist.mask, dtype=np.float32) / 255.0
    ink = np.clip(ink * (0.88 + 0.24 * fibre), 0, 1)
    worn = _noise(W, H, W / 6, nrng, BAND)[:, :, None] * 0.55
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

    # The light, last of all, and it lights the *sheet* -- its swell, its
    # ripple, its creases. Nothing that was written on the page is in the height
    # field: a key does dent paper, but the dent is far too shallow to survive
    # being photographed, and drawn in anyway it reads as an emboss filter.
    out *= raked(z)[:, :, None]

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
            box = _struck(typist.mask, box) or box
        fx, fy = (box[0] + box[2]) / 2 / W, (box[1] + box[3]) / 2 / H
        cx = 0.5 + (0.5 - fx) * W / OUT_W
        cy = 0.5 + (0.5 - fy) * H / OUT_H
        print(f"  anchor {want!r:22} page {fx:.4f},{fy:.4f}  "
              f"width {box[2] - box[0]:5} px  ->  --key t:{cx:.3f},{cy:.3f},1.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
