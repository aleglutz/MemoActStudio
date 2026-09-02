# HANDOFF — session state as of 2026-08-21, evening (supersedes the morning version)

Read `CLAUDE.md` and `SPEC.md` first, as always. This file is the delta. The
morning version recorded that `docs/PLAN.md` had been written and nothing
implemented. Since then **A through F of that plan are built and verified**, the
terminal is no longer on the path from a project folder to a rendered reel, and
**only G is left — none of which is code.**

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

**E — the cost of a look.** All six presets measured on this machine rather
than the two SPEC already carried: clean 23.9 s on the fixture, then `handheld`
2.6×, `archive_soft` 2.9×, `cold_document` 3.2×, `archive_harsh` 3.9×,
`newsreel` 4.0×. The two known figures came back unchanged, which is why the
four new ones can be trusted. `effects.COST` holds them; the editor prints them
beside each preset name.

**F — the things a student is handed.** `example_workflows/reel_stills.json`
(six nodes, titled with the sentence each one is, round-tripped through
ComfyUI's own loader), `projects/workshop_starter` (six sentences that explain
what the tool is doing to them while it does it, one source deliberately too
small), and `docs/WORKSHOP_HANDOUT.md` in the register of module03's handout —
with a "what you get, and what you don't" section, and no command in it.

**D — the focus picker.** Drag a rectangle over the thumbnail and it becomes the
`focus` triple, fitted to what the renderer will use rather than to what was
drawn. Verified through the pipeline, not only the panel: a focus drawn in the
browser and saved changed one line of `shots.csv`, read back as
`(0.525, 0.45, 0.769)`, and `schedule.compute` turned it into crops running
1404 → 1080 px — the 1.30× push-in the panel had promised. The author's file was
restored afterwards.

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

**Item G, and it is not a coding session.** Provision machine A by executing
`docs/WORKSHOP_MACHINE_SETUP.md` for the first time on a clean box, correcting
it as it fails — it was written from this dev machine by inspection and has
never been run. Extend its §6 to verify the *node* path rather than the CLI.
Then measure on the rented hardware: one clean render, one `archive_soft`
render, one alignment from cold. Those three numbers decide how long the
exercise project may be.

And put the four files `projects/workshop_starter` needs into the image — its
`REBUILD.md` names them. Nothing in the repository can do that: media is never
versioned, and one of the three pictures has to be too small on purpose.

**The rehearsal has not been run**, and it is the real test: someone who has not
seen this repository, their own script, their own `.wav`, three of their own
pictures, a stopwatch, and no terminal. If they cannot afterwards name the five
steps, the handout is not finished.

## Two things worth knowing before touching the UI

- **The Chrome extension's `navigate` tool cannot open `127.0.0.1:8188`** —
  it lands on an error page while `fetch` to the same origin from an already-open
  page succeeds. The way in is to open any other local page and set
  `location.href`. Not a ComfyUI problem: loopback, port and server were each
  ruled out separately.
- **Nothing outside the frontend can give a node a minimum size.** A DOM widget
  reports `{minWidth: 0}` for itself; `computeLayoutSize` cannot be overridden —
  not on what `addDOMWidget` returns, not on the widget from `node.widgets`, not
  later from a timeout — and `node.computeSize` is reassigned back over any
  override. Each was read back off the live node and each had reverted. A
  relayout can therefore shrink the node to a sliver; dragging it wide again is
  the cure, and the table scrolls inside whatever it is given.
- **The extension's synthesised drag does not reach a DOM widget.** The picker
  was exercised with dispatched `PointerEvent`s instead, which is what a real
  device sends.

## What is open, carried over unchanged

- **`New_York_May-8_1945.jpg` still has no `SOURCES.md` entry**, and its rights
  are unchecked. Carried from the previous three handoffs.
- Student work isolation on a shared machine, Whisper pre-seeding across an
  image, and the `--use-sage-attention` trap are all in `docs/WORKSHOP_MACHINE_SETUP.md` and all
  still undecided.
