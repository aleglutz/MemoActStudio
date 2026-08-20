"""Subtitle track: .ass for burn-in, .srt as a sidecar (SPEC §5.5).

Why .ass and not per-frame text (GAPS.md #3): P1 drew the caption onto every
frame with DrawText+, because a batched composite collapsed the batch. That
cost ~2.6x the render (139 s vs 54 s on demo_en) and scaled with frame count.
libass draws each cue once per *cue*, inside the same ffmpeg pass that encodes
the reel — see memoacts_core.render.encode(ass=...).

**The text written here is the verbatim script.** Alignment supplies timings
only; `text_normalized` (the digits-expanded form fed to the aligner) must
never reach this module. That is the whole reason the workflow beats CapCut's
auto-subtitles, and it is a project non-negotiable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import caption
from .align import Word

PLAY_W, PLAY_H = 1080, 1920

#: Fonts shipped with the project. Burn-in resolves against this rather than a
#: system font install, so a fresh machine renders identical captions with no
#: provisioning step (HARDENING.md). Share Tech Mono is SIL OFL 1.1 — the
#: licence travels with it in assets/fonts/OFL.txt, as the OFL requires.
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

#: The file behind SubStyle.font, needed because measuring a line (to keep it
#: to one line) has to open the same font libass will burn in.
_FONT_FILE = "ShareTechMono-Regular.ttf"


@dataclass
class SubStyle:
    """Neutral default styling, matching the look P1 established with DrawText+.

    `margin_v` is the gap from the edge the style is anchored to, in
    play-resolution pixels — the bottom for `alignment` 1–3, the top for 7–9.
    The default keeps captions clear of the region where Reels/TikTok/Shorts
    draw their own UI — but the exact safe-zone figures are still an unverified
    SPEC §10 open item, so treat 420 as "what P1 used and looked right", not as
    researched platform guidance.
    """
    #: Style name as written into the .ass. Cues select a style by this name, so
    #: a track can carry captions and labels in one file and one libass pass.
    name: str = "Default"
    #: ASS numpad alignment: 1–3 bottom, 4–6 middle, 7–9 top; 1/4/7 left,
    #: 2/5/8 centre, 3/6/9 right. 2 is bottom-centre, and `margin_v` then puts
    #: the caption where it actually belongs, which is neither place the two
    #: obvious answers offer. Along the foot of the frame it asks the eye to
    #: travel away from the picture and back for every cue — this reel is 9:16
    #: and its subjects, a signature, a face, a map, sit centre-frame. Across
    #: the middle (alignment 5, which ignores margin_v) it lands *on* them, and
    #: on a page move it always will, because there the camera is aimed at its
    #: subject by construction. So: below the middle, clear of both.
    alignment: int = 2
    font: str = "Share Tech Mono"
    #: 56, up from P1's 44. Affordable only because a caption is now one short
    #: line rather than a whole narration block: at 56 the usable width holds
    #: ~31 characters, which would have been unusable when a cue had to carry
    #: 175 of them.
    size: int = 56
    primary: str = "#FFFFFF"
    outline: str = "#000000"
    shadow: str = "#000000"
    outline_width: float = 0.0
    shadow_depth: float = 2.0
    margin_l: int = 60
    margin_r: int = 60
    #: One position for the whole reel, hook included — a caption that moves
    #: between a title beat and the reel proper reads as two different films.
    #: Which makes the cold open the binding constraint, since it is the one
    #: beat whose subject is *drawn* rather than photographed and so has a
    #: measurable extent: the pencilled 67 carries ink down to y = 1259 of 1920,
    #: and 670 put the plate's top edge at 1184 — straight through the tail of
    #: the 7. 530 clears the lowest ink by ~65 px and still sits 110 px above
    #: the 420 the cold open used before the two positions were merged.
    margin_v: int = 530
    bold: bool = False

    #: Plate behind the text. White captions over a pale document are
    #: unreadable without one — the archival stills in this material run from
    #: near-black to bare paper, and no outline colour survives both.
    #: 0 disables it and restores the plain outline style. 0.68 rather than the
    #: 0.80 the reel was first cut with: enough of the paper reads through the
    #: box for it to sit on the sheet instead of punching a hole in it, and the
    #: white type still clears the brightest source in the reel.
    plate_opacity: float = 0.68
    plate_colour: str = "#000000"
    plate_pad: float = 10.0        # how far the box extends past the text


def _ass_colour(hex_rgb: str, opacity: float = 1.0) -> str:
    """#RRGGBB -> &HAABBGGRR.

    ASS stores colours alpha-first and byte-reversed, so the intuitive
    conversion produces red where you wanted blue. Alpha runs backwards too:
    00 is fully opaque and FF fully transparent, so an `opacity` of 1 maps to
    00. Both traps cost an hour each if rediscovered.
    """
    h = hex_rgb.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_rgb!r}")
    r, g, b = h[0:2], h[2:4], h[4:6]
    alpha = max(0, min(255, round(255 * (1.0 - opacity))))
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(t: float) -> str:
    """Seconds -> H:MM:SS.cc (ASS uses centiseconds, not milliseconds)."""
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escape_ass(text: str) -> str:
    """Neutralise the two things libass reads as markup: braces open override
    blocks, and a literal newline would end the Dialogue line."""
    text = text.replace("{", "(").replace("}", ")")
    return re.sub(r"\s*\n\s*", r"\\N", text.strip())


@dataclass
class Cue:
    t_start: float
    t_end: float
    text: str
    style: str = "Default"


def label_style(**over) -> SubStyle:
    """The identifying tag: who this is, or where this is.

    Top-right, because everything else is committed — the caption owns the
    bottom, and the right edge below the midline is where Reels/TikTok/Shorts
    stack their own action column. Smaller than the caption and it must stay
    that way: a label competing with the narration line reads as a second
    voice rather than an annotation.

    Same unverified-safe-zone caveat as `SubStyle`: 220 from the top is chosen
    to clear a platform header, not measured against one (SPEC §10).
    """
    st = SubStyle(name="Label", alignment=9, size=40, margin_v=220,
                  plate_opacity=0.70)
    for k, v in over.items():
        setattr(st, k, v)
    return st


def credit_style(**over) -> SubStyle:
    """The source line: whose footage this is, and from what.

    Under the label and smaller, because it answers a different question. A
    label tells the viewer where they are and can go away once read; a credit
    is a condition of use and stays up for as long as the material it names is
    on screen. Same corner, so the two read as one block rather than as two
    annotations competing across the frame.
    """
    st = SubStyle(name="Credit", alignment=9, size=26, margin_v=286,
                  plate_opacity=0.70)
    for k, v in over.items():
        setattr(st, k, v)
    return st


def _style_line(st: SubStyle) -> str:
    boxed = st.plate_opacity > 0.0
    plate_col = _ass_colour(st.plate_colour, st.plate_opacity)
    # BorderStyle 1 = outline + drop shadow; 3 = opaque box, where the Outline
    # field becomes the box's padding rather than a stroke width. Renderers
    # disagree about which colour fills that box — VSFilter uses OutlineColour,
    # some builds reach for BackColour — so both are set to the plate colour and
    # the question stops mattering.
    return (
        f"Style: {st.name},{st.font},{st.size},{_ass_colour(st.primary)},"
        f"{_ass_colour(st.primary)},{plate_col if boxed else _ass_colour(st.outline)},"
        f"{plate_col if boxed else _ass_colour(st.shadow)},{int(st.bold)},0,0,0,"
        f"100,100,0,0,{3 if boxed else 1},"
        f"{st.plate_pad if boxed else st.outline_width},"
        f"{0.0 if boxed else st.shadow_depth},{st.alignment},"
        f"{st.margin_l},{st.margin_r},{st.margin_v},1"
    )


def build_ass(cues: list[Cue], style: SubStyle | list[SubStyle] | None = None,
              play_w: int = PLAY_W, play_h: int = PLAY_H) -> str:
    styles = ([style] if isinstance(style, SubStyle)
              else list(style) if style else [SubStyle()])
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_w}",
        f"PlayResY: {play_h}",
        # WrapStyle 0 = balanced auto-wrap. P1 could not wrap at all, so a long
        # sentence ran off the frame; libass splits it across lines instead.
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        *(_style_line(st) for st in styles),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    known = {st.name for st in styles}
    for c in cues:
        if c.style not in known:
            raise ValueError(
                f"cue at {c.t_start:.2f}s wants style {c.style!r}, which this "
                f"track does not define (has: {', '.join(sorted(known))})")
    body = [
        f"Dialogue: 0,{_ass_time(c.t_start)},{_ass_time(c.t_end)},{c.style},,"
        f"0,0,0,,{_escape_ass(c.text)}"
        for c in cues
    ]
    return "\n".join(header + body) + "\n"


def build_srt(cues: list[Cue]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{_srt_time(c.t_start)} --> {_srt_time(c.t_end)}\n"
                   f"{c.text.strip()}\n")
    return "\n".join(out)


def cues_from_shots(shots: list[dict], style: SubStyle | None = None,
                    play_w: int = PLAY_W, *, segment: bool = True,
                    min_duration: float = 1.0) -> list[Cue]:
    """Build cues from shots.json entries.

    Reads `text` — the verbatim script — and never `text_normalized`.

    With schema >= 1.1 each shot carries word timings, and a block is cut into
    captions that fit on one line (see memoacts_core.caption for why one line is
    a correctness requirement and not a preference). Without them — an older
    shots.json, or `segment=False` — this falls back to one cue per block, which
    is what P1 did.
    """
    st = style or SubStyle()
    if not segment:
        return [Cue(s["t_start"], s["t_end"], s["text"]) for s in shots]

    font_path = FONTS_DIR / _FONT_FILE
    width = caption.usable_width(play_w, st.margin_l, st.margin_r,
                                 st.plate_pad if st.plate_opacity > 0 else 0.0)
    cues: list[Cue] = []
    for s in shots:
        raw = s.get("words") or []
        if not raw:
            cues.append(Cue(s["t_start"], s["t_end"], s["text"]))
            continue
        words = [Word(w["text"], w["t_start"], w["t_end"]) for w in raw]
        for c in caption.segment(words, size=st.size, max_width=width,
                                 font_path=font_path,
                                 min_duration=min_duration):
            cues.append(Cue(c.t_start, c.t_end, c.text))
    return cues


def labels_from_shots(shots: list[dict], *, hold: float = 3.0,
                      style_name: str = "Label") -> list[Cue]:
    """One cue per shot that carries a `label` — a place or a person.

    The label goes up with the shot and holds for `hold` seconds, or the whole
    shot if that is shorter. It deliberately does not run the length of the
    shot: a tag is an answer to "who is this / where is this", and once the
    viewer has read it, leaving it up turns it into part of the frame. Blocks
    here run to fourteen seconds, so "whole shot" would be exactly that.

    Same field for both jobs by design — a location and a name sit in the same
    corner and read the same way, so there is nothing to gain from two
    mechanisms and a category to get wrong if there were two.
    """
    cues: list[Cue] = []
    for s in shots:
        text = (s.get("label") or "").strip()
        if not text:
            continue
        t0 = s["t_start"]
        t1 = min(t0 + hold, s["t_end"])
        if t1 > t0:
            cues.append(Cue(t0, t1, text, style=style_name))
    return cues


def credits_from_shots(shots: list[dict], *,
                       style_name: str = "Credit") -> list[Cue]:
    """One cue per shot that carries a `credit`, held for the whole shot.

    Unlike a label, this does not time out. A credit that disappears halfway
    through the material it credits has been shown rather than given, and for
    the one shot in this reel that is neither ours nor public domain
    (`SOURCES.md`) the on-screen attribution is the terms, not a courtesy.
    """
    return [Cue(s["t_start"], s["t_end"], (s.get("credit") or "").strip(),
                style=style_name)
            for s in shots if (s.get("credit") or "").strip()]


def check_wrap(cues: list[Cue], style: SubStyle | None = None,
               play_w: int = PLAY_W) -> list[Cue]:
    """Return the cues that will not fit on one line.

    Any non-empty result means overlapping plates and a dark bar through the
    text, so callers should surface it rather than ship it.
    """
    st = style or SubStyle()
    width = caption.usable_width(play_w, st.margin_l, st.margin_r,
                                 st.plate_pad if st.plate_opacity > 0 else 0.0)
    font_path = FONTS_DIR / _FONT_FILE
    return [c for c in cues
            if caption.text_width(c.text, st.size, font_path) > width]


def write_tracks(out_dir: Path, cues: list[Cue], *, stem: str = "subtitles",
                 style: SubStyle | None = None,
                 labels: list[Cue] | None = None,
                 label_st: SubStyle | None = None,
                 credits: list[Cue] | None = None,
                 credit_st: SubStyle | None = None) -> tuple[Path, Path]:
    """Write both the burn-in source and the sidecar. Returns (ass, srt).

    Labels join the captions in the one `.ass`, so burn-in stays a single
    libass pass and they cost nothing per frame (GAPS.md #3). They are kept out
    of the `.srt`: that sidecar is the spoken text, and a place-name nobody says
    aloud does not belong in it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ass = out_dir / f"{stem}.ass"
    srt = out_dir / f"{stem}.srt"
    st = style or SubStyle()
    styles = [st]
    events = list(cues)
    if labels:
        styles.append(label_st or label_style())
        events = sorted(events + labels, key=lambda c: c.t_start)
    if credits:
        styles.append(credit_st or credit_style())
        events = sorted(events + credits, key=lambda c: c.t_start)
    ass.write_text(build_ass(events, styles), encoding="utf-8")
    srt.write_text(build_srt(cues), encoding="utf-8")
    return ass, srt
