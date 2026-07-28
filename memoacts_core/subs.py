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

PLAY_W, PLAY_H = 1080, 1920

#: Fonts shipped with the project. Burn-in resolves against this rather than a
#: system font install, so a fresh machine renders identical captions with no
#: provisioning step (HARDENING.md). Share Tech Mono is SIL OFL 1.1 — the
#: licence travels with it in assets/fonts/OFL.txt, as the OFL requires.
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


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
    size: int = 44
    primary: str = "#FFFFFF"
    outline: str = "#000000"
    shadow: str = "#000000"
    outline_width: float = 0.0
    shadow_depth: float = 2.0
    margin_l: int = 60
    margin_r: int = 60
    margin_v: int = 420
    bold: bool = False


def _ass_colour(hex_rgb: str) -> str:
    """#RRGGBB -> &HAABBGGRR.

    ASS stores colours alpha-first and byte-reversed, so the intuitive
    conversion produces red where you wanted blue. Alpha 00 is fully opaque.
    """
    h = hex_rgb.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_rgb!r}")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


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
        # Alignment 2 = bottom centre. BorderStyle 1 = outline + drop shadow.
        f"Style: Default,{st.font},{st.size},{_ass_colour(st.primary)},"
        f"{_ass_colour(st.primary)},{_ass_colour(st.outline)},"
        f"{_ass_colour(st.shadow)},{int(st.bold)},0,0,0,100,100,0,0,1,"
        f"{st.outline_width},{st.shadow_depth},2,"
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


def cues_from_shots(shots: list[dict]) -> list[Cue]:
    """Build cues from shots.json entries.

    Reads `text` — the verbatim script — and never `text_normalized`.
    """
    return [Cue(t_start=s["t_start"], t_end=s["t_end"], text=s["text"])
            for s in shots]


def write_tracks(out_dir: Path, cues: list[Cue], *, stem: str = "subtitles",
                 style: SubStyle | None = None) -> tuple[Path, Path]:
    """Write both the burn-in source and the sidecar. Returns (ass, srt)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ass = out_dir / f"{stem}.ass"
    srt = out_dir / f"{stem}.srt"
    ass.write_text(build_ass(cues, style), encoding="utf-8")
    srt.write_text(build_srt(cues), encoding="utf-8")
    return ass, srt
