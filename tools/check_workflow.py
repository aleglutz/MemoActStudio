"""A saved workflow, checked against the nodes it names (SPEC 5.2d).

    python tools/check_workflow.py example_workflows/hook_page.json

A workflow file is two tables that have to agree with a third: links index
inputs and outputs by *position*, `widgets_values` is a bare list matched to
the widget inputs by *order*, and both are matched against node definitions
that live somewhere else entirely. Nothing checks that at save time, because
the editor writes files it has just built and they agree by construction. A
file written by hand does not, and the way it fails is quiet: a value lands on
the wrong widget and the graph runs with `keep_border = "fixed"`.

Which is the actual bug this exists because of. `io.Int.Input` has
`control_after_generate` off by default, `KSampler` turns it on for `seed`, and
a widget that has it carries a second entry in `widgets_values` right after its
own. Guessing that wrong shifts every value after it by one.

This checks the three things that shift silently:

    every link names nodes that exist, at slots that exist
    the two ends of a link agree about the type on it
    each node has exactly as many widget values as it has widget inputs,
        plus one for each widget that carries a control

It does not know what a node's widgets *are* -- only the file says that -- so
it cannot catch a value that is wrong while being in the right place. It
catches the shift.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: Widgets that carry a "control after generate" and so a second value. Read
#: off the installed definitions rather than assumed; add to this when a graph
#: brings in a node that sets it.
CONTROLLED = {
    ("KSampler", "seed"),
    ("KSamplerAdvanced", "noise_seed"),
    ("RandomNoise", "noise_seed"),
    ("MemoActsSfxPrompt", "index"),
    ("MemoActsSfxPrompt", "seed"),
}


def check(path: Path) -> list[str]:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids = {n["id"]: n for n in d.get("nodes", [])}
    bad: list[str] = []

    for entry in d.get("links", []):
        lid, src, sslot, dst, dslot, ltype = entry[:6]
        where = f"link {lid}"
        if src not in ids or dst not in ids:
            bad.append(f"{where}: names a node that is not in the file")
            continue
        a, b = ids[src], ids[dst]
        where = f"link {lid} {a['type']}.{sslot} -> {b['type']}.{dslot}"
        if sslot >= len(a.get("outputs", [])):
            bad.append(f"{where}: {a['type']} has no output {sslot}")
            continue
        if dslot >= len(b.get("inputs", [])):
            bad.append(f"{where}: {b['type']} has no input {dslot}")
            continue
        got = b["inputs"][dslot].get("type")
        if got != ltype:
            bad.append(f"{where}: carries {ltype} into a {got} socket")

    for n in d.get("nodes", []):
        if n["type"] in ("MarkdownNote", "Note", "Reroute"):
            continue
        widgets = [i["name"] for i in n.get("inputs", []) if "widget" in i]
        want = len(widgets) + sum((n["type"], a) in CONTROLLED for a in widgets)
        got = len(n.get("widgets_values", []))
        if want != got:
            bad.append(f"node {n['id']} {n['type']}: {got} widget values for "
                       f"{want} widgets {widgets} -- every value after the "
                       f"mismatch is on the wrong widget")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", type=Path, nargs="+")
    args = ap.parse_args()
    hurt = 0
    for p in args.workflow:
        bad = check(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"{p}  {len(d.get('nodes', []))} nodes, {len(d.get('links', []))} links")
        for line in bad:
            print(f"  {line}")
        print("  agrees" if not bad else f"  {len(bad)} problems")
        hurt += len(bad)
    return 1 if hurt else 0


if __name__ == "__main__":
    sys.exit(main())
