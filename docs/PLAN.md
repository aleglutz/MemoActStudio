# Work plan — the interface students are taught

Written 2026-08-21, from `docs/INTERFACE_BRIEF.md`. Replaces the 2026-08-10
plan, which the project owner confirmed finished on 2026-08-20 — subtitles,
`shots.csv`, animated maps and moving bands all landed. It is kept as
`archive/20260810_PLAN.md` for its reasoning.

## Context

The September offline workshop teaches `comfyui-memoacts` itself — 16 students,
two rented machines, local ComfyUI, practical rather than overview-level. The
project owner ruled on 2026-08-21 that **the command line is not the teaching
surface**: `tools/` and `README.md` stay as the author's scaffolding and the
reference implementation of every step, but nothing a student sees, types or is
examined on is a terminal command.

Definition of done: *a student, on a rented machine, with their own script and
their own recording, gets a rendered reel inside one session — and can
afterwards say what each step did and why it exists.* Confirmed 2026-08-21:
students arrive with **their own script, their own recording and their own
images** — the full cycle, not a prepared project.

Deadline is weeks away. The August online intensive is running right now on
Comfy Cloud and nothing here touches it.

---

## What the survey found — three facts that set the order of work

### 1. The node pack is a drifted fork, not a base to extend

The 2026-08-20 handoff records that the pack is "already V3, so P2 extends it
rather than migrating it". That is true of the API and **misleading about
scope**, and the correction is the most consequential finding behind this plan.

The 14 nodes cover `Align → Set Motion / Set Image → Subtitles → Render` and
nothing else. `memoacts_core.shotlist` is imported by **zero** node files, so of
the twelve columns of `shots.csv` exactly three are reachable from the graph.
Where the two paths overlap they have drifted apart:

| Divergence | Consequence |
|---|---|
| `MemoActsAlignShots` calls `aligner.align(...)` with **three** args, omitting `display_blocks` | `Span.words` carry the digits-expanded text, so segmented captions would burn "two thousand and fifteen" onto the screen — against the project's own non-negotiable |
| Its local `_find_narration` globs `<project>/narration.*` only | A narration in `sources/`, which is where the layout puts it, is not found |
| Node defaults `margin_v=420`, `plate_opacity=0.55` | `subs.SubStyle` carries 530 / 0.68, and `render_reel.py --plate` says in its own help text that "the two must not drift apart" |
| No credits, no `focus` setter, no `shots.csv`, no `words`, no `image_path`, no `clamped` / `max_zoom`, nothing written to disk | `MemoActsSetMotion` carefully preserves a `motion.focus` that nothing can set |
| `MemoActsShotReport` opens media with bare PIL | A video-backed shot reports `IMAGE ERROR` |

**`legends_of_surrender` cannot be rendered from the graph today.** So the first
item of work is not the table — it is one shared orchestration layer that both
`tools/` and the nodes call, after which this class of drift cannot recur.

### 2. The core already has the seams an interface needs

Zero `print` / `argparse` / `sys.exit` across all ten modules; warnings come
back as `list[str]` (`resolve_shot_images`, `apply_shot_list`) or through
`warnings.warn`, which a GUI can capture. What looks missing — progress,
cancellation, preview — falls out of one signature:

- `render.encode(frames: Iterable[Image], ...)` takes **any** iterable, so a
  counting wrapper around `reel_frames` gives progress per frame (the total is
  known: `sum(len(s.schedule.ws) for s in shots)`) and cancellation by raising
  out of it.
- `render.shot_frames(shot)` is public and standalone → **single-shot preview**.
  `next(iter(shot_frames(shot)))` is frame 0, with no ffmpeg at all for a still.
- `schedule.compute` is pure math → a crop rectangle can be drawn over a
  thumbnail with nothing rendered.
- `subs.build_ass` / `cues_from_shots` / `check_wrap` are pure string work → a
  live caption preview is free.

The one genuinely opaque step is `StableTsAligner.align()`: a single call into
stable-whisper, not interruptible, no callback, and on first run it downloads
the model. An indeterminate progress line is the honest maximum there.

### 3. ComfyUI on this machine supplies the rest

Frontend `1.48.7`. Verified present in this install: `registerSidebarTab`,
`addDOMWidget`, `registerCustomWidget`; custom aiohttp routes through
`PromptServer.instance.routes` (`comfy-mtb` uses them on this very box); and
`comfy.utils.ProgressBar.update_absolute(value, total, preview)`, which pushes a
**live preview image into the running node**, alongside `send_progress_text` for
a per-node text line.

That settles the brief's central tension in the graph's favour: "one button,
long running, nothing to look at while it works" is not a property of the graph,
it is a property of the current nodes. A render node can show frames as they are
made.

There is no JavaScript anywhere in the repository today — no `WEB_DIRECTORY`, no
widget, no `pyproject.toml`. The table widget is the only genuinely new surface.

---

## The decision: the graph is the spine, the table is a widget inside one node

Five nodes, left to right, on one screen. Each is one sentence a student can
repeat, which is the *understanding* half of the definition of done:

| Node | The sentence | Why it is a node |
|---|---|---|
| **MemoActs — Project** | "This is my material." | Names the folder and shows what was found: the narration and its length, the image count, the script's blocks. Holds `script.md` in a multiline widget that loads and saves — the script is ground truth, so it is visible in the graph |
| **MemoActs — Align** | "My words become timings." | Slow, cached, run once. Its `fingerprint_inputs` is the mtime of `script.md` + the narration only, so editing the shot table never re-runs Whisper |
| **MemoActs — Shot Table** | "I decide what is seen." | The DOM-widget table. Applies `shots.csv` onto the alignment, writes `generated/shots.json` + `report.txt`, emits SHOTS |
| **MemoActs — Subtitles** | "The words become captions." | Style, and the visible proof that the script — not a transcription — is what reaches the screen |
| **MemoActs — Render** | "The reel is made." | Progress bar, live frames, and the finished MP4 playing in the node |

**Why not a sidebar panel.** It would duplicate project state, split attention
away from the thing being taught, and cost more code. The graph's job here is
pedagogical: five nodes is the syllabus.

**Why not fine-grained nodes.** Twenty shots by six decisions is 120 widgets. A
table is the right instrument for a table.

**Why not one big node.** A student who cannot point at the step cannot say what
it did.

**Alignment is split from composition, deliberately.** Today
`generate_shots.py` does both in one pass, so a one-character edit to
`shots.csv` costs a full Whisper run. Splitting them, and letting V3's
`fingerprint_inputs` cache the alignment, is what makes the edit loop survive a
workshop rotation.

The table widget reads and writes **the same `shots.csv` the author edits by
hand** — one artefact, two doors. `#` comment rows, unknown columns and the
`notes` field (which in `legends_of_surrender` carries rebuild commands) must
survive a round trip verbatim.

*Built differently, 2026-08-21:* a write goes to a temp file and replaces the
original, rather than keeping a `.bak` as planned. A backup is one copy of one
previous state and needs a policy for when it is cleared; an atomic replace
means the file is never half-written in the first place, which is the failure
that would actually cost an author their edit decisions. Cells are also handed
back to the widget exactly as spelled rather than as parsed — an in-point
written `0:40` types to `40.0`, and returning that would rewrite the file for
no reason anyone asked for.

---

## What is in scope for the student, decided 2026-08-21

Media · motion (preset / rate / anchor) · **focus** · label · credit ·
**per-shot effects** · notes. Captions styled globally.

Two consequences, recorded rather than discovered later:

1. **This reverses SPEC §0's "`nodes_layers.py` is the designated first cut".**
   Deliberate, like the `nodes_video.py` reinstatement of 2026-08-11. SPEC §0
   is amended, not ignored.
2. **Effects cost three to four times the render time** (SPEC §5.4: 23 s clean,
   71 s `archive_soft`, 104 s `newsreel` on demo_en) against a rotation of ~8
   students per machine. The mitigations are in the plan — single-shot preview,
   a deliberately short exercise project, and a measured figure from the real
   rented hardware before the day. If the measurement says no, effects are the
   second thing cut.

Out of scope for September, stated so it is not rediscovered: maps, bands, page
moves and page rendering (`render_map`, `render_bands`, `render_move`,
`render_page`, `rebuild_media`) stay **author-only CLI tools**. Assembly
(`assemble_reel`) and the P1 Cloud path (`run_p1_local`) likewise.

*Side effect worth banking:* if composites are not taught, the workshop image
does not need `ComfyUI-Olm-DragCrop`, and the redistribution-licence blocker on
imaging machine A (`HARDENING.md`, `SURVEY.md §3`) retires without a decision
having to be made.

---

## The work, ordered by what unblocks the most for the least

Effort is in working days on this machine.

### A. `memoacts_core/pipeline.py` — one orchestration, two doors — **DONE 2026-08-21**

Three functions carrying everything `tools/generate_shots.py` and
`tools/render_reel.py` do between `argparse` and `print`:

```python
def align_project(project, *, lang, model, fps, lead_ms,
                  use_aligner=True, progress=None) -> Alignment
def compose_project(project, alignment, *, fps, lead_ms,
                    write=True, progress=None) -> Composition   # doc, warnings, report
def render_project(project, doc, *, opts, progress=None) -> RenderResult
```

`progress` is one callable — `progress(stage, done, total, message, preview=None)`
— defaulting to `None`. The CLIs pass a printer, the nodes pass a `ProgressBar`
adapter, and nothing in the core learns about either.

`tools/generate_shots.py` and `tools/render_reel.py` are then rewritten as
argparse plus one call plus printing. They keep every flag and every printed
line; they remain the reference implementation, and they become *demonstrably*
the same code path the students run.

Also in A, because they are the same edit:

- `shotlist.write_shot_list(path, edits)` — the round-tripping writer the widget
  needs, preserving comments and unknown columns. Only `write_template` exists
  today.
- `project.write_outputs` grows an `effects` parameter; `SCHEMA_VERSION` → `1.5`,
  additive (`null` on every shot a 1.4 file has), documented in
  `docs/SHOTS_SCHEMA.md` in the style of its 1.1–1.4 entries.
- `render_project` reads per-shot effects from the doc instead of applying one
  global preset to everything.

**Checkpoint:** `legends_of_surrender` re-renders and its `report.txt` comes
back byte-identical. The 2026-08-20 reorganisation was verified exactly this
way.

### B. The five nodes, rebuilt on the spine — **DONE 2026-08-21**

`nodes_align.py`, `nodes_shot.py`, `nodes_subs.py` and `nodes_encode.py` call
`pipeline`, and every divergence in the table above disappears by construction.
New: `MemoActsProject`; and the `Shots` payload carries the whole `shots.json`
document plus its project directory.

- Render gets `ProgressBar` plus a live preview frame every N frames, and the
  finished MP4 in `ui.PreviewVideo` — already the pattern in `nodes_encode.py`.
- Align gets `send_progress_text`: model load, then an indeterminate line, which
  is all that call permits.
- **`MemoActs — Preview Shot`** — one shot number, renders that shot only, video
  preview in the node. This is the iteration loop that keeps a four-minute reel
  render out of a student's edit cycle, and it is why the rotation budget works.
- Warnings from `resolve_shot_images`, `apply_shot_list` and
  `warnings.catch_warnings` merge into one panel on the Shot Table node.

**Checkpoint, and the fallback if C runs late:** at the end of B the whole reel
is renderable from the graph with `shots.csv` edited in Notepad. That is already
a terminal-free path — not a good one, but a shippable one.

### C. The shot-table widget — **DONE 2026-08-21**

`web/` plus `WEB_DIRECTORY`, and routes under `/memoacts/`:

| Route | Purpose |
|---|---|
| `GET /projects`, `POST /project` | list; create the four-folder skeleton |
| `GET` / `POST /script` | `script.md` load and save |
| `GET` / `POST /shots` | `shots.csv` as JSON rows, via `read_shot_list` / `write_shot_list` |
| `GET /media` | media across `MEDIA_DIRS` with pixel size and computed `max_zoom` |
| `GET /thumb` | cached thumbnail |

The widget: one row per shot; columns media (a picker, not free text — today's
`MemoActsSetImage` takes an unvalidated string), motion, rate, anchor, label,
credit, notes; per-row badges for `confidence`, cue drift, `max_zoom`,
`clamped` / `UPSCALED n×`, and missing media. Selecting a row shows the
thumbnail and that shot's text.

Media arrives through the file manager, documented in the handout — the ban is
on the command line, not on Explorer. A drag-and-drop upload route is a
nice-to-have, not scope.

### D. Focus picker on the thumbnail — **DONE 2026-08-21**

Drag a rectangle over the thumbnail; it writes the `focus` triple that
`shots.csv` already accepts and `schedule.focus_window` already validates.
`max_zoom` and `clamped` update live as the rectangle moves.

This is `GAPS.md`'s standing request — *"the P2 GUI should surface `max_zoom`
per shot at selection time, so the warning becomes a choice rather than a
report"* — and it is the most legible moment in the whole interface: the student
watches the resolution guard refuse them, on their own photograph.

Reference patterns for an in-node canvas widget are installed on this machine
(`ComfyUI-Olm-DragCrop`, `comfyui-enricos-nodes`). Read them; do not vendor
them.

### E. Per-shot effects in the table — **mostly landed with A and C**

The `effects` column reaches the renderer for the first time (schema 1.5, from
A), a preset dropdown per row from `sorted(effects.PRESETS)`, and the seven
effect nodes remain the "build your own look" path for students who get that
far. The row shows the render-cost multiplier, because that number is a teaching
point rather than a footnote.

### F. Template workflow, starter project, handout (≈1.5 days)

- `example_workflows/reel_stills.json` — the five nodes, wired, saved as the
  workflow a student opens.
- `projects/workshop_starter/` — a deliberately short fixture (30–45 s) that
  renders inside a rotation slot: `script.md`, three images, a recording.
- `docs/WORKSHOP_HANDOUT.md`, in the register of
  `projects/module03/HANDOUT.md`: numbered steps, a table per run, and an
  explicit **"what you get, and what you don't"** section. That section is where
  the *understanding* half of the definition of done is actually delivered.
- `legends_of_surrender` is the worked example shown in the room, not rebuilt
  there.

### G. Machine A, and the numbers that decide the exercise (≈1 day + owner time)

`docs/WORKSHOP_MACHINE_SETUP.md` §7 already admits that its §6 verifies the core
library and the CLI, not the nodes students will use. Extend §6 to the node
path, then execute the document on a clean box for the first time and correct it
as it fails.

Measure on the actual rented hardware: one clean render, one `archive_soft`
render, one alignment from cold. Those three numbers decide the exercise
project's length. **If a render eats a meaningful slice of a rotation slot, cut
the project's length rather than discovering it live** — the setup document
already says so; now there is a figure to apply it to.

---

## Recommended order, and where it stands

1. ~~**A** — the spine.~~ **Done 2026-08-21.**
2. ~~**B** — the five nodes.~~ **Done 2026-08-21. The terminal-free path exists.**
3. ~~**C** — the table widget.~~ **Done 2026-08-21**, seen working in a browser.
4. ~~**D** — focus picker.~~ **Done 2026-08-21**, and `schedule.focus_limits`
   now states the rule next to the code that enforces it.
5. **E** — per-shot effects. Mostly landed with A (schema 1.5, the column
   reaching the renderer) and C (a preset per row). What is left is the
   cost multiplier shown on the row — hours, not a day. **Next.**
6. **F** — template, starter project, handout. 1.5 d.
7. **G** — machine A and the measurements. 1 d.

A, B, C and D took one day rather than eight and a half, largely because
`memoacts_core` was already interface-agnostic and the drift, once named, was
mechanical to remove. What remains is the tail of E, then F and G — the
teaching material and the machines, which is the half no amount of code
substitutes for.

## What this plan does not touch

The August intensive. `docs/P1_GRAPH.md`, `docs/PARTICIPANT_GRAPH_RECIPE.md`,
`projects/module03/`, `tools/run_p1_local.py` and the exported Cloud graphs are
untouched by every item above. The Cloud path and the local pack share
`memoacts_core` only through `MEDIA_DIRS` and the P1 crop CSVs, and A preserves
both.

## Still open, carried forward

- **Student work isolation** and machine reset between rotations
  (`HARDENING.md`) — unresolved, and it lands in the same folder tree the
  Project node creates. Decide before imaging.
- **Whisper model pre-seeding:** confirm where it caches and that the cache
  survives imaging under a different user account
  (`WORKSHOP_MACHINE_SETUP.md` §3.5 ⚠).
- **`--use-sage-attention`** must be absent from the rented machines' launch
  command (`HARDENING.md` — it renders silent black frames).
- **`New_York_May-8_1945.jpg`** still has no `SOURCES.md` entry and its rights
  are unchecked.

---

## Verification

1. **No regression.** After A,
   `python tools/render_reel.py --project projects/legends_of_surrender`
   produces the same 20 shots, **4 925 frames, 164.167 s**, and
   `generated/report.txt` is byte-identical to the file it replaces apart from
   its schema line. (5 069 frames / 168.97 s is `reel_with_hook.mp4`, the reel
   behind its 4.80 s cold open — a different artefact, assembled afterwards.)
   **Done 2026-08-21:** report identical line for line, `reel.ass` identical
   byte for byte, and the MP4 matches on frame count and duration to the
   microsecond.
2. **Parity.** The same project rendered from the graph and from the CLI agrees
   on frame count, duration and drift, and both reports agree.
3. **Cold start.** Restart ComfyUI, open `example_workflows/reel_stills.json`,
   render `projects/demo_en`: 4 shots, 415 frames, 13.833 s, and the one
   expected `03_small.png` enlargement warning, which is correct behaviour.
4. **Round trip.** Open `legends_of_surrender`'s `shots.csv` in the widget and
   save it unedited; `git diff` is empty — comments, quoting and the rebuild
   commands in `notes` all survive.
5. **The rehearsal, which is the real test.** Someone who has not seen this
   repository takes their own script, their own `.wav` and three of their own
   images and produces a reel, with a stopwatch running and no terminal open. If
   they cannot afterwards name the five steps, F is not finished.
6. **Both machines agree.** Identical frame count and duration for the same
   input (`WORKSHOP_MACHINE_SETUP.md` §6.4).
