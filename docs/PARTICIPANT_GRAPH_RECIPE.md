# P1 graph — facilitator build recipe (Comfy Cloud UI)

One-time build per exercise project, ~15 min. Source of truth for wiring:
`docs/example_shot_chunk_api.json` (the exact graph `tools/run_p1_local.py`
submits — verified locally 2026-07-24). Shortcut to try first: drag that JSON
into the Cloud UI — recent frontends convert API format; if it opens, skip to
step 4 and duplicate.

## 0. Prepared inputs (from the facilitator machine)

Run the generator, then upload to Cloud as input assets:

```
python tools/generate_shots.py --project projects/<name> --lang en --max-chunk 60
```

- all `images/*` used by shots
- `generated/report.txt` open in a text editor (you'll paste from `generated/crops/`)
- narration is NOT uploaded — audio is muxed after download (step 6)

## 1. One shot-chunk group (build once, then duplicate)

| # | Node (search name) | Set |
|---|---|---|
| 1 | **Load Image** | the shot's image |
| 2–5 | **StringSplitDataList** ×4 (Basic data handling) | `sep` = `,` ; paste `shot_NN[_cK].w.csv` / `.h.csv` / `.x.csv` / `.y.csv` into `string` |
| 6–9 | **CastToInt** ×4 (Basic data handling) | wire each from its split node |
| 10 | **🔧 Image Crop** (`ImageCrop+`, essentials) | `position=top-left`; convert `width,height,x_offset,y_offset` to inputs (right-click → convert widget to input) and wire w→width, h→height, x→x_offset, y→y_offset; image ← node 1 |
| 11 | **🔧 Image Resize** (`ImageResize+`) | 1080×1920, `lanczos`, `stretch`, `always`, multiple_of 0; image ← 10 |
| 12 | **🔧 Draw Text** (`DrawText+`) | shot text (EN track only — see GAPS #1), size 44, white, shadow 2/2, align center/bottom, offset_y −420; `img_composite` ← 11. **Must sit here, before batching** (GAPS #3) |
| 13 | **🔧 Image List To Batch** (`ImageListToBatch+`) | image ← 12 |
| 14 | **Video Combine** (VHS) | frame_rate 30, format `video/h264-mp4`, pix_fmt `yuv420p`, crf 19, filename_prefix `reel/shot_NN_cK`, no audio |

RU/HY variant: replace 12 with **Load Image** (subtitle strip PNG, uploaded) →
**ImageCompositeMasked** (core; destination ← 11, source ← strip, mask ← strip alpha).

## 2. Duplicate per chunk

Select the group → clone per `crops` entry in `shots.json`. Only four pastes
(w/h/x/y), the image, the text, and the filename_prefix change per chunk.
Keep prefixes zero-padded (`shot_01_c0`…) — assembly sorts lexically.

## 3. Run

Queue once. Segments land in the Cloud output panel as `reel/shot_*.mp4`.

## 4. Participant exercise surface

Participants change: an image (re-upload + repoint node 1), the text widget,
or a motion by pasting a different crop CSV set (facilitator provides
alternates, e.g. `zoom_in` vs `pan_lr` variants). Everything else is frozen.

## 5. Credit discipline

One full run, note GPU-seconds from the Cloud dashboard, multiply by cohort
size, check against Sachkosten **before** sharing with participants
(SPEC §6.1.4). Iterate locally, validate on Cloud.

## 6. Assembly (facilitator machine)

Download `reel/*.mp4` into one folder, then:

```
python tools/assemble_reel.py --segments-dir <folder> --narration projects/<name>/narration.mp3 --out reel.mp4
```

Lossless concat + narration mux (+faststart). Done — vertical MP4, 30 fps.
