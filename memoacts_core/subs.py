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

    `margin_v` is the gap from the bottom edge in play-resolution pixels. The
    default keeps captions clear of the region where Reels/TikTok/Shorts draw
    their own UI — but the exact safe-zone figures are still an unverified SPEC
    §10 open item, so treat 420 as "what P1 used and looked right", not as
    researched platform guidance.
    """
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
    margin_v: int = 420
    bold: bool = False

    #: Plate behind the text. White captions over a pale document are
    #: unreadable without one — the archival stills in this material run from
    #: near-black to bare paper, and no outline colour survives both.
    #: 0 disables it and restores the plain outline style.
    plate_opacity: float = 0.55
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


def build_ass(cues: list[Cue], style: SubStyle | None = None,
              play_w: int = PLAY_W, play_h: int = PLAY_H) -> str:
    st = style or SubStyle()
    boxed = st.plate_opacity > 0.0
    plate_col = _ass_colour(st.plate_colour, st.plate_opacity)
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
        # Alignment 2 = bottom centre.
        # BorderStyle 1 = outline + drop shadow; 3 = opaque box, where the
        # Outline field becomes the box's padding rather than a stroke width.
        # Renderers disagree about which colour fills that box — VSFilter uses
        # OutlineColour, some builds reach for BackColour — so both are set to
        # the plate colour and the question stops mattering.
        f"Style: Default,{st.font},{st.size},{_ass_colour(st.primary)},"
        f"{_ass_colour(st.primary)},{plate_col if boxed else _ass_colour(st.outline)},"
        f"{plate_col if boxed else _ass_colour(st.shadow)},{int(st.bold)},0,0,0,"
        f"100,100,0,0,{3 if boxed else 1},"
        f"{st.plate_pad if boxed else st.outline_width},"
        f"{0.0 if boxed else st.shadow_depth},2,"
        f"{st.margin_l},{st.margin_r},{st.margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    body = [
        f"Dialogue: 0,{_ass_time(c.t_start)},{_ass_time(c.t_end)},Default,,"
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
                 style: SubStyle | None = None) -> tuple[Path, Path]:
    """Write both the burn-in source and the sidecar. Returns (ass, srt)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ass = out_dir / f"{stem}.ass"
    srt = out_dir / f"{stem}.srt"
    ass.write_text(build_ass(cues, style), encoding="utf-8")
    srt.write_text(build_srt(cues), encoding="utf-8")
    return ass, srt
