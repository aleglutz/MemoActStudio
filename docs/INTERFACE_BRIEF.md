# Brief — the student-facing interface

Paste this file as the opening message of a new session. It is a brief, not a
specification: it says what the job is and what is already known, and leaves the
design to be made.

---

Planning session. Write `docs/PLAN.md` — the plan for making the assembly of a
reel understandable and usable by students. No implementation this session: the
deliverable is the plan itself.

Read `CLAUDE.md`, `HANDOFF.md`, then `SPEC.md` §0. The previous `docs/PLAN.md`
(2026-08-10) is **finished** — subtitles, `shots.csv`, animated maps and moving
bands all landed — so it goes to `archive/` and the new plan replaces it rather
than appending to it.

## The job

The September offline workshop **teaches `comfyui-memoacts` itself**: 16
students, two rented machines, local ComfyUI, practical rather than
overview-level. The interface is therefore not a nicety on top of the pipeline
— it is the thing being taught, and the deadline is weeks away. The August
online intensive is running right now on Comfy Cloud and must not be disturbed.

Definition of done for the plan: **a student, on a rented machine, with their
own script and their own recording, gets a rendered reel inside one session —
and can afterwards say what each step did and why it exists.** Both halves
count. Understanding without a rendered file is a lecture; a rendered file
without understanding is a black box, and either one fails the workshop.

"Teachable" is not the same as "complete". Everything that does not serve that
sentence is P3.

## The command line is not the interface

This is a standing decision by the project owner, made 2026-08-21, and it
reframes the work rather than removing one option from a list:

> CLI-first is my own setup. I cannot and do not want to teach it to anyone.

So `tools/` — `generate_shots`, `render_reel`, `render_move`, `render_bands`,
`render_map`, `assemble_reel` — and `README.md` with them, are **the author's
scaffolding and the reference implementation**, not teaching material. They stay,
they keep working, the interface may call into exactly the same `memoacts_core`
functions they call. But nothing a student sees, types or is examined on is a
terminal command. A plan that ends with "and then the student runs
`generate_shots.py`" has not done the job.

## What already exists — do not re-derive it

- `memoacts_core/` — 2 864 lines. align, caption, effects, normalize, project,
  render, schedule, shotlist, subs, video. This is the machinery, and it is
  interface-agnostic by construction.
- `tools/` — 2 900 lines of CLIs over that machinery. The reference
  implementation of every step, and the place to read what a step actually does.
- `nodes_*.py` — 871 lines, 14 registered nodes, **already V3** (`io.ComfyNode`
  / `io.Schema`, not one `INPUT_TYPES`): `MemoActsAlignShots`,
  `MemoActsRenderReel`, `MemoActsSubtitles`, `MemoActsSetMotion`,
  `MemoActsSetImage`, `MemoActsShotReport`, and seven effect nodes in
  `nodes/layers.py`. P2 extends this pack; there is nothing to migrate.
- `projects/legends_of_surrender/` — a finished 168.97 s reel that exercises
  every part of the machinery, with `REBUILD.md` regenerating every asset from
  the repository. The obvious worked example, and real work rather than a toy.
- `GAPS.md` — the P2 backlog as P1 left it. Re-read it against the September
  scope: some is now irrelevant, some has quietly been done.

The `comfyui-custom-node-skills` plugin is installed; use it for node work.
`comfyui-node-frontend` covers sidebar tabs, custom widgets, dialogs and
commands, so a panel inside ComfyUI is available as a shape, not only a graph.

## The tension the plan has to resolve

The pipeline is not uniformly graph-shaped, and pretending it is will produce
something worse than the CLI it replaces.

- **Compiling** — script plus recording in, `shots.json` out. One button, long
  running, nothing to look at while it works. A node suits this.
- **Rendering** — shots plus media in, a reel out. Also one button, and also
  the part where a graph shows its value, because effects and subtitles hang
  off it visibly.
- **Editing** — `shots.csv`: twenty rows of media, motion, focus, labels,
  credits. This is a *table*, and it is where the actual authorship happens. A
  node graph is poor at tables, and this is the step a student most needs to
  touch and understand.

So the plan's first decision is what the student touches for that middle part,
and how it connects to the two ends. Candidates worth weighing, and the plan
should pick and justify rather than hedge:

- a template workflow the student loads and edits, with the table handled by a
  custom widget or a sidebar panel;
- fewer, larger nodes — one per stage — so the whole path fits on one screen,
  against fine-grained nodes that teach the pipeline's anatomy;
- a ComfyUI frontend panel for editing, with the graph reduced to a runner;
- something else the machinery suggests once you have looked at it.

`SPEC.md` §0 carries the module priority for the September cut and names
`nodes/layers.py` (the six effect families) as the designated **first cut** if
time runs short. That is a standing decision, not a suggestion.

## Method

Plan mode. Present findings and the decision points **before** writing the plan,
not after. One clarifying question at a time. Anything the spec marks "verify"
or "evaluate" is a hypothesis to test — surfacing a contradiction is a
deliverable, not a delay.

Effort in working days on this machine, ordered by what unblocks the most for
the least — the shape the previous `PLAN.md` used, which worked.
