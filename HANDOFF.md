# HANDOFF — session state as of 2026-08-21 (supersedes the 2026-08-20 version)

Read `CLAUDE.md` and `SPEC.md` first, as always. This file is the delta. The
August-20 version described a finished reel and a repository reorganised around
one `sources/` folder; that all still holds and none of it moved today. What
changed is that the interface finally has a plan, and that the survey behind it
contradicted something the previous handoff asserted.

## The short version

**`docs/PLAN.md` is new** — the plan for the student-facing interface, written
from `docs/INTERFACE_BRIEF.md`. Nothing was implemented. The previous plan is
`archive/20260810_PLAN.md`, finished rather than abandoned.

**The decision it makes:** the ComfyUI graph is the spine — five nodes, one
screen, one sentence each — and `shots.csv` is edited in a DOM-widget table
inside the middle node, against the same file the author edits by hand.

## The correction that matters

The 2026-08-20 handoff said the node pack is "already V3, so P2 extends it
rather than migrating it". True of the API, **misleading about scope.** The 14
nodes are a partial fork of the CLI that has drifted from it:
`memoacts_core.shotlist` is imported by no node at all, so three of the twelve
`shots.csv` columns are reachable from the graph; `align()` is called without
`display_blocks`, which would put digits-expanded text on screen; the subtitle
defaults are 420 / 0.55 against `SubStyle`'s 530 / 0.68; narration in `sources/`
is not found; `ShotReport` errors on a video shot.

**`legends_of_surrender` cannot be rendered from the graph today.** So the plan
starts with `memoacts_core/pipeline.py` — one orchestration layer that both
`tools/` and the nodes call — rather than with the table.

## What the survey established, so it is not re-derived

- `render.encode` taking any `Iterable[Image]` is the seam that gives progress,
  cancellation and single-shot preview without touching the core.
- `comfy.utils.ProgressBar.update_absolute(value, total, preview)` pushes a live
  frame into a running node, and `send_progress_text` a text line. The "long
  step with nothing to look at" objection to the graph is a property of the
  current nodes, not of ComfyUI.
- Frontend is 1.48.7; `addDOMWidget`, `registerSidebarTab` and custom aiohttp
  routes are all present, and `comfy-mtb` on this machine uses the last of them.
- There is no JavaScript in this repository yet. The table widget is the only
  new surface.

## Scope decided by the project owner, 2026-08-21

- Students arrive with **their own script, their own recording and their own
  images** — the full cycle.
- Per-shot **focus** and per-shot **effects** are in the September scope. That
  reverses SPEC §0's "`nodes_layers.py` is the designated first cut", which
  should be amended in `SPEC.md` when the next spec edit happens.

## What the next session does first

**Item A of `docs/PLAN.md`** — `memoacts_core/pipeline.py`, plus
`shotlist.write_shot_list`, plus the `effects` parameter on
`project.write_outputs` (schema 1.5). Then rewrite `tools/generate_shots.py` and
`tools/render_reel.py` on top of it, keeping every flag and every printed line.

The checkpoint is a byte-identical `generated/report.txt` for
`legends_of_surrender`, the same way the 2026-08-20 reorganisation was verified.

## What is open, carried over unchanged

- **`New_York_May-8_1945.jpg` still has no `SOURCES.md` entry**, and its rights
  are unchecked. Carried from the previous two handoffs.
- **`projects/demo_en`** renders but has not been run since the reorganisation.
- Student work isolation on a shared machine, Whisper pre-seeding across an
  image, and the `--use-sage-attention` trap are all in `HARDENING.md` and all
  still undecided.
