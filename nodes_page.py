"""The sheet, as a graph — "a document of our own" (SPEC 5.2).

The reel has a shot in which a document moves under a static camera, and a scan
cannot be edited into one. So the sheet is typed: the source is a markdown file
that stays in git, and the PNG is an output like any map plate. These four
nodes put that whole sequence on the canvas:

    Load Image (the act) ─→ Paper Mask ─→ LamaRemover ─→ Upscale ─→ the plate
                                                                      │
    Page File ─→ (text) ─────────────────────────────→ Type Page ─────┤
                                                            │         │
    Image Crop ─→ Qwen edit ─→ Pencil Lift ─────────────────┘         ↓
                                                                  Save Image

The typing is not generated and will not be. Eleven hundred characters of exact
text at 7440x10240 is outside what any local model sets without inventing some
of it, and the reel needs the sheet at s = 1.0 with named anchors -- a generated
image has neither. What the model is for is the two things a renderer cannot
have: the paper's own history, which comes off the act through LaMa, and the
archivist's hand, which comes off the act's pencilled number.

Everything below is widgets and reporting. The work is `memoacts_core.page`.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import torch
from comfy_api.latest import io, ui
from PIL import Image

from .memoacts_core import page as pg

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "assets" / "fonts"

#: A page with nothing on it but the four directives, so the node explains its
#: own format on the canvas. The reel's actual sheet is a file — wire Page File.
STARTER = """<!-- page 7440x10240 -->
<!-- type 64/110 -->
<!-- margin 700,820 -->
<!-- pencil 67 at 0.910,0.057 size 392 -->

The file is typed verbatim: no markdown is parsed and nothing is styled
away, because at this magnification the syntax is what the eye reads.

<!-- center -->
M E M O A C T S
"""


def _first(image: torch.Tensor) -> np.ndarray:
    """The first frame of a batch as H x W x 3 in 0..255.

    A sheet is one image. A batch here means someone wired a loader that
    happened to return several, and typing the same page onto each of them is
    minutes of work for a result nobody asked for.
    """
    a = image[0].detach().cpu().numpy().astype(np.float32) * 255.0
    return a[:, :, :3]


def _image(arr: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.clip(arr, 0, 255).astype(np.float32) / 255.0)[None]


def _fonts() -> list[str]:
    return sorted(p.name for p in FONTS.glob("*.ttf")) or ["SpecialElite-Regular.ttf"]


class MemoActsPaperMask(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPaperMask",
            display_name="MemoActs — Paper Mask",
            category="memoacts/page",
            description="White where a scan is not paper, for big-lama to fill. "
                        "Thin on purpose: LaMa rebuilds a hole from its rim, so "
                        "a typed line (many small holes) comes back perfectly "
                        "and a masked paragraph (one big hole) smears. Feed the "
                        "output to LamaRemoverIMG with gaussblur_radius 3.",
            inputs=[
                io.Image.Input("image", tooltip="The scan to strip."),
                io.Float.Input("ink", default=pg.INK, min=4.0, max=120.0, step=1.0,
                               tooltip="Levels below the LOCAL paper tone that "
                                       "count as ink. A worn strike on the act "
                                       "sits 40-70 down, foxing 8-20; between "
                                       "them, and nearer the foxing, because a "
                                       "missed letter leaves a ghost and a kept "
                                       "speck is just an old sheet."),
                io.Float.Input("blue", default=pg.BLUE, min=0.0, max=80.0, step=1.0,
                               tooltip="Blue-over-red rise that counts as a pen. "
                                       "Under about 12 this marks JPEG chroma "
                                       "noise, which is a tenth of the sheet and "
                                       "none of it ink."),
                io.Int.Input("grow", default=3, min=0, max=20,
                             tooltip="Dilation here, in px. The LaMa node "
                                     "dilates again; past about 12 px total the "
                                     "halo of one line meets the next."),
                io.Float.Input("keep_border", default=0.02, min=0.0, max=0.2,
                               step=0.005,
                               tooltip="Rim at top, right and foot never masked, "
                                       "so the trimmed edge and the vignette "
                                       "live. Thin: on the act the typing runs "
                                       "to within 4% of the right edge."),
                io.Float.Input("keep_left_from", default=0.03, min=0.0, max=0.5,
                               step=0.005,
                               tooltip="The binding band starts inboard: outside "
                                       "it the scan is the scanner's backing, "
                                       "and letting LaMa put paper there is what "
                                       "keeps the plate at the scan's ratio."),
                io.Float.Input("keep_left_to", default=0.12, min=0.0, max=0.5,
                               step=0.005,
                               tooltip="...and ends before the text does. The "
                                       "punch holes live in this band and read "
                                       "darker than any ribbon strike."),
            ],
            outputs=[io.Image.Output(display_name="mask_image"),
                     io.Mask.Output(display_name="mask"),
                     io.String.Output(display_name="report")],
        )

    @classmethod
    def execute(cls, image, ink, blue, grow, keep_border,
                keep_left_from, keep_left_to):
        rgb = _first(image)
        m = pg.ink_mask(rgb, ink=ink, blue=blue, grow=grow, border=keep_border,
                        left=(keep_left_from, keep_left_to))
        a = np.asarray(m, dtype=np.float32) / 255.0
        cov = float(a.mean())
        h, w = a.shape
        report = (f"{w}x{h}  mask covers {cov * 100:.2f}% of the sheet\n"
                  f"plate at 4x will be {w * 4}x{h * 4}  (ratio 1:{h / w:.4f})")
        if cov > 0.18:
            report += ("\nWARNING a fifth of the sheet is masked. What matters "
                       "is the width of the widest hole rather than the total, "
                       "but at this coverage check that paragraphs have not "
                       "merged into blocks. Raise ink.")
        elif cov < 0.01:
            report += "\nWARNING under 1% masked; typing will survive. Lower ink."
        return io.NodeOutput(_image(np.dstack([a * 255] * 3)),
                             torch.from_numpy(a)[None], report,
                             ui=ui.PreviewText(report))


class MemoActsPencilLift(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPencilLift",
            display_name="MemoActs — Pencil Lift",
            category="memoacts/page",
            description="The difference between the crop that went into an edit "
                        "model and the crop that came back, as pigment plus an "
                        "alpha. Because the paper underneath is known exactly, "
                        "what the model added is recoverable exactly — and only "
                        "that travels on. A pasted patch would carry the model's "
                        "idea of this paper, which is a guess; the alpha "
                        "composites onto the sheet's own grain instead.",
            inputs=[
                io.Image.Input("before", tooltip="The crop as it was sent."),
                io.Image.Input("after", tooltip="What the model returned."),
                io.Float.Input("floor", default=6.0, min=0.0, max=64.0, step=1.0,
                               tooltip="Levels of darkening below which a change "
                                       "is the codec, not the pencil."),
                io.Float.Input("gain", default=90.0, min=8.0, max=255.0, step=1.0,
                               tooltip="Levels of darkening that count as fully "
                                       "opaque."),
            ],
            outputs=[io.Image.Output(display_name="pigment"),
                     io.Mask.Output(display_name="alpha"),
                     io.String.Output(display_name="report")],
        )

    @classmethod
    def execute(cls, before, after, floor, gain):
        b, a_ = _first(before), _first(after)
        if b.shape != a_.shape:
            a_ = np.asarray(Image.fromarray(a_.astype(np.uint8)).resize(
                (b.shape[1], b.shape[0]), Image.Resampling.LANCZOS), dtype=np.float32)
        # Pigment only darkens. A pixel the model made brighter is the model
        # rebuilding paper it had no need to touch, and it is not wanted.
        drop = np.clip(b - a_, 0, 255).max(2)
        alpha = np.clip((drop - floor) / max(gain, 1.0), 0, 1)
        # The colour is what the mark is, not what it sits on: unmix the paper
        # out of it at the alpha found above, which compositing will put back.
        rgb = np.clip(b + (a_ - b) / np.maximum(alpha, 1e-3)[:, :, None], 0, 255)

        hit = alpha > 0.15
        core = rgb[alpha > 0.5]
        report = f"mark covers {hit.mean() * 100:.2f}% of the crop"
        if core.size:
            report += (f"\npigment {core.mean(0).round(0)}  "
                       f"(the act's own core is {pg.ACT_PENCIL})")
        if hit.mean() > 0.08:
            report += ("\nWARNING over 8% changed — the model repainted the "
                       "paper as well as writing on it. Reroll, or raise floor.")
        elif hit.mean() < 0.001:
            report += "\nWARNING nothing changed; the model wrote nothing."
        return io.NodeOutput(_image(rgb), torch.from_numpy(alpha.astype(np.float32))[None],
                             report, ui=ui.PreviewText(report))


#: Where the act sets its own text block and its own number, as fractions of
#: the sheet. Measured off `GIoS_Wehrmacht_Signed_Ru_p1`, not chosen: the block
#: starts 17.6% in and 20% down, and the archivist's number sits at 0.910,
#: 0.057. They are constants because a sheet that moved them would stop being
#: the act's, which is the whole reason the plate is a scan.
MARGIN = (0.176, 0.200)
PENCIL_AT = (0.910, 0.057)

#: The directives Page File now writes for itself. Any of these already in a
#: page is stripped: they are the sheet's geometry, the plate is the sheet, and
#: two sources for one number is what kept putting a stale size into the graph.
LAYOUT = ("page", "type", "margin", "pencil")


class MemoActsPencilGraft(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPencilGraft",
            display_name="MemoActs — Pencil Graft",
            category="memoacts/page",
            description="Keeps the model's handwriting and throws away its "
                        "medium. Three rewrites of the prompt moved the ripple "
                        "through the stroke from 0.089 to 0.050 against the "
                        "act's own 0.040 and never once removed the brush — "
                        "flat wide passes, striation down the length of a "
                        "stroke, split ends. At four to six distilled steps "
                        "that is the model's prior for writing a number in "
                        "blue on paper, and a prior does not lose an argument "
                        "with a prompt. So the shape stays and the width, the "
                        "ends, the grain and the colour are taken off the "
                        "act's own pencil instead.",
            inputs=[
                io.Image.Input("mark", tooltip="Pigment from Pencil Lift."),
                io.Mask.Input("alpha", tooltip="Its alpha, from the same node."),
                io.Image.Input("reference", tooltip="A real pencil mark to take "
                                                    "the lead from. Wire Pencil "
                                                    "Crop's `reference`."),
                io.Float.Input("stroke", default=-2.0, min=-12.0, max=12.0,
                               step=0.5,
                               tooltip="Width, in px, against what the model "
                                       "drew. Negative thins. This is the hard "
                                       "guarantee against a fat number: the "
                                       "prompt could only ask, and asking for a "
                                       "narrow stroke and asking for an "
                                       "unbroken one pull against each other."),
                io.Float.Input("grain", default=1.0, min=0.0, max=1.0, step=0.05,
                               tooltip="How much of the reference's own break "
                                       "over the fibre to multiply back in. At "
                                       "0 the stroke is flat and even, which is "
                                       "a marker; at 1 it carries the lead's "
                                       "grain, which is what no prompt has been "
                                       "able to ask for."),
                io.Int.Input("seed", default=8945, min=0, max=2 ** 31 - 1,
                             tooltip="Where the grain is sampled from. Same "
                                     "seed, same mark."),
                io.Float.Input("tone", default=0.50, min=0.0, max=1.0, step=0.05,
                               tooltip="Which of the reference's own pigment to "
                                       "take the colour from: 0 its darkest, 1 "
                                       "its lightest. A pencil is not one "
                                       "colour, and sampling only the darkest "
                                       "of it comes out heavier than the mark "
                                       "it was measured from."),
            ],
            outputs=[io.Image.Output(display_name="pigment"),
                     io.Mask.Output(display_name="alpha"),
                     io.String.Output(display_name="report")],
        )

    @classmethod
    def execute(cls, mark, alpha, reference, stroke, grain, seed, tone=0.5):
        a = alpha[0].detach().cpu().numpy().astype(np.float32)
        rgb = _first(mark)
        if a.shape != rgb.shape[:2]:
            raise ValueError(f"mark is {rgb.shape[1]}x{rgb.shape[0]} and its "
                             f"alpha is {a.shape[1]}x{a.shape[0]} — wire both "
                             f"outputs of the same Pencil Lift")
        out_rgb, out_a, report = pg.graft_pencil(
            rgb, a, _first(reference), stroke=stroke, grain=grain,
            seed=seed, tone=tone)
        return io.NodeOutput(_image(out_rgb),
                             torch.from_numpy(out_a)[None], report,
                             ui=ui.PreviewText(report))


class MemoActsPageFile(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPageFile",
            display_name="MemoActs — Page File",
            category="memoacts/page",
            description="The words, and the sizes they are set at. The sheet's "
                        "geometry is not written down anywhere: it is read off "
                        "the plate, so loading a different scan moves nothing "
                        "and breaks nothing. The two sizes are fractions of "
                        "that sheet rather than pixels, for the same reason — a "
                        "number in pixels is only true for one scan. Whatever "
                        "leaves here IS the page, so Pencil Crop and Type Page "
                        "cannot come to different numbers.",
            inputs=[
                io.String.Input("path", default="projects/legends_of_surrender/"
                                                "sources/hook_page_2.md",
                                tooltip="Relative to the node pack, or absolute."),
                io.Image.Input("plate", optional=True,
                               tooltip="The sheet, for its size. Wire the same "
                                       "plate that goes to Type Page. Without "
                                       "one the page falls back to a default "
                                       "and the report says so."),
                io.String.Input("text", multiline=True, default="", optional=True,
                                tooltip="Empty types the file. Type words here "
                                        "and they are typed instead. Words only "
                                        "— nothing about size belongs in this "
                                        "box or in the file any more."),
                io.Boolean.Input("save", default=False, optional=True,
                                 tooltip="Write `text` back to `path`. An edit "
                                         "worth keeping belongs in the file, in "
                                         "git, where REBUILD.md will find it."),
                io.Float.Input("type_width", default=0.0095, min=0.001, max=0.08,
                               step=0.0005, optional=True,
                               tooltip="The type, as a fraction of the sheet's "
                                       "width: one character cell. 0.0095 is "
                                       "the act's own. The report says how many "
                                       "characters a line then holds — past "
                                       "that, lines run off the paper, because "
                                       "the text is typed verbatim and nothing "
                                       "wraps it."),
                io.Float.Input("line_pitch", default=2.4, min=1.0, max=5.0,
                               step=0.05, optional=True,
                               tooltip="Line spacing, in character cells. The "
                                       "act is typed at about 2.4 — through two "
                                       "intervals, which is most of what makes "
                                       "a sheet read as machine-typed rather "
                                       "than printed."),
                io.Float.Input("pencil_height", default=0.038, min=0.0, max=0.3,
                               step=0.002, optional=True,
                               tooltip="The number in the corner, as a fraction "
                                       "of the sheet's height. Zero leaves the "
                                       "sheet unmarked. It is independent of "
                                       "the type: another hand wrote it, at "
                                       "another time, far larger."),
                io.String.Input("pencil", default="67", optional=True,
                                tooltip="What the number says. On the act it "
                                        "means nothing at all, which is why any "
                                        "number does."),
                io.Float.Input("top", default=0.200, min=0.0, max=0.6,
                               step=0.005, optional=True,
                               tooltip="Where the first line sits, as a "
                                       "fraction of the sheet's height. 0.200 "
                                       "is the act's own. Lower it to move the "
                                       "block up the page."),
            ],
            outputs=[io.String.Output(display_name="text")],
        )

    @classmethod
    def fingerprint_inputs(cls, path, plate=None, text="", save=False,
                           type_width=0.0095, line_pitch=2.4,
                           pencil_height=0.038, pencil="67", top=0.200):
        """Re-read whenever the file itself changes, not just the widgets.

        The whole reason the sheet is a file is that it is edited outside
        ComfyUI. Cached on the widgets alone the node returns the text from
        before the edit, and the graph then types a stale page.
        """
        f = Path(path)
        if not f.is_absolute():
            f = ROOT / f
        try:
            st = f.stat()
            stamp = f"{st.st_mtime_ns}|{st.st_size}"
        except OSError:
            stamp = "missing"
        return (f"{f}|{stamp}|{text}|{save}|{type_width}|{line_pitch}"
                f"|{pencil_height}|{pencil}|{top}")

    @classmethod
    def execute(cls, path, plate=None, text="", save=False, type_width=0.0095,
                line_pitch=2.4, pencil_height=0.038, pencil="67", top=0.200):
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p

        if text.strip():
            # Said loudly, because it is invisible otherwise: an edit made in
            # the file after something was left in this box never reaches the
            # sheet, and the sheet looks exactly as plausible either way.
            source, body = f"TYPED FROM THE BOX — {p.name} IS IGNORED", text
            if save:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body, encoding="utf-8")
        else:
            # `save` with an empty box does nothing. It used to raise, and that
            # was the wrong shape: the error pushed whoever hit it back into
            # filling the box, and a filled box with `save` on then wrote
            # itself over the file. Refusing to act is the safe half.
            if not p.exists():
                raise FileNotFoundError(f"no page at {p}")
            source, body = f"the file — {p.name}", p.read_text(encoding="utf-8")

        # Old geometry, wherever it came from, is dropped. It described a sheet
        # that is now measured rather than declared, and a leftover `page` line
        # from some earlier scan is exactly what kept reaching Pencil Crop.
        kept, dropped = [], []
        for raw in body.splitlines():
            m = pg.DIRECTIVE.match(raw)
            if m and m.group(1).split(" ", 1)[0] in LAYOUT:
                dropped.append(raw.strip())
            else:
                kept.append(raw)
        body = "\n".join(kept).lstrip("\n")

        if plate is not None:
            sheet = _first(plate)
            W, H = int(sheet.shape[1]), int(sheet.shape[0])
            note = f"sheet {W}x{H}, off the plate"
        else:
            W, H = 4096, 5640
            note = f"sheet {W}x{H} — NO PLATE WIRED, this is a fallback"

        advance = W * type_width
        pitch = advance * line_pitch
        head = [f"<!-- page {W}x{H} -->",
                f"<!-- type {advance:g}/{pitch:g} -->",
                f"<!-- margin {round(W * MARGIN[0])},{round(H * top)} -->"]
        if pencil_height > 0 and pencil.strip():
            head.append(f"<!-- pencil {pencil.strip()} at "
                        f"{PENCIL_AT[0]:.3f},{PENCIL_AT[1]:.3f} "
                        f"size {H * pencil_height:g} -->")
        body = "\n".join(head) + "\n" + body

        cfg, lines = pg.parse_text(body)
        # The measure Type Page checks a line against is the sheet's own edge.
        cols = int((W - cfg["margin"][0]) // advance)
        longest = max((len(t) for _, t, _ in lines), default=0)
        depth = cfg["margin"][1] + len(lines) * pitch

        report = [source, note,
                  f"{len(lines)} lines, longest {longest}",
                  f"type {advance:.1f}/{pitch:.1f} - the sheet holds {cols} a line"]
        if longest > cols:
            report.append(
                f"WARNING {longest - cols} characters past the edge. Nothing "
                f"wraps the text, so rewrap it or drop type_width to "
                f"{type_width * cols / longest:.4f}.")
        if depth > H:
            report.append(f"WARNING the text runs {depth - H:.0f} px past the foot. "
                          f"Drop line_pitch or type_width.")
        if cfg["pencil"]:
            report.append(f"pencil {cfg['pencil'][0]} at {cfg['pencil'][2]:.0f} px")
        if dropped:
            report.append(f"dropped {len(dropped)} old directive(s): "
                          + "; ".join(dropped))
        if save and text.strip():
            report.append(f"WROTE {p}")
        elif save:
            report.append("`save` is on but the box is empty, so nothing was "
                          "written. The file is intact.")
        return io.NodeOutput(body, ui=ui.PreviewText("\n".join(report)))


#: Descriptions of a hand, not of a picture. A prompt that asks for a
#: "handwritten number" gets a font; what separates a pencil from a font is the
#: medium -- how the pigment sits, where it breaks, what it does at a corner --
#: so that is what these say. The first is the act's own, measured; the others
#: are the ways the same archive marks a sheet, offered because the point of
#: putting this on a canvas is to try them.
#:
#: Every one of them names the BODY of the stroke before its edge, and that
#: order is not style. A distilled sampler -- Lightning at four to six steps,
#: which is what this graph runs -- has to commit a texture in one or two
#: denoising steps, and an early word like "broken" or "not continuous" is
#: committed as a row of thin parallel lines through the whole stroke. Measured
#: against the act's own mark, the first entry below used to run at 0.089 of
#: ripple through the stroke where the real pencil runs at 0.040; saying the
#: solid pass first and keeping the break at the margins is most of the way
#: across that gap. So: one opaque pass, then where it fails. Never the reverse,
#: and never "broken" as the first thing a stroke is.
#:
#: The other ditch is on the far side of that same road, and the first attempt
#: drove straight into it. "Broad and blunt as if from a thick soft lead",
#: "heavy where the hand bore down": every adjective that makes a stroke
#: continuous also makes it fat, and the model obliges twice over. The mark
#: then carried 19,585 pixels of pigment against the act's 11,280 inside the
#: same box, at a peak of 91 against 57 -- 1.7 times too wide and 60% too dark,
#: which reads as a brush and not a pencil.
#:
#: So: continuity is asked for in words about the stroke's PATH ("one
#: continuous pass", "unbroken"), never in words about its mass; and width and
#: weight are pinned to image2 rather than described at all. The reference is
#: right there in the conditioning, and an adjective only competes with it.
HANDS = {
    "the act's own — blue copying pencil": (
        "the same blue copying pencil and the same hand as the number in "
        "image2: a narrow stroke, no wider than a pencil lead, laid down in "
        "one continuous pass so that its core is unbroken. Match image2 "
        "exactly for width, for weight and for how dark the blue-grey pigment "
        "sits in the paper: no broader, no heavier and no darker than the "
        "number already there. It gives out only at the very ends of a stroke, "
        "where the pigment thins against the grain and leaves a little of the "
        "sheet showing. The same pressure and the same slight rightward slant"),
    "indelible pencil — violet, wet halo": (
        "indelible copying pencil pressed into damp paper: one dense pass of "
        "near-black violet, the core solid and unbroken, thickening where the "
        "hand paused, with a wet violet halo bleeding a little way into the "
        "fibre along its edges"),
    "archivist's graphite — thin, hard, dry": (
        "a hard graphite pencil on dry paper: one continuous thin grey stroke "
        "of even width, silvery where the light catches the graphite, its "
        "edges catching on the tooth of the sheet, with the small hook at the "
        "start of each stroke that a fast hand leaves"),
    "ink — a clerk's dip pen": (
        "a dip pen in blue-black iron gall ink: solid unbroken strokes that "
        "swell where the nib was pressed and go thin on the upstroke, a darker "
        "pool where the pen stopped, and a faint feathering only at the outer "
        "edge of the line where the ink met unsized paper"),
}


class MemoActsPencilCrop(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPencilCrop",
            display_name="MemoActs — Pencil Crop",
            category="memoacts/page",
            description="The two crops an edit model needs: the corner of the "
                        "plate where the number goes, and the act's own number "
                        "for the hand to copy. The corner is cut from the same "
                        "`pencil` directive that will place the mark, so the "
                        "position is stated once and cannot drift; and it is "
                        "cut from the FINISHED plate, which is what makes Pencil "
                        "Lift exact — the paper under the mark is then known.",
            inputs=[
                io.Image.Input("plate", tooltip="The blank sheet, at page size."),
                io.Image.Input("act", tooltip="A scan carrying a real archival "
                                              "number. GIoS_Wehrmacht_Signed_Ru_p1."),
                io.String.Input("text", multiline=True, default=STARTER,
                                tooltip="The page, for its pencil directive. "
                                        "Wire the same source as Type Page."),
                io.Int.Input("size", default=1024, min=256, max=2048, step=64,
                             tooltip="Qwen-Image-Edit works at about a "
                                     "megapixel. Cutting at that size means the "
                                     "mark arrives on the sheet at the size the "
                                     "model drew it, with no resampling of "
                                     "pigment — which is what turns a pencil "
                                     "stroke into a smudge."),
                io.Float.Input("ref_x", default=0.910, min=0.0, max=1.0, step=0.005,
                               tooltip="Where the act's own number is, measured: "
                                       "on p1 the pixels where blue runs 18 "
                                       "levels over red box to a centre of "
                                       "0.9097, 0.0567."),
                io.Float.Input("ref_y", default=0.057, min=0.0, max=1.0, step=0.005),
                io.Float.Input("ref_span", default=0.16, min=0.02, max=0.6, step=0.01,
                               tooltip="How much around it to take, as a "
                                       "fraction of the scan's short side."),
                io.Combo.Input("fit", options=list(pg.FITS), default=pg.FITS[0],
                               tooltip="What to do when the plate is not the "
                                       "size the page directive names. Strict "
                                       "errors and says which scan would have "
                                       "given that size. Scaling moves the "
                                       "TYPE, never the plate -- resampling the "
                                       "plate would cost the grain that is the "
                                       "only reason to have one."),
            ],
            outputs=[io.Image.Output(display_name="corner"),
                     io.Image.Output(display_name="reference"),
                     io.String.Output(display_name="report")],
        )

    @classmethod
    def execute(cls, plate, act, text, size, ref_x, ref_y, ref_span, fit):
        cfg, _ = pg.parse_text(text)
        if not cfg["pencil"]:
            raise ValueError("the page carries no `pencil` directive, so there "
                             "is nowhere to put a number. Add e.g. "
                             "<!-- pencil 67 at 0.910,0.057 size 392 -->")
        sheet = _first(plate)
        # The same reconciliation Type Page does, and it has to be the same one:
        # the corner is cut here and the mark laid back there, so if the two
        # disagreed about the size of the sheet the number would land somewhere
        # other than where the crop was taken from.
        cfg, note = pg.fit_to_plate(cfg, sheet.shape[1], sheet.shape[0], fit)
        _, (px, py), height = cfg["pencil"]
        W, H = cfg["page"]
        corner = _cut(sheet, px, py, size)

        a = _first(act)
        span = int(min(a.shape[0], a.shape[1]) * ref_span)
        ref = _cut(a, ref_x, ref_y, span)
        ref = np.asarray(Image.fromarray(ref.astype(np.uint8)).resize(
            (size, size), Image.Resampling.LANCZOS), dtype=np.float32)

        report = "\n".join(
            ([note] if note else []) +
            [f"corner {size}x{size} from the plate at {px:.3f},{py:.3f}",
             f"reference {span}px from the act at {ref_x:.3f},{ref_y:.3f}",
             f"the mark will be laid back at {height:.0f} px high"])
        return io.NodeOutput(_image(corner), _image(ref), report,
                             ui=ui.PreviewText(report))


def _cut(rgb: np.ndarray, fx: float, fy: float, size: int) -> np.ndarray:
    """A square of `size` centred on (fx, fy), kept inside the sheet."""
    h, w, _ = rgb.shape
    size = min(size, h, w)
    x = min(max(int(fx * w) - size // 2, 0), w - size)
    y = min(max(int(fy * h) - size // 2, 0), h - size)
    return rgb[y:y + size, x:x + size]


class MemoActsPencilPrompt(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsPencilPrompt",
            display_name="MemoActs — Pencil Prompt",
            category="memoacts/page",
            description="The number and the hand, as a prompt pair. Split out "
                        "so that trying a different number is typing two "
                        "characters rather than editing a paragraph — and so "
                        "that what changes between two takes is visible.",
            inputs=[
                io.String.Input("number", default="67",
                                tooltip="What to write. The reference carries a "
                                        "1 and a 0 and nothing else, so any "
                                        "other digit is the model transferring "
                                        "a manner rather than copying a shape. "
                                        "If a hand comes out wrong, a number "
                                        "the act actually has — 10, 13, 31 — "
                                        "sits in the frame the same way."),
                io.Combo.Input("hand", options=list(HANDS), default=list(HANDS)[0],
                               tooltip="What the mark is made of. The medium is "
                                       "what separates a written number from a "
                                       "typeface; ask for 'handwritten' and you "
                                       "get a font."),
                io.String.Input("extra", multiline=True, default="",
                                tooltip="Appended to the description. For one "
                                        "run's worth of an idea — 'underlined "
                                        "twice', 'circled', 'written over the "
                                        "typing'."),
                io.String.Input("negative", multiline=True,
                                default="printed digits, typeface, ballpoint, "
                                        "felt tip, clean even stroke, outline, "
                                        "drop shadow, new paper texture, "
                                        "redrawn background",
                                tooltip="What it must not be. Every entry here "
                                        "is a way a model draws a number when "
                                        "it has decided the task is typography."),
            ],
            outputs=[io.String.Output(display_name="positive"),
                     io.String.Output(display_name="negative")],
        )

    @classmethod
    def execute(cls, number, hand, extra, negative):
        text = (f"Write the number {number.strip()} on the blank paper in "
                f"image1, in {HANDS[hand]}.")
        if extra.strip():
            text += " " + extra.strip().rstrip(".") + "."
        # The last sentence is the one that keeps the lift exact: anything the
        # model repaints comes back as pigment it never laid down.
        text += (" Change nothing else: the paper, its tone, its creases and "
                 "its grain stay exactly as they are.")
        return io.NodeOutput(text, negative, ui=ui.PreviewText(text))


class MemoActsTypePage(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsTypePage",
            display_name="MemoActs — Type Page",
            category="memoacts/page",
            description="Types the text onto the sheet. The text is taken "
                        "verbatim — no markdown is parsed and nothing is styled "
                        "away, because at this magnification the syntax is what "
                        "the eye reads. Layout a typewriter cannot express "
                        "travels in HTML comments, which any markdown reader "
                        "ignores: page WxH, type advance/pitch, margin x,y, "
                        "center, display N, pencil N at x,y size H. Without a "
                        "plate the paper is generated; with one it is the act's "
                        "own, and then the raking light is skipped because a "
                        "scan arrives already lit.",
            inputs=[
                io.String.Input("text", multiline=True, default=STARTER,
                                tooltip="The sheet. Wire Page File to keep it "
                                        "in git instead."),
                io.Image.Input("plate", optional=True,
                               tooltip="A photographed blank sheet at EXACTLY "
                                       "the size the page directive gives. "
                                       "Resampling it here would cost the grain "
                                       "that is the only reason to have it, so "
                                       "a mismatch is an error, not a resize."),
                io.Image.Input("pencil", optional=True,
                               tooltip="Pigment from Pencil Lift. Placed at the "
                                       "position and size the pencil directive "
                                       "gives; the number in it is then a label."),
                io.Mask.Input("pencil_alpha", optional=True),
                io.Combo.Input("font", options=_fonts(),
                               default="SpecialElite-Regular.ttf",
                               tooltip="Special Elite is drawn from typed "
                                       "impressions rather than outlines, so the "
                                       "edge of a letter is where the ribbon hit."),
                io.Int.Input("seed", default=8945, min=0, max=2 ** 31 - 1,
                             tooltip="Fixes the paper, the ribbon's wear and "
                                     "every letter's bounce. Same seed, same "
                                     "sheet."),
                io.String.Input("anchors", multiline=True, default="",
                                tooltip="One phrase per line, or 'pencil'. For "
                                        "each, reports where it sits and the "
                                        "render_move.py --key that centres it at "
                                        "s = 1.0. Framing is never measured off "
                                        "the finished image by eye."),
                io.Combo.Input("fit", options=list(pg.FITS), default=pg.FITS[0],
                               tooltip="What to do when the plate is not the "
                                       "size the page directive names. Strict "
                                       "errors and says which scan would have "
                                       "given that size. Scaling moves the "
                                       "TYPE, never the plate -- resampling the "
                                       "plate would cost the grain that is the "
                                       "only reason to have one."),
            ],
            outputs=[io.Image.Output(display_name="page"),
                     io.String.Output(display_name="report")],
        )

    @classmethod
    def execute(cls, text, font, seed, anchors, fit, plate=None, pencil=None,
                pencil_alpha=None):
        cfg, lines = pg.parse_text(text)

        plate_rgb = _first(plate) if plate is not None else None
        mark = None
        if pencil is not None:
            rgb = _first(pencil)
            if pencil_alpha is None:
                raise ValueError("pencil needs pencil_alpha — without it there "
                                 "is no way to tell the mark from the crop it "
                                 "was lifted out of. Wire both outputs of "
                                 "Pencil Lift.")
            a = pencil_alpha[0].detach().cpu().numpy().astype(np.float32)
            if a.shape != rgb.shape[:2]:
                raise ValueError(f"pencil is {rgb.shape[1]}x{rgb.shape[0]} and "
                                 f"its alpha is {a.shape[1]}x{a.shape[0]}")
            mark = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a * 255])
                                   .astype(np.uint8), "RGBA")

        notes: list[str] = []
        out, info = pg.render(cfg, lines, face=FONTS / font, seed=seed,
                              plate_rgb=plate_rgb, pencil_rgba=mark, fit=fit,
                              warn=lambda m: notes.append(m))
        W, H = out.shape[1], out.shape[0]

        report = "\n".join([f"{W}x{H}", *notes]
                           + [pg.anchor(a.strip(), info, W, H)
                              for a in anchors.splitlines() if a.strip()])
        return io.NodeOutput(_image(out), report, ui=ui.PreviewText(report))
