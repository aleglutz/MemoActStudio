"""A saved canvas workflow, turned into the shape `/prompt` accepts.

    python tools/workflow_to_api.py example_workflows/hook_page.json \
        --out web/hook_page_api.json

The editor saves a graph: nodes with positions, links as a separate table,
widget values as a bare list matched to widgets by order. `/prompt` wants
something else entirely -- a flat map of node id to {class_type, inputs}, with
widgets by name and links as [source_id, slot] pairs. The editor converts
between the two in the browser, which is no use to anything that is not a
browser: a script, a cron job, or an agent with no canvas in front of it.

The one thing to get right is the same thing that goes wrong when a workflow is
written by hand: a widget declaring `control_after_generate` carries a second
entry in `widgets_values` right after its own, and reading past it puts every
later value on the wrong widget. `check_workflow.CONTROLLED` is the list, read
off the installed node definitions.

Written into the pack's `web/` folder, the result is served at
`/extensions/MemoActStudio/<name>` -- same origin as the API, so a page open on
the ComfyUI server can fetch it and queue it without a file dialog.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_workflow import CONTROLLED

SKIP = {"MarkdownNote", "Note", "Reroute", "PrimitiveNode"}


def to_api(wf: dict) -> dict:
    nodes = {n["id"]: n for n in wf["nodes"] if n["type"] not in SKIP}
    # link id -> where it comes from
    src = {l[0]: [str(l[1]), l[2]] for l in wf.get("links", [])}

    out: dict = {}
    for nid, n in nodes.items():
        if n.get("mode") in (2, 4):          # muted or bypassed
            continue
        values = list(n.get("widgets_values") or [])
        inputs: dict = {}
        i = 0
        for slot in n.get("inputs", []):
            name = slot["name"]
            if "widget" in slot:
                if i < len(values):
                    inputs[name] = values[i]
                i += 1
                if (n["type"], name) in CONTROLLED:
                    i += 1               # the control's own value, not an input
            if slot.get("link") is not None:
                inputs[name] = src[slot["link"]]     # a wire beats the widget
        out[str(nid)] = {"class_type": n["type"], "inputs": inputs}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    api = to_api(json.loads(args.workflow.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(api, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out}  {len(api)} nodes")
    for nid, n in sorted(api.items(), key=lambda kv: int(kv[0])):
        wired = sum(isinstance(v, list) for v in n["inputs"].values())
        print(f"  {nid:>3} {n['class_type']:<32} {len(n['inputs'])} inputs, {wired} wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
