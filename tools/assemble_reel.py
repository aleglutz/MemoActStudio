"""Join finished clips end to end and mux the narration under them.

    python tools/assemble_reel.py \
        --clip projects/legends_of_surrender/composites/S00_hook.mp4 \
        --clip projects/legends_of_surrender/out/reel.mp4 \
        --narration projects/legends_of_surrender/narration.wav \
        --out projects/legends_of_surrender/out/reel_with_hook.mp4

    python tools/assemble_reel.py --segments-dir out/ --narration narration.mp3 \
        --out reel.mp4                      # the P1 chunked path, unchanged

Two ways in: `--clip`, named and ordered, or `--segments-dir`, which picks up
*.mp4 in lexical order (the P1 path, P1_GRAPH.md). Video is concatenated
WITHOUT re-encoding — every clip must already agree on codec, size, pixel
format and frame rate, which they do when they come from
`memoacts_core.render.encode`.

**The narration is delayed, not the audio re-cut.** A cold open carries no
recorded line, so the reel proper starts some seconds in; `--narration-at`
pads the front of the narration with exactly that much digital silence and
encodes the result once from the master WAV. The alternative — joining an
already-encoded reel's AAC to a silent AAC segment — costs the narration a
second generation of lossy encoding for nothing, and AAC's encoder priming
would put the whole recording a frame or two off besides. Where the delay is
not given it is read from the clips ahead of the reel, so it cannot drift from
what was actually joined.

Narration is never time-stretched (SPEC §5.6), and `-shortest` is deliberately
absent: the recording is typically a few ms shorter than the frame-quantised
video and would drop the reel's last frame.

`--subs` takes the sidecar of each clip in the same order and writes one .srt
beside the output, each shifted by the clips ahead of it. That file is what a
narrator reads from when a line still has to be recorded to fit a cut.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.video import probe  # noqa: E402


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


_SRT_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def shift_srt(text: str, by: float, first: int = 1) -> tuple[str, int]:
    """Move every cue in an .srt `by` seconds, renumbering from `first`."""
    def stamp(m: re.Match) -> str:
        ms = (int(m.group(1)) * 3600000 + int(m.group(2)) * 60000
              + int(m.group(3)) * 1000 + int(m.group(4)))
        ms = max(ms + int(round(by * 1000)), 0)     # in whole ms, so 999.6 ms
        h, rest = divmod(ms, 3600000)               # cannot round up into 1000
        mnt, rest = divmod(rest, 60000)
        sec, rest = divmod(rest, 1000)
        return f"{h:02d}:{mnt:02d}:{sec:02d},{rest:03d}"

    out, n = [], first
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        out.append(f"{n}\n" + _SRT_TIME.sub(stamp, "\n".join(lines)))
        n += 1
    return "\n\n".join(out), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", type=Path, action="append", default=[],
                    help="a finished clip, in order; repeatable")
    ap.add_argument("--segments-dir", type=Path,
                    help="instead of --clip: every *.mp4 in it, lexically")
    ap.add_argument("--narration", type=Path, required=True)
    ap.add_argument("--narration-at", type=float,
                    help="seconds of silence before the narration starts. "
                         "Default: the length of every clip ahead of the one "
                         "the narration belongs to (see --narration-under)")
    ap.add_argument("--narration-under", type=int, default=-1,
                    help="which clip the narration runs under, 1-based. "
                         "Default -1, the last")
    ap.add_argument("--subs", type=Path, action="append", default=[],
                    help="each clip's .srt, in the same order; repeatable")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    clips = list(args.clip)
    if args.segments_dir:
        clips += sorted(args.segments_dir.glob("*.mp4"))
    if not clips:
        print("nothing to assemble: pass --clip or --segments-dir")
        return 1
    missing = [c for c in clips if not c.exists()]
    if missing:
        print("missing:", ", ".join(str(c) for c in missing))
        return 1

    spans = [probe(c).duration for c in clips]
    for c, d in zip(clips, spans):
        print(f"  {d:8.3f} s  {c.name}")

    under = args.narration_under - 1 if args.narration_under > 0 else len(clips) - 1
    lead = sum(spans[:under])
    at = lead if args.narration_at is None else args.narration_at
    if abs(at - lead) > 1 / 30:
        print(f"  WARNING --narration-at {at:.3f} s is not where "
              f"{clips[under].name} begins ({lead:.3f} s)")
    print(f"  narration under {clips[under].name}, delayed by {at:.3f} s")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{c.resolve().as_posix()}'\n")
        lst = f.name

    cmd = [ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", lst,
           "-i", str(args.narration),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    if at > 0:
        ms = int(round(at * 1000))
        cmd += ["-af", f"adelay={ms}:all=1"]
    # no -shortest: narration is typically a few ms shorter than the
    # frame-quantised video and -shortest would drop the last frame
    cmd += ["-movflags", "+faststart", str(args.out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    Path(lst).unlink(missing_ok=True)
    if r.returncode:
        print(r.stderr[-2000:])
        return r.returncode
    print("wrote", args.out)

    if args.subs:
        if len(args.subs) != len(clips):
            print(f"  WARNING {len(args.subs)} sidecars for {len(clips)} clips; "
                  f"they are matched in order")
        blocks, n = [], 1
        for sub, offset in zip(args.subs, [sum(spans[:i]) for i in range(len(clips))]):
            if not sub.exists():
                print(f"  WARNING no sidecar {sub}")
                continue
            text, n = shift_srt(sub.read_text(encoding="utf-8"), offset, n)
            blocks.append(text)
        srt = args.out.with_suffix(".srt")
        srt.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        print(f"wrote {srt}  {n - 1} cues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
