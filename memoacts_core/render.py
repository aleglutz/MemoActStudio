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
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from .schedule import ShotSchedule

OUT_W, OUT_H = 1080, 1920
RESAMPLE = Image.Resampling.LANCZOS

#: What shows around an image that does not fill the frame (`square_in`).
#: Black, so the inset reads as a card rather than as a rendering mistake.
MATTE = (0, 0, 0)


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
    """One shot: its media, per-frame crop rects, and an optional effect stack.

    `media` is a still or a video fragment; the difference is confined to where
    frame *i*'s pixels come from (see `_source_frames`). `media_in` and `speed`
    are footage-only and ignored for a still.
    """
    media: Path
    schedule: ShotSchedule
    effects: "EffectStack | None" = None
    media_in: float = 0.0
    speed: float = 1.0


def _check_upscale(shot: ShotRender, out_w: int, policy: str) -> None:
    """Enforce the resolution guard at render time (SPEC §5.2).

    `schedule.compute` clamps the zoom *rate* so motion never digs below the
    output width, but a source can be too small before any zoom is applied —
    demo_en's 800x1000 still yields a 562px-wide 9:16 window against a 1080px
    output, a 1.9x enlargement. Clamping the rate cannot fix that, and the
    project forbids upscaling silently, so the decision surfaces here.
    """
    # The *narrowest* crop is the binding one — it is the frame stretched
    # furthest. `compute` clamps the zoom rate so that for the ordinary presets
    # this equals the base window anyway; it differs for `square_in`, whose crop
    # narrows as the frame opens, and reporting the widest there would describe
    # the one frame that is fine and stay quiet about the rest.
    narrowest = min(shot.schedule.ws, default=out_w)
    if narrowest >= out_w:
        return
    factor = out_w / narrowest
    msg = (f"{shot.media.name}: source supplies only {narrowest}px for a "
           f"{out_w}px output ({factor:.2f}x enlargement)")
    if policy == "error":
        raise ValueError(msg)
    if policy == "warn":
        warnings.warn(msg, stacklevel=3)


def _source_frames(shot: ShotRender, n: int, fps: int) -> Iterator[Image.Image]:
    """The shot's `n` source frames, at native resolution.

    This is the whole of the still/footage difference. A still is decoded once
    and handed back n times — the caller crops it, which copies, so sharing the
    original is safe and one decode is the point (§GAPS #2, frame-streaming).
    Footage is decoded lazily by `video.frames`, one frame per output frame.
    """
    from .video import frames as video_frames, is_video
    if is_video(shot.media):
        yield from video_frames(shot.media, n, start=shot.media_in, fps=fps,
                                speed=shot.speed)
        return
    src = load_source(shot.media)
    for _ in range(n):
        yield src


def shot_frames(shot: ShotRender, out_w: int = OUT_W, out_h: int = OUT_H,
                on_upscale: str = "warn", fps: int = 30) -> Iterator[Image.Image]:
    """Yield the shot's frames one at a time, cropped, scaled and graded.

    The source stays open for the whole shot (one decode, not one per frame);
    each yielded frame is an independent image the caller is expected to drop
    before asking for the next.

    `on_upscale` is the SPEC §5.2 guard policy: "warn" (default), "error" to
    refuse the shot outright, or "allow" to enlarge knowingly and silently.

    Shake is applied here rather than in the effect pipeline: it offsets the
    crop window inside the source, so it costs nothing and cannot expose an
    empty edge (see memoacts_core.effects).
    """
    if on_upscale not in ("warn", "error", "allow"):
        raise ValueError(f"on_upscale must be warn|error|allow, got {on_upscale!r}")
    _check_upscale(shot, out_w, on_upscale)

    s = shot.schedule
    n = len(s.ws)
    sources = _source_frames(shot, n, fps)

    offsets = [(0, 0)] * n
    pipeline = None
    if shot.effects is not None:
        from .effects import EffectPipeline, shake_offsets
        if shot.effects.shake is not None:
            offsets = shake_offsets(shot.effects.shake, n, fps)
        pipeline = EffectPipeline(shot.effects, out_w, out_h)

    try:
        for i, (x, y, w, h) in enumerate(zip(s.xs, s.ys, s.ws, s.hs)):
            src = next(sources)
            src_w, src_h = src.size
            dx, dy = offsets[i]
            # Clamp into the source: at the edge the shake flattens rather than
            # sliding past the image and producing a black border.
            x = min(max(x + dx, 0), max(src_w - w, 0))
            y = min(max(y + dy, 0), max(src_h - h, 0))
            crop = src.crop((x, y, x + w, y + h))
            dst_h = s.dst_hs[i] if s.dst_hs else out_h
            if dst_h >= out_h:
                frame = crop.resize((out_w, out_h), RESAMPLE)
            else:
                # The image does not fill the frame yet (square_in). Letterbox
                # rather than stretch: the bands are part of the device.
                frame = Image.new("RGB", (out_w, out_h), MATTE)
                frame.paste(crop.resize((out_w, dst_h), RESAMPLE),
                            (0, (out_h - dst_h) // 2))
            yield frame if pipeline is None else pipeline.apply(frame, i)
    finally:
        sources.close()
        if pipeline is not None:
            pipeline.close()


def reel_frames(shots: Iterable[ShotRender], out_w: int = OUT_W,
                out_h: int = OUT_H, on_upscale: str = "warn",
                fps: int = 30) -> Iterator[Image.Image]:
    for shot in shots:
        yield from shot_frames(shot, out_w, out_h, on_upscale, fps)


def _escape_filter_path(path: Path) -> str:
    r"""Escape a path for use as an *unquoted* ffmpeg filter option value.

    Two parsers stand between this string and libass, and each consumes one
    level of escaping: the filtergraph parser splits filters on ':' and
    unescapes, then the filter's own option parser splits options on ':' and
    unescapes again. A Windows drive colon therefore has to be written
    ``C\\:/a/b.ass`` to arrive as ``C:/a/b.ass``; as_posix() flips the
    separators on the way.

    Quoting the value instead — ``subtitles='...'`` — is what this did until
    now, and **ffmpeg 8.0 stopped accepting it**: the opening quote is read as
    running to the *last* quote in the filter, so the ``':fontsdir='`` between
    them is swallowed and the parse dies with "No option name near ...".
    Escaping works on both, and quoting never solved the colon anyway — a
    quoted ``C:/a/b.ass`` still splits at the filter's own option parser, which
    is why the escape was there as well.

    Getting this wrong fails as "Unable to open file", which reads like a
    missing file rather than a quoting bug.
    """
    s = path.resolve().as_posix()
    # Backslashes first, or the escapes added next would themselves be escaped.
    # as_posix() has already removed the separators, so this only bites on a
    # backslash inside a filename.
    s = s.replace("\\", "\\\\\\\\")
    for ch in (":", "'"):
        s = s.replace(ch, "\\\\" + ch)
    return s


def encode(frames: Iterable[Image.Image], out_path: Path, fps: int, *,
           narration: Path | None = None, ass: Path | None = None,
           fontsdir: Path | None = None, tune: str | None = None,
           max_mbps: float | None = 12.0, sfx: Path | None = None,
           crf: int = 19, out_w: int = OUT_W, out_h: int = OUT_H) -> Path:
    """Stream frames into one ffmpeg process and write a finished MP4.

    Subtitles are burned once here via libass when `ass` is given, rather than
    drawn onto every frame upstream — that is the GAPS.md #3 fix (P1's
    per-frame DrawText+ cost ~2.6x the render).

    Narration is copied in untouched: never re-encoded beyond the AAC mux it
    needs, never time-stretched (SPEC §5.6). `-shortest` is deliberately absent
    — narration is typically a few ms shorter than the frame-quantised video
    and it would drop the final frame.

    `sfx` is the sound design layer (`memoacts_core.sfx`), summed with the
    narration here rather than mixed into it upstream. That is the whole reason
    it is a second input: the voice reaches this process as recorded, and the
    single AAC encode the mux already performed is still the only one. `amix`
    runs with `normalize=0` — its default divides every input by the number of
    inputs, which would quietly drop the narration 6 dB the moment a sound
    design existed.
    """
    if out_w % 2 or out_h % 2:
        raise ValueError(f"H.264 needs even dimensions, got {out_w}x{out_h}")
    if sfx is not None and narration is None:
        raise ValueError("a sound design without narration to mix it under; "
                         "render the reel with its recording or without sfx")

    cmd = [ffmpeg_exe(), "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-"]
    if narration is not None:
        cmd += ["-i", str(narration)]
    if sfx is not None:
        cmd += ["-i", str(sfx)]
    if ass is not None:
        # Point libass at the font shipped with the project rather than a
        # system install, so a fresh machine renders identical captions with no
        # provisioning step. Pass fontsdir explicitly to override.
        if fontsdir is None:
            from .subs import FONTS_DIR
            fontsdir = FONTS_DIR
        vf = f"subtitles=filename={_escape_filter_path(ass)}"
        if fontsdir.is_dir():
            vf += f":fontsdir={_escape_filter_path(fontsdir)}"
        else:
            warnings.warn(
                f"fonts directory {fontsdir} not found; libass will fall back "
                f"to a system font and captions may not match the intended style",
                stacklevel=2)
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-preset", "medium"]
    if tune:
        # `-tune grain` exists precisely for this: film grain is high-frequency
        # noise that H.264 cannot model, so at CRF 19 the encoder spends its
        # whole budget preserving individual particles. Measured on demo_en, a
        # grainy 13.8 s reel came out at 178 MB (~103 Mbps) against 1.9 MB
        # ungraded — the tune keeps the grain reading right at a fraction of it.
        cmd += ["-tune", tune]
    if max_mbps:
        # SPEC §5.7 fixes the delivery target at 12 Mbps. CRF alone is
        # quality-targeted and has no ceiling, so cap it: without this a grain
        # preset silently produces a file no platform will accept.
        kbit = int(max_mbps * 1000)
        cmd += ["-maxrate", f"{kbit}k", "-bufsize", f"{kbit * 2}k"]
    if narration is not None and sfx is not None:
        # duration=first keeps the output as long as the narration, so a sound
        # whose tail runs past the last word cannot lengthen the file and pull
        # the video out of sync with it.
        cmd += ["-filter_complex",
                "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0"
                ":normalize=0[aout]",
                "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    elif narration is not None:
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
                fontsdir: Path | None = None, max_mbps: float | None = 12.0,
                sfx: Path | None = None,
                crf: int = 19, out_w: int = OUT_W, out_h: int = OUT_H,
                on_upscale: str = "warn",
                on_frame: Callable[[int, int, Image.Image], None] | None = None
                ) -> Path:
    """Whole reel, one pass, constant memory. The P1 concat step disappears.

    `on_frame(done, total, frame)` is called as each frame leaves the renderer
    and before it reaches ffmpeg. This is the only progress signal the pipeline
    has: `encode` writes into a process whose stderr goes to a temp file rather
    than a pipe (a Windows deadlock, see `encode`), so ffmpeg's own counter is
    not readable. Raising from inside the callback stops the render — ffmpeg's
    stdin closes and `encode` reports a non-zero return.
    """
    shots = list(shots)
    # Pick the x264 tune from the content rather than making the caller know
    # about it: any shot carrying grain makes the whole reel grainy material.
    tune = "grain" if any(
        s.effects is not None and s.effects.grain is not None
        and s.effects.grain.amount > 0 for s in shots) else None
    frames = reel_frames(shots, out_w, out_h, on_upscale, fps)
    if on_frame is not None:
        frames = _counted(frames, sum(len(s.schedule.ws) for s in shots), on_frame)
    return encode(frames, out_path,
                  fps, narration=narration, ass=ass, fontsdir=fontsdir,
                  tune=tune, max_mbps=max_mbps, sfx=sfx, crf=crf,
                  out_w=out_w, out_h=out_h)


def _counted(frames: Iterable[Image.Image], total: int,
             on_frame: Callable[[int, int, Image.Image], None]
             ) -> Iterator[Image.Image]:
    """Count frames past a callback without holding any of them."""
    for i, frame in enumerate(frames, 1):
        on_frame(i, total, frame)
        yield frame
