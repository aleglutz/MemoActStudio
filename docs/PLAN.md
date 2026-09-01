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

There was exactly one missing seam, and it had two ends. Nothing wrote the
narration into a project — workflow 1 ends in an `AUDIO`, and ComfyUI's save
nodes sanitise `filename_prefix` so it cannot point outside `output/`. And
nothing **made** a project either: the route existed, no button called it. Both
came out as "carry a file by hand".

`MemoActs — Set Narration` closes both, and it is the only new node the
three-workflow shape required. Item I.

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

**A non-negotiable came out.** `CLAUDE.md` used to carry *"Narration audio
passes through untouched — never re-encoded avoidably, never time-stretched."*
Workflow 1 changes speed and pitch, which the rule forbade outright, and the
rule was **removed on 2026-08-29** rather than qualified — cheaper than
expanding it, and the thing it protected is protected by the order of the
workflows instead:

> The voice is authored once, in workflow 1, and **alignment listens to the
> result**. Every timing in the reel is measured against the recording Align
> heard, so nothing after Align can re-time the voice without invalidating all
> of them — which is a fact about the pipeline, not a rule anybody has to keep.

That is the whole safety argument for putting the sound workflow first, and it
is why the order in this plan is the order and not a preference.

The rule's other half — *never re-encoded avoidably* — survives as a design
fact, described above: one AAC encode, at the end, on the deliverable. Item I
adds the other half of that in practice: the voice reaches the project as 24-bit
PCM at whatever rate it was authored in, never resampled and never re-encoded on
the way.

---

## The work

Effort in working days on this machine.

### L. Commit what is already built — **DONE 2026-08-29**

Eleven MemoActs nodes existed only as untracked files, alongside seven more
tools, the Sound Design frontend, ten archived graphs and a font — one bad
`git checkout` from gone. Committed in four: sound, page, the "89" script
rewrite, module03. Twenty `.bak` files deleted and the pattern added to
`.gitignore`, so the next batch stays out of `git status` on its own.

Both typewriter faces got their `SURVEY.md` rows in the process, which
`LICENSE-ErikaOrmig.txt` had been asking for in writing.

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

Recorded in `docs/WORKSHOP_MACHINE_SETUP.md` §3.3: pedalboard is a compiled
wheel. Check that it installs on the September image *before* the image is made.

### I. The door in — **BUILT 2026-08-29**

The start of the pipeline had no door at either end, and it was one gap rather
than two. A student could not **make a project** from the interface — the
`POST /memoacts/project` route existed and no button called it — and could not
**put the voice into one**, because the voice workflow ends in an `AUDIO` and
ComfyUI's save nodes sanitise `filename_prefix` so it cannot point outside
`output/`. Both ends came out as: carry a file by hand. That is a terminal's job
done with a mouse, which `docs/INTERFACE_BRIEF.md` exists to forbid.

**One node closes both.** `MemoActs — Set Narration` takes `AUDIO` and a name,
creates the project if that name is new, writes `sources/narration.wav`, and
outputs `PROJECT`. Naming the folder is not a decision a student thinks about
separately from putting their voice in it, so it is not a separate node — it is
the same sentence: *"my voice goes into my project."*

`pipeline.create_project` holds what a project is; the route now calls it too,
so there is one list of the folders and not two. The route keeps its one
difference: it **refuses** a name that exists, because a route called "new" that
hands back somebody else's project is how a student overwrites a neighbour on a
shared machine. The node is idempotent instead, because it runs on every queue.

Four traps, each closed and each verified against a real filesystem:

1. **WAV, never MP3.** `find_narration` globs `narration.*` and takes
   `sorted(...)[0]`, so `narration.mp3` beats `narration.wav` silently and for
   as long as both exist. Every other `narration.*` in `sources/` is **moved to
   `archive/`** — moved, never deleted — and named in the report. One at the
   project root is only warned about: `sources/` is read first so it cannot win,
   and it is somebody's file.
2. **The file is left alone when the samples match.** The encoded bytes are
   compared through a temp file and the write is skipped, so a re-queued graph
   does not touch the mtime that alignment is cached on. Verified: second run,
   `st_mtime_ns` unchanged.
3. **`fingerprint_inputs` is not `float("nan")`.** Always-run is the obvious
   answer and the wrong one — this node feeds Align, and a node that always
   re-runs re-runs everything downstream. It keys on the written file instead,
   so an emptied folder re-runs and an unchanged one does not.
4. **The rate and channel count survive.** Not `audio_to_numpy`, which forces
   44.1 kHz stereo for the mix bed. Verified: 48 kHz stereo in, 48 kHz stereo
   24-bit PCM out.

The node also reports what is still missing — scenes in `script.md`, pictures in
`sources/images/` — because it is the only step that knows the project is brand
new, and therefore the only one that can say what to do next without guessing.

**Still open in this item:** `generated/mix.wav` as a render byproduct (§4), and
a button for the create-project route. The button matters much less now that the
node makes projects; it is a nicety for someone who wants an empty project
before they have recorded anything.

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

### M. The storyline panel — **BUILT 2026-09-01**

The editor was a `<table>` inside the Shot Table node, and 34 scenes against 20
pictures broke it two ways. It had **no time in it** — `/memoacts/shots` calls
`read_project`, which never touches the aligner, so every row was the same
height whether the scene ran 1.4 s or 8 s and the rhythm of the film was
invisible. And pictures were chosen from a **dropdown of filenames**, with one
thumbnail on screen for drawing the focus rectangle on: assigning 34 scenes
meant already knowing what each filename looked like.

`web/memoacts_storyline.js` is a sidebar tab. Scenes stack in spoken order with
a duration bar each; the pictures are a shelf above them; **click a scene, then
click a picture.** Expand puts the same panel full screen for laying a whole
reel out at once. Two marks fell out of the rebuild almost free and close two
more holes: **auto**, for a scene whose picture nobody chose — the cycled
default is how a scene reaches the render unlooked-at — and **same as
previous**, for the cut that does not cut.

The bars come from `generated/shots.json`, which already held `t_start`,
`t_end` and `n_frames`: one file read, no aligner. **The guard on it is the
load-bearing part.** A `shots.json` from a different script would draw
confident, wrong bars, and both live projects were in exactly that state — so
the timing is attached only when the file has the same number of scenes *and*
the same words in each. Otherwise the panel says why there are none.

What was underneath the table — `load` / `persist`, the focus picker, the option
lists — moved unchanged into `web/memoacts_shots.js`. `web/memoacts.js` is gone,
the node has no widget, and it keeps the job it actually does: compiling the
table and printing the report.

**Not in scope, decided with it:** media below the scene. A change inside a
scene is a composite, as `S12_ru_page_move.mp4` already is, not a third level in
`shots.json`.

### N. The escaped-heading guard — **BUILT 2026-09-01, found by the crash test**

`89-in-comfy`'s `script.md` arrived with every `## S01` written `\## S01` — an
editor escaping the hashes on paste. Markdown says a backslash there means "a
literal hash, not a heading", so the parser was right to obey, and the result is
silent and total: no headings, the plain layout, 34 scenes read as **69 blocks**,
and the heading lines themselves aligned and burnt into subtitles. Nothing about
the file looks wrong until you count.

`project.escaped_headings()` counts them and `read_project` puts it first among
the warnings, in words that say what to do. This is the crash test working as
intended: the hole was found by walking the path, not by reasoning about it.

### G. Machine A, and the numbers (≈1 d + owner time) — carried unchanged

Verbatim from the last plan, still true, still next among the non-code work:
provision machine A by executing `docs/WORKSHOP_MACHINE_SETUP.md` on a clean box
for the first time, correcting it as it fails; extend its §6 to the node path;
measure one clean render, one `archive_soft` render and one cold alignment on
the rented hardware. Those three numbers decide the exercise project's length.

**H adds a dependency to that document.** Do H before G, or provision twice.

## Recommended order

1. ~~**L** — commit.~~ **Done 2026-08-29.** Four commits, and the `.bak` files
   are gone.
2. **H** — the audio pack comes inside. 0.5 d. Blocks G.
3. ~~**I** — the narration seam.~~ **Done 2026-08-29**, and it turned out to be
   both ends of the same gap: the door in now makes the project as well as
   filling it.
4. **J** — the script format. 0.5 d. **N is done**, which is the half of it
   that had teeth.
5. **K** — rebuild "89". 1 d, blocked on a recording that does not exist yet.
6. **G** — machine A. 1 d, not code.

## What this plan does not touch

The August intensive (`docs/P1_GRAPH.md`, `projects/module03/`,
`tools/run_p1_local.py`) is untouched by every item above, as before.

## Still open, carried forward

- ~~`New_York_May-8_1945.jpg` has no `SOURCES.md` entry and unchecked rights.~~
  **Closed 2026-08-29.** Recorded in the project's `SOURCES.md`: Museum
  Berlin-Karlshorst's own page, credited *"unknown, akg images, Berlin"*, and
  carried on the commissioning museum's licence. One email to MBK would close it
  in writing rather than on judgement; a screening outside the museum needs that
  email.
- ~~`HARDENING.md`~~ **retired 2026-08-29** into
  `docs/WORKSHOP_MACHINE_SETUP.md`. Student work isolation and machine reset are
  now that document's §7, written out rather than deferred; the
  `--use-sage-attention` trap is §3.5 with its detection in §6.5; Whisper
  pre-seeding is §3.7. All three are still **undecided or unexecuted** — they
  moved to where they will be read, not to where they are done.
- No project has an `sfx.csv`. `sources/sfx/` now exists in the two live
  projects with a README explaining what belongs in it, so the folder is no
  longer the thing standing in the way. The sound design still works as a
  mechanism and has never been used as material.
