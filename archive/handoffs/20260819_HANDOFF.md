# HANDOFF — session state as of 2026-08-19 (supersedes the 2026-07-28 version)

Read `CLAUDE.md` and `SPEC.md` first, as always. This file is the delta: what a
fortnight on a MacBook changed, where the reel stands, and what is still open.
The July version described the close of P1 and the building of the node layer;
none of that changed. What changed is that `legends_of_surrender` went from a
first rough render to a reel with a real narration under it.

## The short version

The reel is **20 shots, 164.82 s, 4 945 frames**, cut to a recorded English
narration, and every generated asset in it is rebuilt from the repository by
`projects/legends_of_surrender/REBUILD.md`. The last commit is `e2290b1`.

## What changed

**The narration is real.** A recorded read replaced the Kokoro scratch track, so
`confidence` in the report is meaningful for the first time (0.63–0.91, nothing
`[ESTIMATED]`). Two things were learned the expensive way and are now guarded:

- The read arrived as raw ADTS `.aac`, whose duration is *estimated from the
  bitrate* — 168.12 s against the 164.82 s actually in the file. That figure
  sets the last shot's end. It is converted to WAV, and `align.audio_duration`
  now prefers the audio stream's own duration and refuses rather than guesses.
- `torchaudio.info` was removed in torchaudio 2.9. The length is read with
  ffprobe now, which also removes torchaudio from the repository entirely.

**The script's cues are measured, not guessed.** The re-recorded script arrived
with its cue timecodes stripped and one block split in two, so every row of
`shots.csv` matched nothing and every shot silently fell back to a cycled image.
Alignment does not need `shots.csv`, so it ran first and the cues were written
from the measured block starts. A duplicated cue is now a warning rather than a
silent reroute — a dict comprehension had been keeping the *last* of a repeated
key.

**The maps speak the reel's own language.** `render_map.py` gained `--marker`
(a pinned town, since Natural Earth 1:50m has no Reims), `--scale` (a plate with
room to push into), and `--palette`. The palette is sampled from the reel's own
document scans rather than chosen: paper 239–249 / 221–240 / 198–215, warm by
about +38 red over blue; ink from 69,49,43 to 132,101,89; signatures blue-black.
All three plates run on `ink` — land from the page, water from the signatures.

**Stacked frames come from this repository now.** `render_bands.py` gained
`--still` and `--mono`, so `S01-02_two-band` and `S18_three-cities_bw` no longer
depend on Olm-DragCrop, whose licence forbids redistribution and which blocked
imaging the September machines (`SURVEY.md §3`).

**1:26–1:38 is one gesture across two shots.** `tools/render_move.py` is new: a
page is placed on the frame by keys of `t:cx,cy,s`, `--turn` folds a sheet over
with a crease instead of swapping the image, and the two shots read consecutive
parts of one clip through `shots.csv`'s `in` column. The choreography was
measured off a reference reel rather than described from it — 28 segments in
40 s, median 1.05 s, 374 px/s median while moving, no zoom anywhere, and 27 text
lines filling the height.

**The caption track was re-styled.** Captions moved to the middle of the frame
(this is 9:16 and the subjects sit centre-frame), the plate went 0.55 → 0.80 for
the black-and-white material, and a `credit` column was added: unlike a label it
holds for the whole shot, because for the one shot that is neither ours nor
public domain the on-screen attribution is a condition of use.

**Two ffmpeg breakages, both environmental.** ffmpeg 8 stopped accepting quoted
filter values, so the subtitle path is escaped instead — which is also the form
Windows drive colons need. And Homebrew's core ffmpeg no longer ships libass at
all; `README.md` points at the `homebrew-ffmpeg` tap. Neither affects this
machine, whose ffmpeg has always carried libass.

## Where it runs

Windows uses ComfyUI's embedded Python, as `CLAUDE.md` says. The Mac used a
`.venv` and is not part of the pipeline. Nothing in the reel path needs ComfyUI,
torch or a GPU except alignment, which needs stable-ts.

`docs/CONTINUE_ON_PC.md` records the move itself: what had to travel
(`narration.wav` and two images — everything else is in git or rebuilt) and what
to check before spending a render.

## Open, in rough order of cost

- **`docs/PLAN.md` is stale.** Dated 2026-08-10, it marks A1/A2 done and does
  not know that C1, C2 and C3 landed. Item **B** — several shots per narration
  block — is genuinely still open, and it is still the thing that would buy the
  most pacing.
- **Rights.** The Loznitsa frame at 1:58 is quoted with an on-screen credit but
  **not cleared**. `New_York_May-8_1945.jpg` has no `SOURCES.md` entry at all,
  which by that file's own rule means unchecked. The grant makes provenance a
  deliverable.
- **Upscaling the act scans** is planned on this machine. When it happens,
  divide every `s` in the page-move command by the upscale factor; the framing
  does not move. `UPSCALE.md` §"when not to upscale" applies to the signatures.
- **September.** The workshop teaches `comfyui-memoacts`, the deadline is hard,
  and the rented machines are still unspecified (`HARDENING.md`). The seminar-
  scale Cloud concurrency test and the facilitator recovery procedure
  (`GAPS.md`) remain August-intensive blockers, not P2 work.