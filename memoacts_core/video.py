"""Video fragments as a frame source (SPEC §5.2, §2.3).

A still shot and a footage shot differ in exactly one thing: where the pixels
for frame *i* come from. Everything after that — the per-frame crop rect from
`schedule.compute`, the resize, the letterbox, shake, the effect stack — is
already written against "an image per frame" and does not care whether the
image was decoded or repeated. So this module supplies frames and stops there,
and every motion preset works on footage without knowing footage exists.

Audio is deliberately not touched. The narration is the only audio track in a
reel and it passes through untouched (a project non-negotiable); a fragment's
own sound is dropped at decode.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image

from .render import ffmpeg_exe

#: Extensions treated as footage. Kept beside shotlist.VIDEO_EXTS rather than
#: imported from it: that module decides what a *shot list* may name, this one
#: what this decoder can actually open, and they are free to diverge.
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def ffprobe_exe() -> str:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    # Same directory as ffmpeg when it is not separately on PATH.
    cand = Path(ffmpeg_exe()).with_name("ffprobe" + Path(ffmpeg_exe()).suffix)
    if cand.exists():
        return str(cand)
    raise RuntimeError("ffprobe not found; needed to read video fragments")


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


def probe(path: Path) -> VideoInfo:
    """Dimensions, frame rate and duration of the first video stream."""
    out = subprocess.run(
        [ffprobe_exe(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    doc = json.loads(out)
    if not doc.get("streams"):
        raise ValueError(f"{path.name}: no video stream")
    st = doc["streams"][0]
    num, _, den = st["r_frame_rate"].partition("/")
    fps = float(num) / float(den or 1)
    return VideoInfo(int(st["width"]), int(st["height"]), fps,
                     float(doc.get("format", {}).get("duration", 0.0)))


def frames(path: Path, n: int, *, start: float = 0.0, fps: int = 30,
           speed: float = 1.0) -> Iterator[Image.Image]:
    """Decode exactly `n` frames from `start`, resampled to `fps`.

    `speed` is playback rate: 0.4 is the slow motion SPEC §5.2 asks for, 2.0
    runs it double. It is applied by restamping presentation times and then
    resampling to the reel's frame rate, so the shot's frame count stays what
    the schedule said it was — the timeline is fixed by the narration, and
    footage bends to it rather than the reverse.

    Running out of footage raises rather than padding: a fragment that ends
    mid-shot is an edit that has not been finished, and the reel silently
    freezing on its last frame would hide that.
    """
    if speed <= 0:
        raise ValueError(f"speed must be > 0, got {speed}")
    info = probe(path)
    w, h = info.size
    # setpts divides by speed, so speed < 1 stretches the clip (slow motion);
    # fps then resamples whatever came out to the reel's rate.
    vf = f"setpts=PTS/{speed},fps={fps}"
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin",
           "-ss", f"{start:.6f}", "-i", str(path),
           "-an", "-vf", vf, "-frames:v", str(n),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    stride = w * h * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=stride)
    try:
        for i in range(n):
            buf = proc.stdout.read(stride)
            if len(buf) < stride:
                need = (n / fps) * speed
                raise ValueError(
                    f"{path.name}: ran out of footage after {i} of {n} frames. "
                    f"From {start:.2f}s at speed {speed} this shot needs "
                    f"{need:.2f}s, but the fragment is {info.duration:.2f}s long")
            yield Image.frombytes("RGB", (w, h), buf)
    finally:
        # Both pipes, not just stdout: stderr is opened by Popen too, and
        # leaving it dangling leaks a descriptor per shot and trips
        # ResourceWarning under -W error.
        for pipe in (proc.stdout, proc.stderr):
            if pipe:
                pipe.close()
        proc.terminate()
        proc.wait(timeout=10)
