"""Rebuild every generated file this project's shot list points at.

    python tools/rebuild_media.py --project projects/legends_of_surrender

`REBUILD.md` in the project folder is the authoritative record: what each build
is, why it is framed that way, and what to change if the narration is
re-recorded. This runs the same five commands with the same arguments, so a
machine that has just pulled the repository can produce the media in one step
instead of retyping sixteen keyframes into a shell that quotes differently.

Kept as a list of argument lists rather than shell lines on purpose: no quoting,
no line continuations, and the same behaviour on Windows and macOS. Nothing here
takes a decision — every value below is copied from REBUILD.md, and REBUILD.md
is where a change belongs first.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def builds(project: str) -> list[tuple[str, list[str]]]:
    return [
        ("map_baltics", [
            "tools/render_map.py", "--out", f"{project}/maps",
            "--name", "map_baltics", "--frames", "360", "--palette", "ink",
            "--highlight", "Latvia", "Estonia", "Lithuania"]),
        ("map_poland_ukraine", [
            "tools/render_map.py", "--out", f"{project}/maps",
            "--name", "map_poland_ukraine", "--frames", "360",
            "--palette", "ink", "--highlight", "Poland", "Ukraine",
            "--already", "Latvia", "Estonia", "Lithuania"]),
        ("map_france_reims", [
            "tools/render_map.py", "--out", f"{project}/maps",
            "--name", "map_france_reims", "--highlight", "France",
            "--context", "1.5", "--scale", "2", "--palette", "ink",
            "--marker", "4.0317,49.2583,Reims"]),
        ("S01-02_two-band", [
            "tools/render_bands.py", "--project", project,
            "--name", "S01-02_two-band", "--still",
            "--band", "Reims-Signing.jpg:0.5",
            "--band", "Karlshorst_Signing.jpg:0.5"]),
        ("S18_three-cities_bw", [
            "tools/render_bands.py", "--project", project,
            "--name", "S18_three-cities_bw", "--still", "--mono",
            "--band", "London.jpg:0.5", "--band", "Berlin.jpg:0.5",
            "--band", "Moscow.jpg:0.5"]),
        ("S12_ru_page_move", [
            "tools/render_move.py", "--project", project,
            "--image", "GIoS_Wehrmacht_Signed_Ru_p1.jpg",
            "--image", "GIoS_Wehrmacht_Signed_Ru.jpg",
            "--name", "S12_ru_page_move", "--frames", "344",
            "--ease", "cosine",
            "--key", "0.000:0.500,0.950,2.60,1",
            "--key", "0.035:0.500,0.950,2.60",
            "--key", "0.122:-0.231,0.950,2.60",
            "--key", "0.166:-0.231,0.950,2.60",
            "--key", "0.279:1.231,0.863,2.60",
            "--key", "0.314:1.231,0.863,2.60",
            "--key", "0.384:0.550,0.780,2.60",
            "--key", "0.414:0.550,0.780,1.43",
            "--key", "0.528:-0.066,0.204,1.43",
            "--key", "0.567:-0.066,0.204,1.43",
            "--key", "0.672:0.796,0.309,1.43",
            "--key", "0.715:0.796,0.309,1.43",
            "--key", "0.942:0.328,0.929,1.43",
            "--key", "1.000:0.328,0.929,1.43",
            "--turn", "0.384,0.414,2"]),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="projects/legends_of_surrender",
                    help="project folder, relative to the repository root")
    ap.add_argument("--only", action="append", default=[],
                    help="rebuild just these by name; repeatable")
    ap.add_argument("--list", action="store_true",
                    help="print what would be built and stop")
    args = ap.parse_args()

    project = Path(args.project).as_posix()
    todo = [(n, a) for n, a in builds(project)
            if not args.only or n in args.only]
    if not todo:
        print(f"nothing matches --only {args.only}"); return 1
    if args.list:
        for name, argv in todo:
            print(f"{name}\n    python {' '.join(argv)}\n")
        return 0

    for i, (name, argv) in enumerate(todo, 1):
        print(f"\n=== [{i}/{len(todo)}] {name} " + "=" * 40)
        # sys.executable, so this runs under whatever interpreter started it —
        # on Windows that is ComfyUI's embedded Python, which is the one with
        # the dependencies (CLAUDE.md).
        r = subprocess.run([sys.executable, *argv], cwd=ROOT)
        if r.returncode:
            print(f"\n{name} failed ({r.returncode}); stopping so the rest of "
                  f"the media is not built against a half-made set")
            return r.returncode
    print(f"\nrebuilt {len(todo)} of {len(builds(project))}. "
          f"Next: generate_shots.py, then render_reel.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())