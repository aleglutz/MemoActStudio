# P1 graph — facilitator build recipe (Comfy Cloud UI)

One-time build per exercise project, ~15 min. Source of truth for wiring:
`docs/example_shot_chunk_api.json` (the exact graph `tools/run_p1_local.py`
submits — verified locally 2026-07-24). Shortcut to try first: drag that JSON
into the Cloud UI — recent frontends convert API format; if it opens, skip to
step 4 and duplicate.

## 0. Prepared inputs (from the facilitator machine)

Run the generator, then upload to Cloud as input assets:

```
python tools/generate_shots.py --project projects/<name> --lang en --max-chunk 30
python tools/run_p1_local.py --project projects/<name> --export-all cloud_graphs
```

- all `images/*` used by shots
- `generated/report.txt` open in a text editor (you'll paste from `generated/crops/`)
- narration is NOT uploaded — audio is muxed after download (step 6)

`cloud_graphs/` holds one API-format graph per chunk plus `manifest.json`
(images to upload, per-chunk text and frame count). The export needs no
ComfyUI server — run it before travelling. Every node class in those graphs is
confirmed present on Cloud (`SURVEY.md §2.1`).

## 1. One shot-chunk group (build once, then duplicate)

| # | Node (search name) | Set |
|---|---|---|
| 1 | **Load Image** | the shot's image |
| 2–5 | **StringSplitDataList** ×4 (Basic data handling) | `sep` = `,` ; paste `shot_NN[_cK].w.csv` / `.h.csv` / `.x.csv` / `.y.csv` into `string` |
| 6–9 | **CastToInt** ×4 (Basic data handling) | wire each from its split node |
| 10 | **🔧 Image Crop** (`ImageCrop+`, essentials) | `position=top-left`; convert `width,height,x_offset,y_offset` to inputs (right-click → convert widget to input) and wire w→width, h→height, x→x_offset, y→y_offset; image ← node 1 |
| 11 | **🔧 Image Resize** (`ImageResize+`) | 1080×1920, `lanczos`, `stretch`, `always`, multiple_of 0; image ← 10 |
| 12 | **🔧 Draw Text** (`DrawText+`) | shot text (English — the only language, SPEC v3.1), size 44, white, shadow 2/2, align center/bottom, offset_y −420; `img_composite` ← 11. **Must sit here, before batching** (GAPS #3) |
| 13 | **🔧 Image List To Batch** (`ImageListToBatch+`) | image ← 12 |
| 14 | **Video Combine** (VHS) | frame_rate 30, format `video/h264-mp4`, pix_fmt `yuv420p`, crf 19, filename_prefix `reel/shot_NN_cK`, no audio |

> **⚠ Keep chunks small — Cloud kills long jobs.** A job whose execution passes
> roughly 21–44 s is terminated with "RIP to the server your workflow was
> running on", which names no cause and looks like a platform outage
> (`GAPS.md`, 2026-07-28). 30 frames per chunk keeps execution near 16 s even on
> a large source. **Do not raise it to 60** — that lands at 44–49 s and dies.
> Contention makes this worse, so if several people render at once, expect
> failures even at safe sizes and stagger the submissions.
>
> **Questioned 2026-08-20.** The billing feed records single jobs consuming
> 165, 254 and 359 GPU-seconds, which a 44-second kill cannot produce. The
> failures above were real, so this stands until one deliberate long job
> settles it — see `projects/module03/CLOUD.md`.

> **⚠ Your uploaded filename will change.** Comfy Cloud stores every upload under
> a long hexadecimal (SHA-256) name — upload `01_big.png` and it becomes something
> like `a003f3b5….png`. **Node 1 must reference that hashed name, not your
> original filename** — a typed original filename fails with "invalid image file".
> Always pick the file from the Load Image dropdown instead of typing a name.
> This bites once per image and is the likeliest way this recipe goes wrong.
> (`GAPS.md` #4 — verified via the upload API 2026-07-28; **how the Cloud UI
> labels the file in that dropdown is not yet verified — check this before the
> seminar**, since it decides whether participants can recognise their own image.)

*(The former RU/HY subtitle-strip variant is removed — SPEC v3.1 makes the
project English-only, and `DrawText+` covers English directly.)*

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

**One chunk first**, never the whole set — it proves list-map execution and
node availability on Cloud for the price of the shortest segment. Then one full
run; note GPU-seconds from the Cloud dashboard, multiply by cohort size, check
against Sachkosten **before** sharing with participants (SPEC §6.1.4). Iterate
locally, validate on Cloud.

## 6. Assembly (facilitator machine)

Download `reel/*.mp4` into one folder, then:

```
python tools/assemble_reel.py --segments-dir <folder> --narration projects/<name>/narration.mp3 --out reel.mp4
```

Lossless concat + narration mux (+faststart). Done — vertical MP4, 30 fps.
