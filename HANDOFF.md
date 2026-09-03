# HANDOFF — session state as of 2026-09-03

Read `CLAUDE.md` and `SPEC.md` first. This file is the delta, and it supersedes
`archive/handoffs/20260902_HANDOFF.md`, whose one open item — S01's camera move
— was closed the same day.

**The pack is now the whole pipeline.** Thirty-five nodes, in four categories,
and nothing the workflow needs lives outside git any more.

---

## Do this first: item G, and it is not code

`docs/PLAN.md` item **H is done**, which was the last thing blocking it.
Provision **machine A** by executing `docs/WORKSHOP_MACHINE_SETUP.md` on a
clean box for the first time, correcting the document as it fails, and measure
three numbers on the rented hardware:

- one clean render,
- one `archive_soft` render,
- one cold alignment.

Those three decide how long the September exercise project can be, and they
cannot be guessed from this machine — a 3090 Ti is not what the workshop rents.
**Step 3 is the one to watch**: `pedalboard` is a compiled wheel, it is now a
declared dependency, and if no wheel exists for that machine's Python this is
where it fails. Better there than mid-workshop.

The other open items, unchanged and none of them blocking: `docs/WALKTHROUGH.md`
§6 is still empty; no project has an `sfx.csv`; `generated/mix.wav` is still
only inside the MP4; Stable Audio Open's licence is still unanswered against
the Zuwendungsbescheid.

---

## What landed 2026-09-03 — the voice comes inside (PLAN item H)

`custom_nodes/memoacts_audio/` was seven nodes on pedalboard, pyloudnorm and
scipy that were **not a git repository, carried no version, and appeared in
nobody's requirements file**. One folder deletion from not existing, and
certain not to be on machine A in September.

They are now `nodes_voice.py` + `memoacts_core/voice.py`, category
`memoacts/audio`, V3 API, split the way the rest of the pack is split: the
node file is widgets, ranges and tooltips; the core file is torch-free DSP that
`tools/` could call tomorrow.

**Three decisions worth knowing, because each one changes something on disk:**

1. **The ids changed.** `AudioPitchTime`, `AudioNormalize`, `AudioDeEsser` —
   names general enough that the Registry hands them to somebody else
   eventually, and a collision there resolves silently in favour of whichever
   pack loaded last. They are `MemoActsAudio*` now. The one saved workflow that
   used the old ids was being rewritten anyway.
2. **The old folder is `custom_nodes/memoacts_audio.disabled`** — renamed, not
   deleted, because ComfyUI skips that suffix and a rename is undone in a
   second. Delete it once the September image is built from
   `requirements.txt`.
3. **The dependencies are declared.** `pedalboard` and `pyloudnorm` are in
   `requirements.txt` and `pyproject.toml`; `docs/WORKSHOP_MACHINE_SETUP.md` §3
   installs from the file rather than a hand-typed list. Both licences went
   into `SURVEY.md`, and one of them matters: **pedalboard is GPL-3.0**, and we
   *import* it rather than sit beside it in a graph. This pack is already
   GPL-3.0-or-later for the same reason, so the obligation is satisfied by
   construction — but nothing here can be re-licensed more permissively while
   that import stands.

**The workflow gained the end it was missing.**
`user/default/workflows/MemoActs_VO_Speed_Normalize.json` is now
`example_workflows/voice.json`, and it no longer finishes at
`SaveAudioAdvanced` writing **`narration.mp3`** — which is precisely the file
that beats a `narration.wav` in `find_narration`'s alphabetical pick, the trap
`Set Narration` was built to close. It finishes at **Loudness Meter → Set
Narration**: measured, then written into the project as 24-bit PCM. The
markdown note beside it was rewritten with it, and `docs/WALKTHROUGH.md` §1 now
opens a file that exists on a student's machine.

**Verified by running it, not by reading it.** Every function exercised on a
synthetic take; then the graph itself queued on the server:

```
20.06 s in → 17.45 s out at tempo 1.15      (the arithmetic agrees to the sample)
44100 Hz, 2 ch, 24-bit PCM written          (rate and channels never touched)
-13.41 LUFS | peak -1.00 dBFS | 17.45s      (off the meter node)
project created, narration.wav written      (Set Narration's own report)
```

The scratch project used for it is deleted. `docs/NODES.html` gained the seven
nodes and their ranges, and its counts now read 35 nodes in 4 categories.

---

## What landed 2026-09-02, after the last handoff was written

**S01 no longer crawls.** The hook page was on `pan_ud` — a vertical pan, the
document sliding upward — with a focus the pan silently ignored. The composite
route was rejected deliberately: three more documents in the reel have the same
problem, and a per-document composite does not scale. Instead all four were
upscaled with `4x_foolhardy_Remacri` (the model `docs/UPSCALE.md` chose, for
inventing the least), S01 became `static`, and the focus already in the row
started working.

| scene | file | was | now | headroom |
|---|---|---|---|---|
| S01 | `67_Page_x2.png` | 4096×5640 | 8192×11280 | 2.94× → 5.88× |
| S08 | `2301-EN_x4.png` | 768×1057 | 3072×4228 | 0.55× → 2.20× |
| S16 | `GIoS_…_p1_x4.png` | 1024×1410 | 4096×5640 | 0.73× → 2.94× |
| S17 | `8-5-RU_x4.png` | 768×1057 | 3072×4228 | 0.55× → 2.20× |

Three of the four were **below 1.0** — the render was stretching them just to
fill 1080 px, with nothing left for a move. The page went to 2× rather than 4×
on purpose: 4× would be 370 megapixels and 1.1 GB in memory every time the
renderer opens it. The arithmetic, and what 2× does not buy, is written into
`projects/89-in-comfy/REBUILD.md` — the pencilled `67` still cannot reach dead
centre, because a crop cannot leave its source.

`read_project` now returns one warning where it returned five. `docs/NODES.html`
was added the same day: the node reference in the repository rather than only on
a URL.

---

## State of the material

| | |
|---|---|
| `projects/89-in-comfy` | 26 scenes, all with pictures, rendered end to end on 2026-09-02: 4260 frames, 142.000 s against 141.99 s of narration, drift +10 ms, 85 cues. S01 fixed since. Stops on S01 are still to be placed by hand, in the panel |
| `projects/legends_of_surrender` | Untouched. Its `generated/shots.json` is 20 shots against a 28-scene script, so the panel correctly refuses to draw timing bars |
| Environment | numba 0.67.0 / llvmlite 0.49.0 / numpy 2.4.6 / pedalboard 0.9.19 / pyloudnorm 0.1.1. Whisper `medium` cached locally |
| Registered | 35 MemoActs nodes: 9 reel, 4 sound, 8 effects, 7 page, 7 voice |

## Known and deliberately left alone

`PIL.UnidentifiedImageError` in the log after every render is not ours:
`ui.PreviewVideo` emits `{"images": …, "animated": true}`, the frontend asks
`/view` for a webp thumbnail of an `.mp4`, and PIL refuses. `comfy_extras/nodes_video.py`
does the same thing, so core video nodes produce it too.
