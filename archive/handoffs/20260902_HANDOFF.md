# HANDOFF — session state as of 2026-09-02

Read `CLAUDE.md` and `SPEC.md` first. This file is the delta, and it supersedes
`archive/handoffs/20260821_HANDOFF.md`, whose plan items A–F are all built.

**The reel exists.** `projects/89-in-comfy` rendered end to end on 2026-09-02:
26 scenes, 4260 frames, 1080×1920, **142.000 s against 141.99 s of narration,
drift +10 ms**, 85 subtitle cues, 301 s including alignment. It is
`output/memoacts/89_00001.mp4`. That is the crash test's first complete pass and
the first time this project has produced a film from an empty folder.

---

## Do this first: S01's camera move is wrong, and the diagnosis is complete

**What you see:** the hook page drifts slowly upward for 4.5 seconds.
**What was wanted:** two fast moves with stops — `M E M O A C T S`, then the
pencilled `67`, then the `8, 9` in the numbers row.

**Why.** Read straight out of `generated/shots.json`:

```json
"image":  "67_Page.png",
"motion": {"preset": "pan_ud", "rate": 0.06, "focus": null, "path": null}
```

`pan_ud` is a vertical pan — literally the document moving up. Three separate
things are true at once and each one needs a decision:

1. **The composite is not assigned.** `sources/composites/S01_hook_move.mp4`
   exists, was rendered with the three stops, and was verified frame by frame —
   but S01's `media` column still says `67_Page.png`.
2. **The composite is the wrong length.** It is 180 frames (6.00 s); the scene
   is **135 frames (4.50 s)**. Assigned as it stands, the reel would take the
   first 135 frames and the third beat — the `8, 9` — would never arrive.
   Re-render with `--frames 135`; the command is in
   `projects/89-in-comfy/REBUILD.md`.
3. **The row's focus was silently dropped.** S01 carries
   `focus = 0.257 0.300 0.465`, and a pan ignores a focus. The render warned;
   the panel warns too. It is dead weight either way once the move is a
   composite or a path.

**Two routes, and the choice is real.** They are not interchangeable, and the
reason is geometry rather than preference:

| | |
|---|---|
| **Composite** (`tools/render_move.py`) | The sheet sits on a surface and can leave the frame, so the corner `67` can genuinely reach the centre. Costs a second encode and a frame count that must match the scene by hand. Already rendered and verified — only the length is wrong. |
| **Path in the schedule** (`shots.csv` `path` column, schema 1.6) | No intermediate file, no second encode, length always equals the scene. But the window is a crop *inside* the picture: two of the three stops cannot be centred. Measured — asking for `(0.281, 0.137)` lands on `(0.281, 0.227)`, and `(0.891, 0.045)` lands on `(0.824, 0.227)`. |

**Recommendation:** re-render the composite at 135 frames and assign it. The
three beats in 4.5 s is what "two fast moves with stops" means, and the desk
showing behind the corner reads as a document being handled rather than
photographed — which suits a hook. The path column stays the right answer for
every ordinary scene where the target is not near an edge.

A third option, if the corner in dead centre matters more than the surface:
**re-render the page larger.** `67_Page.png` is 4096 px wide, giving a 1:1
window of `w = 0.264` and a 2.94× ceiling. `render_page.py` defaults to 7440 px,
which would take that to `w = 0.145`. A tighter window reaches further into a
corner before the crop hits the edge.

---

## What landed since 2026-08-21

Twenty commits. In dependency order rather than chronological:

**The door in** — `MemoActs — Set Narration`. The pipeline had no entrance: a
project could not be created from the interface (the route existed, no button
called it) and the voice could not be put into one, because ComfyUI's save nodes
sanitise `filename_prefix` and cannot write outside `output/`. One node closes
both. Writes 24-bit PCM at the incoming rate, moves any competing
`narration.*` to `archive/`, and skips the write when the samples match so the
alignment cache survives a re-queue.

**The Storyline panel** — `web/memoacts_storyline.js`, a sidebar tab. The table
inside the Shot Table node is gone; `web/memoacts.js` is deleted and what was
underneath it moved to `web/memoacts_shots.js` unchanged. Scenes stack in spoken
order with a duration bar each, pictures are a shelf above them, and assignment
is click-a-scene then click-a-picture. `auto` marks a scene whose picture nobody
chose; `same as previous` marks a cut that will not read as a cut. Expand puts
the same panel full screen by moving the root element, so unsaved edits survive.

**Scene boundaries** — merge and split, in the panel, editing `script.md` **and
renumbering `shots.csv` with it**. That second half is the load-bearing one: a
boundary moving shifts every scene after it. Merging folds the absorbed row into
the survivor cell by cell, which is how "hold this picture, then push in"
survives becoming one scene. Used in anger: 34 scenes → 26, eight duplicate pairs
gone, zero rows misplaced.

**Keyed paths** — `Motion.path`, `schedule.keyed()`, the `path` column, schema
1.6. Built out of `focus_window` so the resolution guard is the same code. In the
panel the rectangle is the scale, its position the stop, the times between stops
the speed. Every stop the crop cannot reach is reported with the coordinate it
will actually land on.

**The enlargement floor came out.** A window narrower than the output used to be
widened back, which made the guard a refusal. `CLAUDE.md`'s rule is that
enlargement is never *silent* — so the floor is gone, the factor is printed
beside the rectangle as it is drawn and named per scene in the report, and
`on_upscale` still decides warn / error / allow. Audited first: no focus in any
project sat below its floor, so nothing existing renders differently. The
ceiling stays and is arithmetic.

**Three defects the crash test found by being walked:**

- **Escaped headings.** `script.md` arrived with every `## S01` written
  `\## S01` — an editor escaping the hash on paste. Markdown says that means
  "not a heading", so the parser was right, and 34 scenes read as 69 blocks with
  the heading lines aligned and subtitled. `project.escaped_headings()` now
  counts them and `read_project` says so first.
- **A spreadsheet holding the file.** LibreOffice's lock made `write_table`'s
  atomic replace fail with `WinError 5`; aiohttp turned it into a text 500 and
  the panel called `.json()` on it, so the person saw a JSON parser error
  describing a spreadsheet. Now `TableLocked` names the lock file, the route
  answers 400, and the panel reads the body as text before trusting it.
- **numba against numpy.** `ImportError: Numba needs NumPy 2.3 or less. Got
  NumPy 2.4` — numpy went to 2.4.6 on 24 August and took the aligner with it.
  Nobody noticed for eight days **because alignment is cached**, so the one step
  that needed the dependency was the one step that never ran. Fixed by upgrading
  numba to 0.67 (`numpy<2.6`), not by downgrading numpy.

---

## What the first full render said, beyond S01

**Four scenes set a focus that a pan ignores** — 1, 3, 10 and 21. Three of them
name the pan explicitly; **scene 10's `motion` column is empty** and
`default_motion` cycles by scene number, so a rectangle drawn on a scene whose
motion was never chosen lands on a pan every other time and does nothing. The
panel now writes `zoom_in` alongside a focus when the motion is unset. The three
explicit ones are yours to decide: change the motion, or drop the focus.

**Thirty-four commented rows.** `## S01,Six-seven is dead.,…` — leftovers from
the 34-scene numbering, carrying only the scene's `words`. Verified: **none of
them decides anything**, so nothing is lost, but they outnumber the live rows.
Worth deleting.

**Thirteen scenes are being enlarged**, and this is an editorial fact about the
picture set rather than a fault. The worst:

```
Loznitca_VDay_Treptov.jpg   482 px   2.24×
2301-EN.jpg / 8-5-RU.jpg    594 px   1.82×
Karlshorst-Foyer…png        752 px   1.44×
Who-give-orders-THF.jpg     770 px   1.40×
```

A larger source for the Loznitsa frame is the single replacement that would most
improve the picture — and it is also the one shot in the reel with no route to
clearance (`sources/SOURCES.md`).

**`PIL.UnidentifiedImageError` in the log after every render is not ours.**
`ui.PreviewVideo` emits `{"images": …, "animated": true}`, the frontend asks
`/view` for a webp thumbnail of an `.mp4`, and PIL refuses. `comfy_extras/nodes_video.py`
lines 73 and 202 do exactly the same thing, so core video nodes produce it too.
The `gifs` key that VideoHelperSuite uses does not exist in frontend 1.49.6 —
it is VHS's own JS. Left alone deliberately.

---

## State of the material

| | |
|---|---|
| `projects/89-in-comfy` | 26 scenes, all with pictures. `narration.wav` 141.99 s, 44.1 kHz stereo 24-bit. Aligned, rendered, watchable. |
| `projects/legends_of_surrender` | Untouched. Its `generated/shots.json` is 20 shots against a 28-scene script, so the panel correctly refuses to draw its timing bars. |
| Environment | numba 0.67.0 / llvmlite 0.49.0 / numpy 2.4.6. Whisper `medium` (1.42 GB) is now cached locally. |

## Still open

- **`docs/WALKTHROUGH.md` §6 is empty.** The crash-test log is the deliverable
  of walking it, and the walk has now happened — filling it in is what turns
  this session into the handout.
- **Item G**, unchanged and still not code: provision machine A by executing
  `docs/WORKSHOP_MACHINE_SETUP.md` on a clean box, and measure one clean render,
  one `archive_soft` render and one cold alignment on the rented hardware.
- **Stable Audio Open's licence** against the Zuwendungsbescheid (`SURVEY.md`).
  Not a blocker — the pack ships no weights and the sound design works from CC0
  files — but unanswered.
- **`sfx.csv` does not exist in any project.** The sound design works as a
  mechanism and has never been used as material.
- **`generated/mix.wav`** — the finished mix exists only inside the MP4. A
  lossless master is one ffmpeg call and is what a sound designer would be
  handed.
