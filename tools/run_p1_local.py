"""Drive the P1 stock-node graph against a local ComfyUI server, one
submission per shot-chunk (P1_GRAPH.md Option 1), then assemble the reel.

This is the *programmatic twin* of the participant-facing graph: identical
nodes and wiring, submitted via the API instead of clicked. The exported
workflow JSON for participants is generated from the same builder
(--export-workflow writes the first shot's graph in API format for reference).

    python tools/run_p1_local.py --project projects/demo_en [--host 127.0.0.1:8188]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoacts_core.project import MEDIA_DIRS  # noqa: E402


def build_chunk_workflow(image_name: str, csvs: dict[str, str], text: str,
                         prefix: str, fps: int) -> dict:
    """The frozen P1 shot chain — stock/Cloud-supported nodes only."""
    wf = {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
    }
    nid = 2
    param_refs = {}
    for key in ("w", "h", "x", "y"):
        wf[str(nid)] = {"class_type": "Basic data handling: StringSplitDataList",
                        "inputs": {"string": csvs[key], "sep": ",", "maxsplit": -1}}
        wf[str(nid + 1)] = {"class_type": "Basic data handling: CastToInt",
                            "inputs": {"input": [str(nid), 0]}}
        param_refs[key] = [str(nid + 1), 0]
        nid += 2
    wf["10"] = {"class_type": "ImageCrop+", "inputs": {
        "image": ["1", 0], "width": param_refs["w"], "height": param_refs["h"],
        "position": "top-left", "x_offset": param_refs["x"], "y_offset": param_refs["y"]}}
    wf["11"] = {"class_type": "ImageResize+", "inputs": {
        "image": ["10", 0], "width": 1080, "height": 1920,
        "interpolation": "lanczos", "method": "stretch",
        "condition": "always", "multiple_of": 0}}
    # DrawText+ must run in LIST domain: with a batched img_composite it
    # collapses the batch to one frame (verified 2026-07-24, GAPS.md #3).
    # Mapped per item it renders the same text on every frame.
    wf["13"] = {"class_type": "DrawText+", "inputs": {
        "text": text, "font": "ShareTechMono-Regular.ttf", "size": 44,
        "color": "#FFFFFF", "background_color": "#00000000",
        "shadow_distance": 2, "shadow_blur": 2, "shadow_color": "#000000",
        "horizontal_align": "center", "vertical_align": "bottom",
        "offset_x": 0, "offset_y": -420,  # safe-zone rough value, P1 only
        "direction": "ltr", "img_composite": ["11", 0]}}
    wf["12"] = {"class_type": "ImageListToBatch+", "inputs": {"image": ["13", 0]}}
    wf["14"] = {"class_type": "VHS_VideoCombine", "inputs": {
        "images": ["12", 0], "frame_rate": fps, "loop_count": 0,
        "filename_prefix": prefix, "format": "video/h264-mp4",
        "pix_fmt": "yuv420p", "crf": 19, "save_metadata": True,
        "trim_to_audio": False, "pingpong": False, "save_output": True}}
    return wf


def submit_and_wait(host: str, wf: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(f"http://{host}/prompt",
        data=json.dumps({"prompt": wf}).encode(),
        headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req).read())["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(urllib.request.urlopen(f"http://{host}/history/{pid}").read())
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed") or st.get("status_str") in ("success", "error"):
                if st.get("status_str") == "error":
                    msgs = [m[1].get("exception_message") for m in st.get("messages", [])
                            if m[0] == "execution_error"]
                    raise RuntimeError(f"execution error: {msgs}")
                return h[pid]
        time.sleep(1)
    raise TimeoutError(pid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--host", default="127.0.0.1:8188")
    # The pack lives in ComfyUI/custom_nodes/<this repo>, so the install is
    # two levels above it. Derived rather than written out: a path from one
    # machine is wrong on every other one, and this default used to be
    # exactly that.
    ap.add_argument("--comfy-root", type=Path,
                    default=Path(__file__).resolve().parents[3])
    ap.add_argument("--export-workflow", type=Path, default=None)
    ap.add_argument("--export-all", type=Path, default=None,
                    help="write every chunk graph (API format) to this dir and exit — "
                         "no server needed; use for the Cloud run")
    args = ap.parse_args()

    gen = args.project / "generated"
    doc = json.loads((gen / "shots.json").read_text(encoding="utf-8"))
    fps = doc["fps"]
    run_tag = f"memoacts_{args.project.name}"

    def chunk_graphs():
        for s in doc["shots"]:
            for stem in s["crops"]:
                csvs = {k: (gen / "crops" / f"{stem}.{k}.csv").read_text("ascii")
                        for k in ("w", "h", "x", "y")}
                yield stem, s, build_chunk_workflow(s["image"], csvs, s["text"],
                                                    f"{run_tag}/{stem}", fps)

    if args.export_all:
        args.export_all.mkdir(parents=True, exist_ok=True)
        manifest = []
        for stem, s, wf in chunk_graphs():
            (args.export_all / f"{stem}.json").write_text(json.dumps(wf, indent=2))
            manifest.append({"chunk": stem, "image": s["image"], "text": s["text"],
                             "frames": len((gen / "crops" / f"{stem}.x.csv")
                                           .read_text("ascii").split(",")),
                             "filename_prefix": f"{run_tag}/{stem}"})
        (args.export_all / "manifest.json").write_text(
            json.dumps({"project": args.project.name, "fps": fps,
                        "images": sorted({m["image"] for m in manifest}),
                        "chunks": manifest}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"exported {len(manifest)} chunk graphs to {args.export_all}")
        return 0

    # stage images into ComfyUI input
    for s in doc["shots"]:
        src = args.project / MEDIA_DIRS[0] / s["image"]
        shutil.copy2(src, args.comfy_root / "input" / s["image"])

    seg_dir = args.comfy_root / "output" / run_tag
    if seg_dir.exists():
        shutil.rmtree(seg_dir)

    t0 = time.time()
    n_jobs = 0
    for stem, _s, wf in chunk_graphs():
        if args.export_workflow and n_jobs == 0:
            args.export_workflow.write_text(json.dumps(wf, indent=2))
        submit_and_wait(args.host, wf)
        n_jobs += 1
        print(f"  rendered {stem}")
    render_s = time.time() - t0
    print(f"{n_jobs} segments in {render_s:.1f}s")

    narration = next(args.project.glob("narration.*"))
    out = args.project / "reel_p1.mp4"
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "assemble_reel.py"),
                        "--segments-dir", str(seg_dir),
                        "--narration", str(narration), "--out", str(out)],
                       capture_output=True, text=True)
    print(r.stdout or r.stderr)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
