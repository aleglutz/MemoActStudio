"""Run a Module 03 workflow over a long clip, one chunk of frames at a time.

Why chunks: the level-3 graph holds every frame's 4x intermediate in VRAM at
once, and one 4272x3200 float32 frame is 164 MB. Thirty frames is the largest
unit that fits comfortably beside the model on a 24 GB card. Level 4 chunks for
a different reason -- a diffusion pass per frame is simply slow, and a chunk
that fails should cost a second, not an hour.

The same shape is what the Cloud graphs already use (docs/PARTICIPANT_GRAPH_
RECIPE.md), for a third reason again: Cloud kills a job that runs much past
half a minute. Three environments, three causes, one answer.

Usage:
    python tools/module03_render.py <workflow.json> --frames 900 --chunk 30 \
        --loader-node 1 --save-node 5 --prefix module03/L3/
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

SERVER = "http://127.0.0.1:8188"  # overridden by --server


def set_server(url):
    global SERVER
    SERVER = url.rstrip("/")


def post_prompt(graph):
    body = json.dumps({"prompt": graph}).encode()
    req = urllib.request.Request(
        SERVER + "/prompt", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        return json.load(urllib.request.urlopen(req))["prompt_id"]
    except urllib.error.HTTPError as exc:
        # ComfyUI returns the validation failure as a JSON body; without it the
        # only thing on screen is "HTTP 400", which says nothing about which
        # node's input was wrong.
        sys.exit("submit rejected:\n" + exc.read().decode(errors="replace"))


def free():
    """Drop models and cached tensors between chunks.

    Without this the server's host memory climbs across a long run until an
    upscale allocation fails -- and on this machine it did not fail cleanly, it
    took the process down with a segfault inside the upscale node. Chunking
    bounds the peak of one chunk; only this bounds the sum of them.
    """
    body = json.dumps({"unload_models": True, "free_memory": True}).encode()
    req = urllib.request.Request(
        SERVER + "/free", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req).read()
    except Exception:
        pass  # advisory only; a refused free is not a reason to stop rendering


def wait(prompt_id, timeout=900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = json.load(urllib.request.urlopen(f"{SERVER}/history/{prompt_id}"))
        if prompt_id in hist:
            status = hist[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                sys.exit("run failed:\n" + json.dumps(status, indent=2)[:2000])
            return hist[prompt_id]
        time.sleep(1.0)
    sys.exit(f"timed out after {timeout}s waiting for {prompt_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--frames", type=int, required=True, help="total frames to cover")
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--start", type=int, default=0, help="first frame (for resuming)")
    ap.add_argument("--loader-node", default="1", help="node holding skip_first_frames")
    ap.add_argument("--save-node", default="5", help="node holding filename_prefix")
    ap.add_argument("--prefix", required=True, help="output prefix, chunk id appended")
    ap.add_argument(
        "--server",
        default=SERVER,
        help="ComfyUI to submit to. A second instance on another port lets this "
        "run with --disable-pinned-memory --cache-none without disturbing "
        "whichever server the user already has open on 8188.",
    )
    args = ap.parse_args()
    set_server(args.server)

    base = json.load(open(args.workflow, encoding="utf-8"))
    started = time.time()
    for offset in range(args.start, args.frames, args.chunk):
        graph = json.loads(json.dumps(base))
        graph[args.loader_node]["inputs"]["skip_first_frames"] = offset
        graph[args.loader_node]["inputs"]["frame_load_cap"] = min(
            args.chunk, args.frames - offset
        )
        # Zero-padded so the frames sort into order on disk; ffmpeg's glob
        # pattern is the only thing that reassembles them later.
        graph[args.save_node]["inputs"]["filename_prefix"] = f"{args.prefix}{offset:05d}"
        wait(post_prompt(graph))
        free()
        done = offset + args.chunk
        rate = (time.time() - started) / max(done - args.start, 1)
        print(
            f"  {min(done, args.frames):4d}/{args.frames} frames"
            f"  {rate:5.2f} s/frame"
            f"  eta {rate * (args.frames - done) / 60:5.1f} min",
            flush=True,
        )


if __name__ == "__main__":
    main()
