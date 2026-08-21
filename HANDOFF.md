# HANDOFF — session state as of 2026-08-21, evening (supersedes the morning version)

Read `CLAUDE.md` and `SPEC.md` first, as always. This file is the delta. The
morning version recorded that `docs/PLAN.md` had been written and nothing
implemented. Since then **A, B and C of that plan are built and verified**, and
the terminal is no longer on the path from a project folder to a rendered reel.

## The short version

The graph runs the reel now. `Project → Align → Shot Table → Subtitles →
Render Reel`, with the shot table drawn as a real table inside its node, editing
the same `shots.csv` the author edits by hand.

## What landed

**A — `memoacts_core/pipeline.py`.** Four calls: `read_project`,
`align_project`, `compose_project`, `render_project`. Everything `tools/` did
between `argparse` and `print` lives there, and both CLIs are now thin over it.
One `progress(stage, done, total, message, preview)` callback carries the
human-readable lines, already phrased, so the CLI and the nodes cannot describe
the same fact two ways. `render.render_reel` grew an `on_frame` hook.

Also: `shotlist.read_table` / `write_table` / `edits_from_table` /
`rows_with_edits` (the shot list, round-trippable), and **schema 1.5** — per-shot
`effects`, a column that had been parsed and thrown away since it was invented
because `write_outputs` had nowhere to put it.

**B — the five nodes.** Every divergence catalogued in `docs/PLAN.md` is gone by
construction. Render reports progress frame by frame with the frame attached;
that also buys cancellation for nothing, because ComfyUI's progress hook throws
if the user pressed Cancel. `MemoActs — Preview Shot` renders one shot in
seconds. `MemoActsShotReport` is gone — the table prints the real `report.txt`.

**C — the table widget.** `web/memoacts.js` plus routes under `/memoacts/`.
Media is a picker whose every option carries its own `max_zoom`, so the
resolution guard is a choice at selection time rather than a warning after the
render — which is what `GAPS.md` has been asking for.

## What it was checked against

- `legends_of_surrender`: `report.txt` identical line for line except its schema
  number, `shots.json` longer by exactly the 20 new `effects: null`, `reel.ass`
  identical byte for byte, and the render matching frame count and duration to
  the microsecond — **4 925 frames, 164.167007 s**. (5 069 / 168.97 is
  `reel_with_hook.mp4`, a different artefact.)
- The graph on the running server: 16 nodes exposed, a prompt through `/prompt`
  returns `success`, `demo_en` renders 415 frames, drift +1 ms, with a subtitle
  track byte-identical to the CLI's.
- The widget in a browser: 20 rows, thumbnails, and the detail strip reporting
  `max_zoom 0.42×` on the KAPFILM footage — the same number the render warns
  with. GET then POST with no edits leaves `git diff` clean; two edits change
  exactly two lines.

## What the next session does first

**Item D of `docs/PLAN.md`** — the focus picker: drag a rectangle on the
thumbnail, write the `focus` triple, update `max_zoom` and `clamped` live. The
detail strip is already the place it goes and already computes what it needs.

E is nearly closed by A and C (schema, renderer, per-row dropdown); what is left
is showing the render-cost multiplier on the row. Then **F** — the template
workflow, a short starter project, and the handout in the register of
`projects/module03/HANDOUT.md` — and **G**, machine A.

## Two things worth knowing before touching the UI

- **The Chrome extension's `navigate` tool cannot open `127.0.0.1:8188`** —
  it lands on an error page while `fetch` to the same origin from an already-open
  page succeeds. The way in is to open any other local page and set
  `location.href`. Not a ComfyUI problem: loopback, port and server were each
  ruled out separately.
- **A DOM widget reports `{minWidth: 0}`**, and `computeLayoutSize` cannot be
  overridden to say otherwise — not on what `addDOMWidget` returns, not on the
  widget looked up from `node.widgets`, not later from a timeout. So a node
  holding a table can be dragged narrower than its columns; the table scrolls
  inside it instead.

## What is open, carried over unchanged

- **`New_York_May-8_1945.jpg` still has no `SOURCES.md` entry**, and its rights
  are unchecked. Carried from the previous three handoffs.
- Student work isolation on a shared machine, Whisper pre-seeding across an
  image, and the `--use-sage-attention` trap are all in `HARDENING.md` and all
  still undecided.
