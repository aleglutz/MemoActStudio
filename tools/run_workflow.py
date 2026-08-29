"""Queue an API-format workflow on a running ComfyUI and wait for it.

    python tools/run_workflow.py docs/workflows/paper_plate_api.json
    python tools/run_workflow.py docs/workflows/pencil_67_api.json --set sample.seed=1234

The graphs in `docs/workflows/` are API format -- the shape `/prompt` takes,
not the shape the canvas saves -- so the UI's Load will not open them and this
is how they run. Keys beginning with an underscore are notes to whoever reads
the file and are stripped before the graph is sent; that is the only reason the
notes can live in the same file as the graph.

`--set node.input=value` overrides one input without editing the file, which is
what a reroll is: `--set sample.seed=7`. Values are read as JSON where they
parse and as strings where they do not, so `--set sample.cfg=1.5` is a number
and `--set save.filename_prefix=plate/try2` is not.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SERVER = "http://127.0.0.1:8188"


def _api(server: str, path: str, payload: dict | None = None) -> dict:
    """A call, and on a rejection the *reason* rather than the status line.

    `/prompt` answers a graph it will not run with 400 and a body naming the
    node and the input, which is the only useful thing in the exchange. urllib
    raises on 4xx and throws that body away unless it is read off the exception,
    so a first pass of this tool turned "LoadImage corner: no such image" into
    "HTTP Error 400: Bad Request" and sent the reader to the server log.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{server}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: HTTP {e.code} {e.reason}")
        print(f"{path}: HTTP {e.code} -- {body.get('error', {}).get('message', e.reason)}")
        for node, err in (body.get("node_errors") or {}).items():
            for d in err.get("errors", []):
                print(f"  node {node}: {d.get('message')}  {d.get('details', '')}")
        raise SystemExit(1)


def strip(graph: dict) -> dict:
    """The graph without the notes. Underscored keys never reach the server."""
    out = {}
    for k, v in graph.items():
        if k.startswith("_"):
            continue
        out[k] = {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", type=Path)
    ap.add_argument("--server", default=SERVER)
    ap.add_argument("--set", action="append", default=[], metavar="NODE.INPUT=VALUE")
    ap.add_argument("--timeout", type=float, default=1800)
    args = ap.parse_args()

    graph = strip(json.loads(args.workflow.read_text(encoding="utf-8")))
    for spec in args.set:
        key, _, raw = spec.partition("=")
        node, _, field = key.partition(".")
        if node not in graph:
            raise SystemExit(f"no node {node!r} in {args.workflow}")
        try:
            graph[node]["inputs"][field] = json.loads(raw)
        except json.JSONDecodeError:
            graph[node]["inputs"][field] = raw
        print(f"  set {node}.{field} = {graph[node]['inputs'][field]!r}")

    try:
        stats = _api(args.server, "/system_stats")
    except urllib.error.URLError as e:
        raise SystemExit(f"no ComfyUI at {args.server}: {e}")
    dev = (stats.get("devices") or [{}])[0]
    print(f"server up: {dev.get('name', '?')}  "
          f"{dev.get('vram_free', 0) / 2**30:.1f} GB free of "
          f"{dev.get('vram_total', 0) / 2**30:.1f}")

    cid = str(uuid.uuid4())
    r = _api(args.server, "/prompt", {"prompt": graph, "client_id": cid})
    if "prompt_id" not in r:
        raise SystemExit(f"rejected: {json.dumps(r)[:2000]}")
    pid = r["prompt_id"]
    print(f"queued {pid}")

    t0 = time.time()
    while time.time() - t0 < args.timeout:
        hist = _api(args.server, f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                for m in status.get("messages", []):
                    print(f"  {m}")
                raise SystemExit("run failed")
            files = [f"output/{o.get('subfolder','')}/{o['filename']}".replace("//", "/")
                     for out in entry.get("outputs", {}).values()
                     for o in out.get("images", [])]
            print(f"done in {time.time() - t0:.0f}s")
            for f in files:
                print(f"  {f}")
            return 0
        time.sleep(3)
    raise SystemExit(f"still running after {args.timeout}s; check the queue")


if __name__ == "__main__":
    raise SystemExit(main())
