"""A markdown file typed on a sheet of paper, rendered as a page (SPEC 5.2).

The work, with no opinion about who asks for it. `tools/render_page.py` is the
command line over this module and `nodes/page.py` is the graph over it, and
they are a parser and a set of widgets respectively -- neither owns a line of
what follows. That split is the pack's own rule (`__init__`: "the nodes are
widgets and reporting; the work is `memoacts_core`"), and it is here for the
reason given there: the tool and the node used to be two implementations of one
sequence, and two implementations of one sequence drift.

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

import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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

#: What the act's own number is actually made of, which is not that. Over the
#: 815 pixels of `GIoS_Wehrmacht_Signed_Ru_p1.jpg` where blue runs more than 18
#: levels over red -- the mark and nothing else on that sheet -- the mean is
#: (147,171,180) and the darkest quarter (122,148,160): a pale blue copying
#: pencil, not a violet one. `PENCIL` above is a different mark on a different
#: sheet; this is the one to match a lifted layer against.
ACT_PENCIL = (122, 148, 160)

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
#: How far a letter sits off its line, and how far a line sits off square.
#: Measured by `tools/measure_type.py`, not chosen -- which is the whole of the
#: correction here, because these two were the last constants on the sheet
#: fitted by eye and both came out small. Over the twenty clean lines of
#: `GIoS_Wehrmacht_Signed_Ru_p1.jpg`, counting only letters within a tenth of
#: the cap height so that a descender is not read as a low strike:
#:
#:     baseline scatter    0.48 px on a 13.25 px advance  =  0.036 advance, sd
#:     line skew           1.34 px per 1000               =  0.077 deg
#:
#: A uniform's sd is its half-range over root three, so 0.036 asks for 0.063
#: and the sheet had 0.045. The skew is the same arithmetic across a line: a
#: median |slope| of 0.00134 over ninety cells is 0.12 advance of rise, and the
#: median of a uniform's magnitude is half its half-range, so 0.24.
#:
#: Sideways is *not* measured and is left alone. The method reads the left edge
#: of the ink, which carries the glyph's own side bearing -- on this machine an
#: "I" and a "Ш" start at different places in the same cell -- so what it
#: returns there is the alphabet, not the escapement.
BOUNCE = 0.063              # a letter off its baseline, as a fraction of advance
WOBBLE = 0.24               # and the whole line off square, across its length

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


def plate(path: Path, w: int, h: int) -> tuple[np.ndarray, np.ndarray, None]:
    """A sheet photographed instead of generated, and the grain that is on it.

    `paper()` above was fitted to the act and reaches the right statistics: the
    tone is within four levels, the grain within half a level, the swell and the
    ripple within a tenth. What it cannot reach is the sheet's history. Punch
    holes, the crease down the left third, the darkening where the page was
    trimmed, the drift from one corner to the other -- none of those are a
    distribution to be matched, they are one sheet that sat in one file, and a
    lifetime of value noise will not produce them. `paper_plate.py` and
    `docs/workflows/paper_plate_api.json` take the act's own paper off the act;
    this reads what comes back.

    **The plate returns no height field, and that is the whole of it.** A scan
    is already lit: the swell and the ripple in it are shading the scanner's own
    lamp put there, baked into the pixels. `raked()` on top of that lights a lit
    sheet twice, and the second light does not agree with the first -- the page
    comes out quilted, which is the exact fault an invented sheet has. So `z` is
    None here and `main` skips the raking. Everything the light was for is
    already in the plate.

    The fibre field is the plate's own: what ink is about to sit in, and what
    breaks a pencil stroke. Local variation over a 9 px blur, normalised to the
    0..1 that `_noise` returns, so the thinning in `Typist` and the pencil core
    take the real grain and read against the real paper without a constant
    anywhere needing to change.
    """
    im = Image.open(path).convert("RGB")
    if im.size != (w, h):
        print(f"  NOTE plate is {im.size[0]}x{im.size[1]} and the sheet is "
              f"{w}x{h} -- resampling, which costs the plate its grain. Set the "
              f"page directive to the plate instead.")
        im = im.resize((w, h), Image.Resampling.LANCZOS)
    sheet = np.asarray(im, dtype=np.float32)
    return sheet, fibre_of(sheet), None


#: What `fit` may be. "strict" is the default because the sizes agreeing is
#: usually a fact about the pipeline rather than a coincidence, and a silent
#: rescale hides the one thing worth knowing: the reel holds this sheet at
#: s = 1.0, so a sheet half the width is a camera that sees twice as much of it.
FITS = ("strict", "scale layout to plate")


def fit_to_plate(cfg: dict, w: int, h: int, mode: str = "strict") -> tuple[dict, str | None]:
    """Reconcile the page directive with the plate that actually arrived.

    Under "strict" a mismatch is an error, and the message says where the two
    numbers come from, because the cause is almost always one dropdown: the
    plate is a scan times the upscaler's factor, so loading a different scan
    silently moves the sheet.

    Under "scale layout to plate" the *layout* is scaled and the plate is not.
    That distinction is the whole point -- resampling the plate would cost it
    the grain that is the only reason to have a plate, whereas type set at a
    different advance is just type set at a different advance. The aspect ratio
    still has to match: a sheet is a sheet, and stretching one is not a fit.
    """
    W, H = cfg["page"]
    if (w, h) == (W, H):
        return cfg, None
    if mode == "strict":
        raise ValueError(
            f"plate is {w}x{h} and the page directive says {W}x{H}.\n"
            f"  The plate is whatever scan you loaded times the upscaler's "
            f"factor, so the usual cause is the wrong scan: at 4x, "
            f"{w // 4}x{h // 4} in gives {w}x{h} out, and the directive wants "
            f"{W // 4}x{H // 4} in.\n"
            f"  Either load that scan, set the directive to {w}x{h}, or set "
            f"fit to 'scale layout to plate' and let the type follow the sheet.")
    if abs(h / w - H / W) > 0.01 * H / W:
        raise ValueError(
            f"plate is {w}x{h} (1:{h / w:.4f}) and the page is {W}x{H} "
            f"(1:{H / W:.4f}). Scaling the layout can follow a sheet of a "
            f"different size but not one of a different shape -- that would be "
            f"a stretch, and the sheet would stop being the act's.")

    k = w / W
    cfg = dict(cfg, page=(w, h),
               type=(cfg["type"][0] * k, cfg["type"][1] * k),
               margin=(round(cfg["margin"][0] * k), round(cfg["margin"][1] * k)))
    if cfg["pencil"]:
        text, at, height = cfg["pencil"]
        cfg["pencil"] = (text, at, height * k)
    return cfg, (
        f"layout scaled by {k:.3f} to a {w}x{h} plate: advance "
        f"{cfg['type'][0]:.1f}, pitch {cfg['type'][1]:.1f}, margin "
        f"{cfg['margin'][0]},{cfg['margin'][1]}. The sheet still reads the "
        f"same, but the reel holds it at s = 1.0, so a {OUT_W} px frame now "
        f"covers {OUT_W / w * 100:.0f}% of its width instead of "
        f"{OUT_W / W * 100:.0f}% -- check the anchors before trusting a move.")


def fibre_of(sheet: np.ndarray) -> np.ndarray:
    """The plate's own grain, on the 0..1 that `_noise` returns.

    Local variation over a 9 px blur, divided by its own spread rather than by
    a constant: a plate that came off a cleaner scan is not a smoother sheet,
    it is the same sheet measured with less noise, and normalising by the
    measurement keeps the ink thinning by the same amount either way.
    """
    lum = sheet.mean(2)
    low = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.GaussianBlur(9.0)), dtype=np.float32)
    d = lum - low
    return np.clip(0.5 + d / (5.0 * (float(d.std()) or 1.0)), 0.0, 1.0)


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
        wobble = self.rng.uniform(-WOBBLE, WOBBLE) * advance   # the line sits askew
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
                           - tile // 3 + self.rng.uniform(-BOUNCE, BOUNCE) * advance))
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
    """The sheet as a file. See `parse_text` -- this only reads it."""
    return parse_text(path.read_text(encoding="utf-8"))


def parse_text(text: str) -> tuple[dict, list[tuple[str, str, float]]]:
    """-> settings, and (kind, text, scale) per line. Directives never print."""
    cfg: dict = {"page": (9000, 6360), "type": (68.0, 116.0),
                 "margin": (500, 560), "pencil": None}
    lines: list[tuple[str, str, float]] = []
    pending: tuple[str, float] | None = None
    in_comment = False
    for raw in text.splitlines():
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
            raise ValueError(f"unknown directive {word!r}")
    return cfg, lines


#: Coverage below this is the lift's own noise rather than a stroke.
MARK_ON = 38

#: How little pigment a piece may carry, against the heaviest piece, and still
#: be part of the number. A digit is dense; a streak the model left at the edge
#: of its frame is long, thin and weighs a fraction of one. Set above the worst
#: streak seen rather than as low as possible: the cost of being too generous
#: is the whole number scaled to fit the streak, and the cost of being too mean
#: is one detached fragment of a broken stroke going missing.
MARK_KEEP = 0.20

#: How far from the heaviest piece a piece may sit and still belong to the same
#: number, in multiples of that piece's diagonal. The digits of a two-figure
#: number touch; anything the model did in another part of the crop does not.
MARK_REACH = 2.0


def mark_box(alpha: np.ndarray) -> tuple[tuple[int, int, int, int] | None, np.ndarray]:
    """-> the box round the number, and an alpha with everything else cleared.

    A model asked to write in a corner also touches the paper elsewhere: a
    faint streak down one side, a smudge where its frame ended. Those come back
    through the lift as pigment, and a box drawn round *everything* is taller
    than the digits -- so the digits, scaled to fill that box, come out at half
    the size asked for, and at a different size on every run, because what the
    model leaves behind changes with the seed.

    So the coverage is split into connected pieces and each is weighed by the
    pigment it actually carries. The heaviest is the number; a piece is kept
    only if it carries a real share of that weight AND sits within reach of it.
    Both tests are needed: weight alone keeps a heavy smudge in the far corner,
    reach alone keeps a long faint streak lying right beside the digits.
    """
    from scipy import ndimage

    on = alpha > MARK_ON
    if not on.any():
        return None, alpha
    lab, n = ndimage.label(on)
    a = alpha.astype(np.float32)
    mass = ndimage.sum(a, lab, index=range(1, n + 1))
    heaviest = int(np.argmax(mass)) + 1

    ys, xs = np.where(lab == heaviest)
    cy0, cx0 = ys.mean(), xs.mean()
    reach = MARK_REACH * float(np.hypot(np.ptp(ys) + 1, np.ptp(xs) + 1))
    centres = ndimage.center_of_mass(a, lab, index=range(1, n + 1))

    keep = np.zeros(n + 1, bool)
    for i in range(1, n + 1):
        near = np.hypot(centres[i - 1][0] - cy0, centres[i - 1][1] - cx0) <= reach
        keep[i] = near and mass[i - 1] >= MARK_KEEP * mass[heaviest - 1]
    dropped = int(n - keep[1:].sum())
    if dropped:
        print(f"  lay_pencil: {dropped} of {n} pieces were not the number")

    kept = np.where(keep[lab], alpha, 0).astype(np.uint8)
    ys, xs = np.where(kept > MARK_ON)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), kept


def lay_pencil(out: np.ndarray, layer: Image.Image, cx: float, cy: float,
               height: float) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Composite a lifted pencil mark onto the sheet, centred and to size.

    The layer arrives as pigment plus an alpha, with the paper already unmixed
    out of it in `pencil_layer.lift`, so this is an ordinary over -- and that is
    the reason for going the long way round rather than pasting the model's
    crop back. Pasted, the mark would bring the model's paper with it and sit in
    a rectangle of it; composited, it sits on this sheet's own grain, and the
    breaks in the stroke show the fibre underneath rather than a memory of some
    other fibre.

    Scaled to the directive's `size` by the *mark's* height, not the layer's:
    the layer is a 1024 crop with a number somewhere in it, and where in it is
    the model's business, not the page's. Which is the mark and which is the
    model having touched the paper elsewhere is `mark_box`'s problem.
    """
    layer = layer.convert("RGBA")
    alpha = np.asarray(layer.getchannel("A"), dtype=np.uint8)
    box, kept = mark_box(alpha)
    if box is None:
        print("  WARNING the pencil layer carries no mark; the sheet goes "
              "out unnumbered")
        return out, (int(cx), int(cy), int(cx), int(cy))
    layer.putalpha(Image.fromarray(kept))
    layer = layer.crop(box)
    k = height / layer.height
    layer = layer.resize((max(1, round(layer.width * k)),
                          max(1, round(layer.height * k))), Image.Resampling.LANCZOS)

    H, W = out.shape[:2]
    x, y = int(round(cx - layer.width / 2)), int(round(cy - layer.height / 2))
    x, y = min(max(x, 0), W - layer.width), min(max(y, 0), H - layer.height)
    a = np.asarray(layer, dtype=np.float32)
    rgb, alpha = a[:, :, :3], a[:, :, 3:4] / 255.0
    patch = out[y:y + layer.height, x:x + layer.width]
    out[y:y + layer.height, x:x + layer.width] = patch * (1 - alpha) + rgb * alpha
    return out, (x, y, x + layer.width, y + layer.height)




# --------------------------------------------------------------------------
# the sheet, start to finish


def render(cfg: dict, lines: list, *, face: Path = FONT, seed: int = 8945,
           plate_rgb: np.ndarray | None = None,
           pencil_rgba: Image.Image | None = None,
           fit: str = "strict", warn=print) -> tuple[np.ndarray, dict]:
    """Type `lines` onto a sheet and return it, with where everything landed.

    -> (H x W x 3 float32 in 0..255, {"placed", "pencil_box", "mask"}).

    `plate_rgb` is a photographed sheet at exactly the page size; without one
    the paper is generated. The order is the order of the physical thing and
    is not free to change: paper, then type into it, then the pencil on top of
    the type -- the number in the corner was written after the document was
    typed, and on the act it crosses a letter -- then the light, which lights
    the sheet's shape and nothing that was written on it.
    """
    W, H = cfg["page"]
    advance, pitch = cfg["type"]
    mx, my = cfg["margin"]
    rng, nrng = random.Random(seed), np.random.default_rng(seed)

    if plate_rgb is not None:
        cfg, note = fit_to_plate(cfg, plate_rgb.shape[1], plate_rgb.shape[0], fit)
        if note:
            warn(note)
        W, H = cfg["page"]
        advance, pitch = cfg["type"]
        mx, my = cfg["margin"]
        sheet, fibre, z = plate_rgb.astype(np.float32), fibre_of(plate_rgb), None
    else:
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
                warn(f"line runs off the sheet: {text[:44]!r}")
            placed.append((text, x, adv, typist.line(text, x, y, adv)))
        y += pitch * scale
    if y > H - my * 0.5:
        warn(f"the text runs {int(y - H)} px past the foot of the sheet")

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
    if cfg["pencil"] and pencil_rgba is not None:
        _, (px, py), height = cfg["pencil"]
        out, pencil_box = lay_pencil(out, pencil_rgba, px * W, py * H, height)
    elif cfg["pencil"]:
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

    # A photographed sheet arrives lit -- the swell and the ripple in it are the
    # scanner's own lamp, baked into the pixels. Raking it again lights it twice
    # with two lights that do not agree, and the page comes out quilted.
    if z is not None:
        out *= raked(z)[:, :, None]
    return np.clip(out, 0, 255), {"placed": placed, "pencil_box": pencil_box,
                                  "mask": typist.mask}


def anchor(want: str, info: dict, W: int, H: int) -> str:
    """Where the camera sits to hold `want`, as a `render_move.py --key`.

    s = 1.0 throughout: one page pixel per frame pixel, so nothing is resampled
    anywhere. It aims at the *ink*, not at the cells the escapement advanced
    through -- the two differ by a side bearing at every edge, and by a whole
    cell when the phrase ends in a space, which is enough to push a numeral off
    a 1080 px frame.
    """
    if want == "pencil":
        box = info["pencil_box"]
        if box is None:
            return f"anchor {want!r}: the sheet carries no pencil mark"
    else:
        hit = next((p for p in info["placed"] if want in p[0]), None)
        if hit is None:
            return f"anchor {want!r}: not on the sheet"
        text, x, adv, box = hit
        i = text.index(want)                  # centre the substring, not its line
        box = (int(x + i * adv), box[1], int(x + (i + len(want)) * adv), box[3])
        box = _struck(info["mask"], box) or box
    fx, fy = (box[0] + box[2]) / 2 / W, (box[1] + box[3]) / 2 / H
    cx = 0.5 + (0.5 - fx) * W / OUT_W
    cy = 0.5 + (0.5 - fy) * H / OUT_H
    return (f"anchor {want!r:22} page {fx:.4f},{fy:.4f}  "
            f"width {box[2] - box[0]:5} px  ->  --key t:{cx:.3f},{cy:.3f},1.00")


# --------------------------------------------------------------------------
# the plate: what on a scan is not paper


#: Levels below the local paper tone at which something stops being paper. A
#: worn strike on this scan sits 40-70 levels down, foxing 8-20. Between them,
#: and nearer the foxing, because a missed letter leaves a ghost and a kept
#: speck is just an old sheet.
INK = 26

#: Ink is *colder* than this paper: the sheet is warm by ~35 levels of red over
#: blue, and every signature on the act is blue-black or violet, so blue minus
#: red rises where a pen went. Typescript is neutral and comes in on `INK`
#: alone; this catches the pen, which is grey enough in places to slip under it.
#: The cast is measured off the sheet rather than assumed -- a scan of the same
#: document at a different sitting is warm by a different amount. Read against
#: that median, JPEG chroma noise alone reaches 6, which is why this is 18: a
#: threshold under it marks a tenth of the sheet and none of it is ink.
BLUE = 18

#: The paper tone is local, not global -- this sheet is 30 levels darker at the
#: trimmed edge than at the centre, and a global threshold takes the edge as
#: ink. Read at 1/24 of the sheet, which is coarse enough that no letter
#: survives into it and fine enough to follow the vignette.
FIELD = 24


def paper_field(lum: np.ndarray, scale: int = FIELD) -> np.ndarray:
    """What the paper would read at each point if nothing were written there.

    A maximum, not a mean: paper is the brightest thing on the sheet, so the
    high end of a neighbourhood is the paper in it, and a mean would be dragged
    down wherever the typing is dense and would then read that block as clean.
    """
    h, w = lum.shape
    small = Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8)).resize(
        (max(2, w // scale), max(2, h // scale)), Image.Resampling.BOX)
    small = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.6))
    return np.asarray(small.resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32)


def ink_mask(rgb: np.ndarray, ink: float = INK, blue: float = BLUE,
             grow: int = 3, border: float = 0.02,
             left: tuple[float, float] = (0.03, 0.12)) -> Image.Image:
    """White where the scan is not paper, black where it is.

    Thin on purpose. LaMa reconstructs a hole from its rim, and a typed line is
    two hundred small holes with paper between them -- it fills those almost
    perfectly. Give it a block covering a whole paragraph and it has nothing to
    reconstruct from and will smear. So this marks strokes, not regions.

    What is *not* marked is the point. Foxing, the punch holes, the trimmed
    edge and the scanner's vignette all read darker than paper and all of them
    stay: they are the difference between a sheet from an archive and a sheet
    of paper. `left` fences the binding edge where the holes are, and starts
    inboard of the sheet on purpose -- outside it the scan is not paper at all
    but the scanner's backing, and the one thing to do with that is let LaMa
    put paper there, which also keeps the plate at the scan's own ratio.
    """
    h, w, _ = rgb.shape
    lum = rgb.mean(2)
    dark = paper_field(lum) - lum
    cold = rgb[:, :, 2] - rgb[:, :, 0]
    cold = cold - float(np.median(cold))              # the sheet's own warm cast
    mask = (dark > ink) | ((cold > blue) & (dark > ink * 0.45))

    keep = np.zeros((h, w), bool)
    if border > 0:
        bx, by = int(w * border), int(h * border)
        keep[:by, :] = keep[h - by:, :] = keep[:, w - bx:] = True
    if left and left[1] > left[0]:
        keep[:, int(w * left[0]):int(w * left[1])] = True
    mask &= ~keep

    im = Image.fromarray((mask * 255).astype(np.uint8))
    return im.filter(ImageFilter.MaxFilter(grow * 2 + 1)) if grow > 0 else im

# --------------------------------------------------------------------------
# the archivist's hand, grafted: shape from the model, pencil from the sheet
def _disk(r: int) -> np.ndarray:
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def pigment_alpha(rgb: np.ndarray) -> np.ndarray:
    """-> 0..1 coverage of blue-grey pigment on warm paper.

    Blue over red, because the sheet is warm by some thirty levels and a
    copying pencil is not. Scaled by its own peak so a faint scan and a strong
    one measure the same.
    """
    a = np.clip(rgb[:, :, 2] - rgb[:, :, 0], 0, None)
    peak = np.percentile(a, 99.5)
    return np.clip(a / peak, 0, 1) if peak > 1 else a * 0


def _grain_window(ref_a: np.ndarray, side: int = 0) -> np.ndarray | None:
    """A square of pure pigment, cut where the reference stroke is thickest.

    Every pixel in it has to be inside the stroke: a window that clips the edge
    tiles the stroke's own outline into the middle of the grafted number, and
    that reads as a pattern rather than as a lead.
    """
    from scipy import ndimage

    dist = ndimage.distance_transform_edt(ref_a > 0.3)
    if dist.max() < 3:
        return None
    cy, cx = np.unravel_index(int(np.argmax(dist)), dist.shape)
    r = side // 2 or max(2, int(dist.max() * 0.7))
    win = ref_a[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
    return win if win.size > 16 and win.min() > 0.05 else None


def graft_pencil(shape_rgb: np.ndarray, shape_alpha: np.ndarray,
                 ref_rgb: np.ndarray, *, stroke: float = 0.0,
                 grain: float = 1.0, seed: int = 8945, tone: float = 0.5
                 ) -> tuple[np.ndarray, np.ndarray, str]:
    """-> (pigment RGB, alpha, report). Model's shape, reference's pencil."""
    from scipy import ndimage

    rng = np.random.default_rng(seed)
    a = np.clip(shape_alpha.astype(np.float32), 0, 1)
    if a.max() <= 0:
        return shape_rgb, shape_alpha, "no mark to graft"

    # 1. A stencil. The threshold is low on purpose: striation along a stroke
    #    is modulation, not holes, and a low cut fills it back in.
    solid = a > 0.22

    # 2. The stroke's own width, as twice its distance transform's median on
    #    the skeleton-ish core -- measured rather than guessed, because it is
    #    what every radius below is stated in.
    dist = ndimage.distance_transform_edt(solid)
    core = dist > dist.max() * 0.4
    half = float(np.median(dist[core])) if core.any() else max(dist.max(), 1.0)

    # 3. Frayed ends are spikes thinner than the stroke. An opening with a disk
    #    of about a third of the half-width takes them and leaves the stroke.
    r = max(1, int(round(half * 0.34)))
    clean = ndimage.binary_opening(solid, _disk(r))
    if clean.sum() < solid.sum() * 0.25:        # the stroke was thinner than r
        clean = solid
    clean = ndimage.binary_closing(clean, _disk(max(1, r // 2)))

    # 4. Width, to order. Negative thins, positive fattens; 0 leaves it be.
    if stroke:
        k = _disk(max(1, int(round(abs(stroke)))))
        clean = (ndimage.binary_erosion(clean, k) if stroke < 0
                 else ndimage.binary_dilation(clean, k))

    soft = np.asarray(Image.fromarray((clean * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(max(0.6, half * 0.18))),
                      dtype=np.float32) / 255.0

    # 5. The grain, tiled off the reference mark at its OWN scale. Resizing the
    #    whole reference to fit stretches one soft blob across the number and
    #    reads as a bleach stain; and tiling the reference's bounding box drags
    #    its blank paper in and punches holes. So the window is cut from the
    #    thickest part of the reference stroke, where every pixel is pigment,
    #    and repeated. What that carries is the break of a real lead over real
    #    fibre, which is the one thing no prompt has been able to ask for.
    ref_a = pigment_alpha(ref_rgb)
    win = _grain_window(ref_a)
    if win is None:
        tex = np.ones_like(soft)
        grain_note = "no grain: the reference has no stroke thick enough"
    else:
        reps = (soft.shape[0] // win.shape[0] + 2, soft.shape[1] // win.shape[1] + 2)
        tex = np.tile(win, reps)
        tex = np.roll(tex, (int(rng.integers(win.shape[0])),
                            int(rng.integers(win.shape[1]))), (0, 1))
        tex = tex[:soft.shape[0], :soft.shape[1]] / max(win.mean(), 1e-3)
        grain_note = f"grain from a {win.shape[1]}x{win.shape[0]} window of the reference"
    tex = np.clip(tex, 0.35, 1.45)
    out_a = np.clip(soft * (1 - grain + grain * tex), 0, 1)

    # 6. Colour, off the reference's darkest pigment rather than its mean: the
    #    mean folds in every half-covered edge pixel and comes out pale.
    # A pencil is a range, not a colour, and which part of the range is taken
    # decides whether the graft reads as the same lead or a heavier one. The
    # darkest fifth -- the first thing tried here -- came out too dark for the
    # mark it was measured from, so the band is a widget.
    ink = ref_rgb[ref_a > 0.55].reshape(-1, 3)
    if len(ink) > 50:
        order = np.argsort(ink.sum(1))
        lo = int(np.clip(tone, 0, 1) * (len(order) - 1))
        band = order[max(0, lo - len(order) // 10):lo + max(25, len(order) // 10)]
        colour = ink[band].mean(0)
    else:
        colour = np.array([122., 148., 160.])
    out_rgb = np.broadcast_to(colour, shape_rgb.shape).astype(np.float32).copy()

    report = "\n".join([
        f"stroke half-width {half:.1f} px, ends opened at r={r}",
        f"coverage {100 * (out_a > 0.2).mean():.2f}% "
        f"(the model's own was {100 * (a > 0.2).mean():.2f}%)",
        grain_note,
        f"pigment {colour.round(0)} taken off the reference at tone {tone:.2f}"])
    return out_rgb, out_a, report
