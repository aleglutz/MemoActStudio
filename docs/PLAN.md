# Work plan — three workflows, one project folder

**Written 2026-08-29.** Supersedes `archive/20260821_PLAN.md`, whose items A–F
are built and verified and whose item G is carried forward here unchanged.

## Why this plan replaces the last one

The 2026-08-21 plan described **one graph**. Since it was written, two node
families landed that do not fit in one graph — sound (4 nodes, 2026-08-24) and
the page (7 nodes) — and a third body of work, voiceover post-processing, grew
up *outside this repository altogether* in `ComfyUI/custom_nodes/memoacts_audio/`.

The count, taken off the running server on 2026-08-29: **27 MemoActs nodes are
registered on this machine, 16 of them are in git, and 7 more are in a folder
that is not a git repository at all.** That is the state this plan starts from,
and closing that gap is the first item in it.

---

## The shape

Three workflows, opened in this order, each finishing before the next begins:

| # | Workflow | The sentence | Rhythm | What it leaves in the project |
|---|---|---|---|---|
| **1** | **Sound** | "This is my voice, as I want it heard" | once per take | `sources/narration.wav` |
| **2** | **Reel** | "This is the film" | once per edit | `out/reel.mp4` |
| **3** | **Generation** | "This is a thing that did not exist" | once per item, batched | `sources/composites/`, `sources/sfx/`, `sources/images/` |

Workflow 3 is open-ended by design: the page is its first tenant, textures and
whatever else MemoActStudio grows are the next. It is not a fixed graph but a
place in the order.

**The project folder is the bus.** The output of workflow 1 becomes the input of
workflow 2 not through a wire but through a file, and this is already how the
pack is built: the `PROJECT` socket carries a path and nothing else, and every
node re-reads the folder. A wire dies when ComfyUI restarts. A folder does not,
which is what lets a student record on Tuesday and edit on Wednesday.

---

## The four decisions taken 2026-08-29

### 1. Three workflows, not one canvas

Three reasons, none of them taste:

- **The alignment cache.** `MemoActsAlign.fingerprint_inputs` keys on the mtime
  of `script.md` and of the recording. A processing chain that rewrites the
  recording on every Run changes that mtime on every Run, and buys the student a
  90-second re-alignment for turning an EQ knob. Splitting the graphs is what
  makes the cache mean what it says.
- **Arity.** Workflow 3 runs on batch count — one queued run walks a whole
  table, `index` on increment. Workflow 2 runs exactly once. They cannot share a
  Run button; one of them would always be wrong.
- **The cost of Run.** Pressing Run on a five-minute render to hear a
  two-second sound is bad teaching before it is bad engineering.

### 2. The seams are nodes, not file management

The bus is a folder, but nobody may be asked to *carry* anything to it. A
student who has to drag a `.wav` out of `ComfyUI/output/` into
`projects/<name>/sources/` is doing a terminal's work with a mouse, which is
what `docs/INTERFACE_BRIEF.md` exists to forbid.

Today there is exactly one missing seam: **nothing writes the narration into the
project.** Workflow 1 ends in an `AUDIO` socket, and `SaveAudio` puts it in the
wrong folder under the wrong name. That is item I below, and it is the only new
node the three-workflow shape requires.

### 3. The script loses its timecodes

A student's script is scene headings and nothing else:

```markdown
## S01
The 8th of May. And the 9th.

## S02
One long day here opened a fork that still runs across Europe.

## S03
```

**This costs no code.** `parse_script_shots` already supports the storyboard
layout (`_SHOT_HEADING_RE = ^#{1,6}\s*S\s*(\d+)\b`, case-insensitive); `cue` is
`Optional` the whole way down; `write_outputs` omits the cue and drift columns
when there is no cue, and reports "exactly as it did before the column existed".
`shots.csv` already addresses a row by number as readily as by timecode. Item J
is documentation and fixtures, not implementation.

What is gained: the drift column disappears, and with it the whole class of
silent failure this project has just walked into — see K. What is lost: nothing
a student can use. Drift measures the read against a timecode the author wrote
*before* recording, and a student writes no such timecode.

**The one trap, and it must be said out loud in the handout:** the heading needs
its `#`. A bare line `s01` is not a heading and will be swallowed into the
previous scene's narration — spoken by nobody, aligned anyway, and burnt into a
subtitle.

`## S03` with no text under it stays legal: a **silent scene**, holding screen
time that alignment fills from the pause between its neighbours.

### 4. WAV to the end, one AAC at the mux

The question was why ffmpeg encodes AAC at all. The answer, in order:

- **Everything upstream is already lossless.** `narration.wav` is PCM. Every
  generated effect is PCM (`sfx.write_wav`). The bed is PCM. `amix` sums them in
  float. There is no intermediate lossy step anywhere in the pack.
- **The AAC encode is the last operation in the chain and the only lossy one.**
  It exists because the deliverable is an MP4, and ffmpeg's MP4 muxer will not
  carry `pcm_s16le` — that needs MOV or MKV, which no vertical-video platform
  accepts, and all of which re-encode on upload regardless.
- **So: sound-design in WAV, yes, and that is already what happens.** The
  format of the deliverable was never propagating backwards into the work.

One thing worth adding, and it is cheap (item I): write **`generated/mix.wav`**
— narration plus bed, summed, lossless — as a byproduct of the render. Today the
finished mix exists only inside the MP4. A lossless master is what you hand a
sound designer, and what you re-cut from a year later.

**Amendment to a non-negotiable.** `CLAUDE.md` says *"Narration audio passes
through untouched — never re-encoded avoidably, never time-stretched."*
Workflow 1 changes speed and pitch, so the rule needs one clause:

> …never re-encoded avoidably, and **never time-stretched after alignment**.
> Workflow 1 may change the read's speed and pitch: that is an authored
> decision, taken once, upstream, and everything downstream — alignment
> included — listens to its result. The rule is about **ordering**. Nothing
> after Align may re-time the voice, because every timing in the reel is
> measured against the recording Align heard.

That ordering is the whole safety argument for putting the sound workflow first,
and it belongs in `SPEC.md` rather than in somebody's memory.

---

## The work

Effort in working days on this machine.

### L. Commit what is already built (hours) — **before anything else**

Eleven MemoActs nodes exist only as untracked files: `nodes_audio.py`,
`nodes_page.py`, `memoacts_core/sfx.py`, `memoacts_core/page.py`, alongside
edits to seven tracked files, `docs/SOUND_DESIGN.md` and two example workflows.
Beside them sit `page.py.bak`, `.bak2`, `.bak3`, `__init__.py.bak`,
`sound_design.json.bak` and five `.bak-*` of `hook_page_2.md`.

One bad `git checkout` and a fortnight is gone. Commit the work; delete the
`.bak` files — that is what git is for.

### H. Bring the audio pack inside (≈0.5 d)

`custom_nodes/memoacts_audio/` — seven nodes (Pitch/Time, De-esser, Vocal
Compressor, Normalize, Speech Denoise, Auto-Tune, Loudness Meter), 463 lines on
pedalboard, pyloudnorm and scipy — is **not a git repository, carries no
version, and appears in nobody's requirements file**. It is one folder deletion
from not existing, and it will not be on machine A in September.

- Move it into this pack as `nodes_voice.py` + `memoacts_core/voice.py`,
  category `memoacts/audio`, V3 API like everything else. The seven names do not
  collide with core: `comfy_extras/nodes_audio.py` supplies
  `AudioEqualizer3Band`, `AudioAdjustVolume`, `AudioConcat`, `AudioMerge` and
  `EmptyAudio`, and none of the seven.
- Add `pedalboard` and `pyloudnorm` to `requirements.txt`. Both are installed
  here and neither is declared anywhere; `scipy` ships with ComfyUI.
- `user/default/workflows/MemoActs_VO_Speed_Normalize.json` becomes
  `example_workflows/voice.json` — a student's machine has no `user/default`
  of yours.

For `HARDENING.md`: pedalboard is a compiled wheel. Check that it installs on
the September image *before* the September image is made.

### I. The narration seam (≈0.5 d)

One node, `MemoActs — Set Narration`: takes `AUDIO` and a project, writes
`sources/narration.wav` as PCM, and outputs `PROJECT`, so workflow 1 ends where
workflow 2 begins.

Three things it must do, each because of a specific trap:

1. **Write WAV, never MP3.** `find_narration` globs `narration.*` and returns
   `sorted(...)[0]` — with both files present, `narration.mp3` wins silently.
   The node should say so when it finds one, and offer to move it aside.
2. **Report the length**, against the script's scene count, so "I saved the
   wrong take" is caught here rather than 90 seconds into an alignment.
3. **Not rewrite the file when nothing changed**, or it invalidates the
   alignment cache for free — the exact hazard decision 1 splits the graphs to
   avoid.

Same item, same code path: `generated/mix.wav` as a render byproduct (§4).

### J. The script without timecodes (≈0.5 d, mostly prose)

- `docs/SHOTS_SCHEMA.md` and `docs/WORKSHOP_HANDOUT.md`: the `## S01` layout is
  the taught format; timecodes become an author's dialect, documented as such.
- `projects/workshop_starter/script.md` converts to headings — it is the file a
  student copies.
- The handout gains the heading trap in one sentence.
- Nothing in `memoacts_core` changes. Verify that by conversion rather than by
  reading: convert `workshop_starter`, render it, diff the report.

### K. Rebuild "89" against the new read (≈1 d, needs owner time)

`projects/legends_of_surrender` is now a demonstration of exactly the failure
decision 3 removes.

The script was rewritten on 2026-08-26 from 20 blocks to 28, the hook folded in
as scenes 1–2. `shots.csv` is from 2026-08-22 and addresses its rows by
timecode. Against the new script: **9 new blocks have no row**, one row (`0:14`)
matches nothing and warns, and **four rows match by key while landing on a
different line** — `0:00` onto "Six-seven is dead", `0:06` onto "The 8th of
May", `0:54`'s protocol plate a scene early, `1:09`'s Truman-and-Churchill a
scene early. Only the last kind is silent, and it is the kind that reaches a
museum wall.

1. The new recording is **not on disk**. The newest audio in the project is
   from 2026-08-20; the script is six days younger. Everything below waits on it.
2. Convert `script.md` to `## S01` headings *while* rebuilding, not after —
   renumbering 20 rows against 28 scenes is hand work either way, and doing it
   once in the robust format is cheaper than doing it twice.
3. Rewrite `shots.csv` by scene number.
4. Scenes 1–2 need media: either `S00_hook.mp4` cut in two, or the new sheet —
   `hook_page_2.md` and `example_workflows/hook_page.json` were built for this.
5. `assemble_reel.py` leaves the path. The hook is inside the reel now, and
   `out/reel.mp4` is the finished film.

### G. Machine A, and the numbers (≈1 d + owner time) — carried unchanged

Verbatim from the last plan, still true, still next among the non-code work:
provision machine A by executing `docs/WORKSHOP_MACHINE_SETUP.md` on a clean box
for the first time, correcting it as it fails; extend its §6 to the node path;
measure one clean render, one `archive_soft` render and one cold alignment on
the rented hardware. Those three numbers decide the exercise project's length.

**H adds a dependency to that document.** Do H before G, or provision twice.

## Recommended order

1. **L** — commit. Hours. Nothing below is safe until it is done.
2. **H** — the audio pack comes inside. 0.5 d. Blocks G.
3. **I** — the narration seam. 0.5 d. Closes the shape.
4. **J** — the script format. 0.5 d.
5. **K** — rebuild "89". 1 d, blocked on a recording that does not exist yet.
6. **G** — machine A. 1 d, not code.

## What this plan does not touch

**Per-scene work** — deciding what a single scene looks like, on the example of
the opening hook over the newly generated sheet. That is the next conversation,
and it is deliberately left undecided here: the real question is whether
workflow 3's output reaches one scene as media, as an effect stack, or as a
composite, and it should be answered against a real scene rather than in the
abstract.

The August intensive (`docs/P1_GRAPH.md`, `projects/module03/`,
`tools/run_p1_local.py`) is untouched by every item above, as before.

## Still open, carried forward

- `New_York_May-8_1945.jpg` has no `SOURCES.md` entry and unchecked rights.
  Fifth plan or handoff in a row. It is in the reel.
- Student work isolation on a shared machine, Whisper pre-seeding across an
  image, the `--use-sage-attention` trap: all in `HARDENING.md`, all undecided.
- No project has an `sfx.csv`, and `sources/sfx/` is empty everywhere. The sound
  design works as a mechanism and has never been used as material.
