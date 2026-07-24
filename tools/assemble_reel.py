"""Concat per-shot segments + mux narration (P1 assembly step, P1_GRAPH.md).

    python tools/assemble_reel.py --segments-dir out/ --narration narration.mp3 --out reel.mp4

Segments are picked up as *.mp4 in lexical order (shot_01…, chunks included).
Video streams are concatenated WITHOUT re-encoding; narration is muxed in the
same pass (AAC 192k, +faststart). Narration is never time-stretched (SPEC §5.6).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments-dir", type=Path, required=True)
    ap.add_argument("--narration", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    segs = sorted(args.segments_dir.glob("*.mp4"))
    if not segs:
        print("no *.mp4 segments in", args.segments_dir); return 1
    print(f"{len(segs)} segments:", ", ".join(s.name for s in segs))

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        for s in segs:
            f.write(f"file '{s.resolve().as_posix()}'\n")
        lst = f.name

    cmd = [ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", lst,
           "-i", str(args.narration),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           # no -shortest: narration is typically a few ms shorter than the
           # frame-quantised video and -shortest would drop the last frame
           "-movflags", "+faststart", str(args.out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    Path(lst).unlink(missing_ok=True)
    if r.returncode:
        print(r.stderr[-2000:]); return r.returncode
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
