"""Frame-streaming motion renderer — the P2 replacement for P1's tensor batches.

Why this exists (GAPS.md #2): P1 materialised a whole shot as float32 tensors,
~11.5 GiB for a 240-frame shot, because the graph held source-resolution crop
intermediates until the resize collected them. That forced <=60-frame chunking
and an external concat step. Here exactly one frame is alive at a time, so RAM
is constant in shot length: chunking is unnecessary and the whole reel encodes
in a single ffmpeg pass.

Why not ffmpeg zoompan (SPEC §5.3, §8): its integer rounding jitters visibly.
Crop rects are computed in float by memoacts_core.schedule, rendered with PIL,
and piped here as raw frames.

The split below is deliberate: `reel_frames` is a pure generator that can be
tested and inspected without touching ffmpeg, and `encode` is the only part
that spawns a process.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import warnings
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .schedule import ShotSchedule

OUT_W, OUT_H = 1080, 1920
RESAMPLE = Image.Resampling.LANCZOS


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # optional fallback; not a hard dependency
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_source(path: Path) -> Image.Image:
    """Open a still as plain RGB, upright.

    Covers the mixed-input pitfalls in SPEC §8: EXIF rotation is applied (phone
    and scanner output), and CMYK / palette / alpha sources are flattened to
    RGB so every downstream frame has the same layout.
    """
    img = ImageOps.exif_transpose(Image.open(path))
    return img if img.mode == "RGB" else img.convert("RGB")


@dataclass
class ShotRender:
    """One shot: a still plus the per-frame crop rects computed for it."""
    image: Path
    schedule: ShotSchedule


def _check_upscale(shot: ShotRender, out_w: int, policy: str) -> None:
    """Enforce the resolution guard at render time (SPEC §5.2).

    `schedule.compute` clamps the zoom *rate* so motion never digs below the
    output width, but a source can be too small before any zoom is applied —
    demo_en's 800x1000 still yields a 562px-wide 9:16 window against a 1080px
    output, a 1.9x enlargement. Clamping the rate cannot fix that, and the
    project forbids upscaling silently, so the decision surfaces here.
    """
    widest = max(shot.schedule.ws, default=out_w)
    if widest >= out_w:
        return
    factor = out_w / widest
    msg = (f"{shot.image.name}: source supplies only {widest}px for a {out_w}px "
           f"output ({factor:.2f}x enlargement)")
    if policy == "error":
        raise ValueError(msg)
    if policy == "warn":
        warnings.warn(msg, stacklevel=3)


def shot_frames(shot: ShotRender, out_w: int = OUT_W, out_h: int = OUT_H,
                on_upscale: str = "warn") -> Iterator[Image.Image]:
    """Yield the shot's frames one at a time, cropped and scaled to output size.

    The source stays open for the whole shot (one decode, not one per frame);
    each yielded frame is an independent image the caller is expected to drop
    before asking for the next.

    `on_upscale` is the SPEC §5.2 guard policy: "warn" (default), "error" to
    refuse the shot outright, or "allow" to enlarge knowingly and silently.
    """
    if on_upscale not in ("warn", "error", "allow"):
        raise ValueError(f"on_upscale must be warn|error|allow, got {on_upscale!r}")
    _check_upscale(shot, out_w, on_upscale)
    src = load_source(shot.image)
    s = shot.schedule
    for x, y, w, h in zip(s.xs, s.ys, s.ws, s.hs):
        yield src.crop((x, y, x + w, y + h)).resize((out_w, out_h), RESAMPLE)


def reel_frames(shots: Iterable[ShotRender], out_w: int = OUT_W,
                out_h: int = OUT_H, on_upscale: str = "warn") -> Iterator[Image.Image]:
    for shot in shots:
        yield from shot_frames(shot, out_w, out_h, on_upscale)


def _escape_filter_path(path: Path) -> str:
    r"""Escape a path for use inside an ffmpeg filter argument.

    ffmpeg parses the filtergraph itself, so a Windows path needs its drive
    colon escaped and its separators flipped: C:\a\b.ass -> C\:/a/b.ass.
    Getting this wrong fails as "Unable to open file", which reads like a
    missing file rather than a quoting bug.
    """
    return path.resolve().as_posix().replace(":", r"\:")


def encode(frames: Iterable[Image.Image], out_path: Path, fps: int, *,
           narration: Path | None = None, ass: Path | None = None,
           fontsdir: Path | None = None,
           crf: int = 19, out_w: int = OUT_W, out_h: int = OUT_H) -> Path:
    """Stream frames into one ffmpeg process and write a finished MP4.

    Subtitles are burned once here via libass when `ass` is given, rather than
    drawn onto every frame upstream — that is the GAPS.md #3 fix (P1's
    per-frame DrawText+ cost ~2.6x the render).

    Narration is copied in untouched: never re-encoded beyond the AAC mux it
    needs, never time-stretched (SPEC §5.6). `-shortest` is deliberately absent
    — narration is typically a few ms shorter than the frame-quantised video
    and it would drop the final frame.
    """
    if out_w % 2 or out_h % 2:
        raise ValueError(f"H.264 needs even dimensions, got {out_w}x{out_h}")

    cmd = [ffmpeg_exe(), "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-"]
    if narration is not None:
        cmd += ["-i", str(narration)]
    if ass is not None:
        # Point libass at the font shipped with the project rather than a
        # system install, so a fresh machine renders identical captions with no
        # provisioning step. Pass fontsdir explicitly to override.
        if fontsdir is None:
            from .subs import FONTS_DIR
            fontsdir = FONTS_DIR
        vf = f"subtitles='{_escape_filter_path(ass)}'"
        if fontsdir.is_dir():
            vf += f":fontsdir='{_escape_filter_path(fontsdir)}'"
        else:
            warnings.warn(
                f"fonts directory {fontsdir} not found; libass will fall back "
                f"to a system font and captions may not match the intended style",
                stacklevel=2)
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-preset", "medium"]
    if narration is not None:
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(out_path)]

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg's stderr goes to a temp FILE, never to a pipe. Piping it deadlocks:
    # a Windows anonymous pipe defaults to ~4 KB, ffmpeg's banner plus the x264
    # options line alone exceeds that, and once ffmpeg blocks writing stderr it
    # stops draining stdin — so the frame write below blocks forever and the
    # render hangs with both processes idle. (Observed 2026-07-28: silent hang
    # with narration, which pushes stderr past the threshold; fine without it.)
    n = 0
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=log)
        assert proc.stdin is not None
        try:
            for frame in frames:
                if frame.size != (out_w, out_h):
                    frame = frame.resize((out_w, out_h), RESAMPLE)
                proc.stdin.write(frame.tobytes())
                n += 1
        except BrokenPipeError:
            # ffmpeg died early; the log holds the real diagnosis, so fall
            # through to the returncode check rather than raising this instead.
            pass
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
        proc.wait()
        log.seek(0)
        stderr = log.read().decode("utf-8", "replace")

    if proc.returncode:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{stderr[-2000:]}")
    if n == 0:
        raise ValueError("no frames were rendered")
    return out_path


def render_reel(shots: Iterable[ShotRender], out_path: Path, fps: int, *,
                narration: Path | None = None, ass: Path | None = None,
                fontsdir: Path | None = None,
                crf: int = 19, out_w: int = OUT_W, out_h: int = OUT_H,
                on_upscale: str = "warn") -> Path:
    """Whole reel, one pass, constant memory. The P1 concat step disappears."""
    return encode(reel_frames(shots, out_w, out_h, on_upscale), out_path, fps,
                  narration=narration, ass=ass, fontsdir=fontsdir, crf=crf,
                  out_w=out_w, out_h=out_h)
