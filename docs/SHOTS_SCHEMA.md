# shots.json + crop CSV — prepared-inputs contract, schema 1.4

**Frozen 2026-07-24.** This is the interface handed to participants (SPEC §4).
Additive changes bump the minor version; anything that breaks an existing
graph or reader bumps the major version and is announced. `schema_version`
is always present.

**1.1 (2026-08-10)** adds the optional per-shot `words` array. Purely additive:
a 1.0 reader ignores it, and a 1.0 file still loads — the subtitle builder
falls back to one caption per block when it is absent.

**1.2 (2026-08-11)** adds `motion.focus`, the window a shot arrives at or leaves
from. Additive: it is `null` on every shot that does not set one, which is what
a 1.1 file behaves as.

**1.3 (2026-08-11)** adds `label`, the corner tag naming a place or a person.
Additive: an empty string is the absence of one, which is how a 1.2 file reads.

**1.4 (2026-08-11)** adds `media_in` and `speed` for video fragments. Additive:
both are `null` for a still, which is every shot in a 1.3 file.

**1.5 (2026-08-21)** adds `effects`, the shot's own look by preset name. It is
the `effects` column of `shots.csv`, which until now was parsed and then thrown
away — `write_outputs` had nowhere to put it, so a per-shot look could not
reach the renderer at all and every shot got whatever `--effects` said.
Additive: `null` on every shot in a 1.4 file, which is what "no look of its
own" means, and a 1.4 reader ignores it.

## shots.json

```json
{
  "schema_version": "1.1",
  "fps": 30, "width": 1080, "height": 1920,
  "lang": "ru",
  "narration": "narration.mp3",
  "duration_s": 151.32,
  "shot_lead_ms": 100,
  "shots": [ { …shot… } ]
}
```

Per shot:

| field | type | meaning |
|---|---|---|
| `id` | int | 1-based shot number |
| `text` | str | **verbatim script block — this is what reaches the screen** |
| `text_normalized` | str | digits expanded to spoken form; used for alignment only, never displayed |
| `t_start`, `t_end` | float s | shot boundaries after `shot_lead_ms` applied; contiguous, tile `[0, duration_s]` |
| `n_frames` | int | frame count; `sum(n_frames) == round(duration_s * fps)` |
| `estimated` | bool | true = proportional fallback, not aligned (SPEC §5.1) |
| `confidence` | float 0–1 | mean word probability from the aligner; 0 when estimated |
| `had_digits` | bool | block contained digits — read `confidence` with care |
| `image` | str | media filename; resolved against `sources/images/`, `sources/composites/`, `sources/maps/`, `sources/videos/` in that order (`project.MEDIA_DIRS`). `image_path` beside it records where it was actually found, project-relative |
| `media_in` | float s\|null | *1.4, footage only.* Where in the fragment this shot starts. How much is consumed is not stored: the shot's duration comes from the narration and the footage bends to it. |
| `speed` | float\|null | *1.4, footage only.* Playback rate; 0.4 is the slow motion SPEC §5.2 asks for. The frame count is unaffected — speed changes how much footage is spent, not how long the shot runs. |
| `motion` | obj | `{preset, rate, anchor, focus}`; presets: `static, zoom_in, zoom_out, pan_lr, pan_rl, pan_ud, pan_du, square_in, fit`. `square_in` opens as a square inset and pushes in to full-bleed; `fit` shows the media whole at full output width, letterboxed — no crop, so a landscape source is reduced rather than enlarged. Both write `dst_h`; `square_in`'s grows, `fit`'s is constant. Neither uses `rate`. |
| `motion.focus` | [float]\|null | *1.2, optional.* `[cx, cy, w]` in fractions of the source: the window the shot is *about*. `zoom_in` opens on the full frame and arrives here, `zoom_out` starts here and pulls back, `static` holds it; the pans ignore it and the generator warns. Supersedes `rate`, which is a fraction of the whole frame and so cannot reach a detail. Guarded like any other window: never narrower than the output width, never wider than the base 9:16 window, and `clamped` reports when it was widened. |
| `clamped` | bool | resolution guard reduced `rate` so the crop never drops below output width (no silent upscaling) |
| `max_zoom` | float | how far this source *could* zoom (source-window-width / 1080) |
| `words` | [obj] | *1.1, optional.* `{text, t_start, t_end}` per word, **verbatim script text** with aligner timings. Lets a block be cut into single-line captions at real word boundaries (`memoacts_core.caption`). Absent on 1.0 files and when `estimated`; in a block flagged `had_digits` the word *placement* is approximate, because normalisation changes the token count — block boundaries stay exact. |
| `label` | str | *1.3, optional.* Tag burnt into the top-right corner — a place or a person, for shots where the narration does not name what is on screen. Verbatim, like `text`: it is screen text, so normalisation never touches it. It rides in the same `.ass` as the captions under a second style, so burn-in stays one libass pass and the cost is per cue rather than per frame. Empty means no tag. |
| `crops` | [str] | crop-file stems, one per chunk (`shot_03`, or `shot_03_c0`, `shot_03_c1`, … when chunked to `--max-chunk` frames) |

A `square_in` or `fit` shot also writes `crops/<stem>.dst_h.csv` — the height the image
occupies in the output frame, per frame, full output width. Absent for every
other preset, where the crop fills the frame by definition.

## Crop CSVs (`crops/<stem>.{w,h,x,y}.csv`)

Four files per stem — plain ASCII, one line, comma-separated **integers, one
value per frame**, all four the same length. They paste directly into the four
`StringSplitDataList` widgets of the shot subgraph (P1_GRAPH.md):
`w`/`h` = crop size in source pixels (9:16, even numbers), `x`/`y` = top-left
offset. Semantics: `ImageCrop+` position `top-left`, absolute offsets.

## report.txt

Human-readable per-shot line: time span, frames, confidence, image, motion,
`max_zoom`, and flags `[ESTIMATED] [DIGITS] [CLAMPED]`. The facilitator reads
this before uploading anything.

## Invariants a consumer may rely on

1. Boundaries are contiguous and start at 0.
2. Frame counts follow cumulative rounding (no drift against the narration).
3. CSV lengths equal `n_frames` (or its chunk split), and `w/h` are even.
4. `text` is byte-identical to the script block — normalisation never leaks.
