# shots.json + crop CSV — prepared-inputs contract, schema 1.0

**Frozen 2026-07-24.** This is the interface handed to participants (SPEC §4).
Additive changes bump the minor version; anything that breaks an existing
graph or reader bumps the major version and is announced. `schema_version`
is always present.

## shots.json

```json
{
  "schema_version": "1.0",
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
| `image` | str | filename inside the project `images/` dir |
| `motion` | obj | `{preset, rate, anchor}`; presets: `static, zoom_in, zoom_out, pan_lr, pan_rl, pan_ud, pan_du` |
| `clamped` | bool | resolution guard reduced `rate` so the crop never drops below output width (no silent upscaling) |
| `max_zoom` | float | how far this source *could* zoom (source-window-width / 1080) |
| `crops` | [str] | crop-file stems, one per chunk (`shot_03`, or `shot_03_c0`, `shot_03_c1`, … when chunked to `--max-chunk` frames) |

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
