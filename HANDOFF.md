# HANDOFF — session state as of 2026-08-20 (supersedes the 2026-08-19 version)

Read `CLAUDE.md` and `SPEC.md` first, as always. This file is the delta. The
August-19 version described a reel cut to a narration that did not yet include
the cold open; since then the read was re-recorded in one pass, the cold open
was cut to it, and the repository was reorganised around a single `sources/`
folder. Nothing in P1's Cloud story changed.

## The short version

`legends_of_surrender` is **20 shots behind a 4.80 s cold open — 168.97 s,
5 069 frames** — cut to a recorded English narration that carries the hook and
the reel in one take. Every generated asset is rebuilt from the repository by
`projects/legends_of_surrender/REBUILD.md`; nothing in `out/`, `generated/` or
`sources/` travels between machines.

To render it from a clean checkout, follow `README.md` §0–§6. The whole chain
was run end to end after the reorganisation and the alignment report came back
byte-identical, so the move changed no timing anywhere.

## What changed

**The narration is one take, split once.** `sources/voiceover.wav` (168.968 s)
holds the hook and the reel. `sources/narration.wav` is its tail from 4.800 s,
cut with `-c copy` — sample-exact on PCM, verified against an `atrim` of the
same point. The cut lands inside the 1.31 s of silence between the last hook
word and the first reel word. Everything downstream of alignment means the
*reel's* narration by `narration.wav`; the finished file takes its audio from
the whole take, encoded once, with `--narration-under 1`.

**The cold open is cut to the read, not to a feel.** The take was measured on
its own envelope in 50 ms buckets: speech at 1.20–2.60 and 2.95–4.45. The move
was refitted so each line is on screen from just before its first syllable to
just after its last. The 0.30 s the reader left between the sentences is the
whole budget for the second whip, which is why it runs at 9 250 px/s.

**One caption height for the reel, and it is set by the 67.** `margin_v` 530,
plate 0.68 — both in `subs.SubStyle`, which `render_reel` no longer overrides
with a default of its own. The pencilled 67 is the only subject in the reel
whose extent can be measured (ink to y = 1259 of 1920), so it decides.

**The act turns page on the move.** `render_move` takes each sheet's scale from
that sheet's own keys (`scale_at`), so a page change is a cut in scale and a
turn needs no keys of its own. The sheet runs from the tape at the punch holes
to de Lattre de Tassigny's signature in one gesture.

**One `sources/` folder per project.** See `CLAUDE.md` § Project layout. The
search order lives once, in `memoacts_core.project.MEDIA_DIRS`; it used to be
written out twice and the copies had drifted apart.

## What is open

- **`docs/PLAN.md` is finished.** Confirmed by the project owner on
  2026-08-20: subtitles, `shots.csv`, animated maps and moving bands all
  landed. It is history, not a task list. The next plan is a different subject
  — packaging the machinery as something teachable — and replaces it.
- **The MemoActStudio interface has not been started.** The cleanup above was
  the preparation for it, and writing its plan is the next session's whole job.
  Useful fact for it: the node pack is **already V3** — `io.ComfyNode` /
  `io.Schema` throughout, no `INPUT_TYPES` anywhere — so P2 extends it rather
  than migrating it. 871 lines across six files, 14 registered nodes, against
  2 864 lines of `memoacts_core` and 2 900 of `tools/`.
- **`New_York_May-8_1945.jpg` still has no `SOURCES.md` entry**, and its rights
  are unchecked. Carried over from the previous handoff, still true.
- **`projects/demo_en`** renders but has not been run since the reorganisation.
  Its stills are in `sources/images/` now, and its narration is still at the
  project root, which `find_narration` handles.
