# Rebuilding this project's generated media

Media is never versioned, so everything here is an *output*: rebuilt from
`sources/`, not copied between machines. Run from the repository root.

## The four documents, upscaled 2026-09-02

Four scenes hold a typed sheet still enough to be read, and three of them were
smaller than the frame — the reel was enlarging them just to fill 1080 px, with
nothing left over for a move. Upscaled with **4x_foolhardy_Remacri**, which
`docs/UPSCALE.md` chose for archival material: it adds the least invented detail
of the five models installed (1.44 against a lanczos floor of 1.32), where
UltraSharp and NMKD are disqualified for hardening edges into plastic.

| Scene | File | Before | After | Headroom | Tightest window |
|---|---|---|---|---|---|
| S01 | `67_Page_x2.png` | 4096×5640 | 8192×11280 | 2.94× → **5.88×** | 0.264 → 0.132 |
| S08 | `2301-EN_x4.png` | 768×1057 | 3072×4228 | 0.55× → **2.20×** | 0.774 → 0.352 |
| S16 | `GIoS_Wehrmacht_Signed_Ru_p1_x4.png` | 1024×1410 | 4096×5640 | 0.73× → **2.94×** | 0.775 → 0.264 |
| S17 | `8-5-RU_x4.png` | 768×1057 | 3072×4228 | 0.55× → **2.20×** | 0.774 → 0.352 |

Headroom below 1.0× means the source cannot fill a 9:16 frame at all. Three of
the four were there; none is now.

Run against the local ComfyUI, one graph per file —
`LoadImage → UpscaleModelLoader → ImageUpscaleWithModel → SaveImage`, with
`ImageScaleBy 0.5` after the model on the page only:

```
model:  4x_foolhardy_Remacri.safetensors
S08, S16, S17   4× native, no reduction
S01             4× then ×0.5, i.e. 2×
```

**Why the page is 2× and not 4×.** At 4× it would be 16384×22560 — 370
megapixels, 4.4 GB as one float32 tensor, and 1.1 GB resident every time the
renderer opens it for a shot. 2× is 92 megapixels and halves the tightest legal
window, which is what a camera move needs.

The consequence, stated because it decides what S01 can be: **the pencilled `67`
still cannot be centred.** It sits 4.5 % down the page, and a crop cannot leave
its source, so centring it needs half the window above it — `H ≥ 960 / 0.045 =
21333 px`, which is the 4× page. At 2× the window can approach it and stop. The
alternative is a composite, where the sheet lies on a surface and may leave the
frame; `tools/render_move.py --at` does that and `S01_hook_move.mp4` is one,
rendered and verified, waiting only for a re-render at the scene's own 135
frames.

The originals are kept beside the upscales. Nothing was deleted.

## S01 — the hook sheet, three beats

`sources/composites/S01_hook_move.mp4`

The opening scene is one sentence in two halves — *"Six-seven is dead. Let's
talk eight-nine."* — and the picture is one sheet of paper read in three
stops: the title, then the number in the corner that means nothing, then the
two numbers the reel is about.

This cannot be written in `shots.csv`. A motion preset is one gesture between
two windows and it restarts at every shot boundary; three named stops on one
page is a path, and a path is a composite (`docs/PLAN.md`, "media below the
scene is a composite").

```
python tools/render_move.py --project projects/89-in-comfy \
    --image 67_Page.png --name S01_hook_move \
    --frames 180 --ease cosine \
    --at 0.000:0.281,0.137,0.75 \
    --at 0.140:0.281,0.137,0.75 \
    --at 0.440:0.891,0.045,0.75 \
    --at 0.560:0.891,0.045,0.75 \
    --at 0.880:0.398,0.600,0.75 \
    --at 1.000:0.398,0.600,0.75
```

`--at t:fx,fy,s` names **what to look at**: `fx,fy` is a point on the page and
it goes in the centre of the frame. The three points were measured off the
scan, not guessed:

| beat | on the page | what it is |
|---|---|---|
| 1 | `0.281, 0.137` | the centre of `M E M O A C T S` |
| 2 | `0.891, 0.045` | the centre of the pencilled `67` |
| 3 | `0.398, 0.600` | the `8, 9` in the row `1,2,3,…,11` |

Each stop is written twice, a beat apart, which is what holds it: the pairs
`0.000/0.140`, `0.440/0.560` and `0.880/1.000` are still, and the travel
happens between them.

**`--frames` must match the scene.** 180 frames is 6.00 s at 30 fps, an
estimate made before the reel had been aligned. Run Align and Shot Table, read
S01's real length off the Storyline panel, and re-render with that number of
frames — a clip shorter than its scene is the one thing here that shows.

### Why the desk shows on the first two beats, and why that is not a fault

`s = 0.75` means the page is drawn at three quarters of its own pixels: 3072 ×
4230 in a 1080 × 1920 frame, so about a third of the sheet's width is on screen.
The renderer reports `EDGE IN FRAME` at beats 1 and 2 — the paper does not fill
the frame there and the bed shows behind it.

That is geometry, not a setting. To put a point in the middle of the frame *and*
keep paper to every edge, the point has to be at least half a frame from every
edge of the sheet. `M E M O A C T S` is 13.7 % down the page and the `67` is
4.5 % down and 89 % across — the corner of a sheet cannot be in the middle of
the frame with the sheet still covering it. Covering the frame at beat 2 would
need `s ≥ 3.8`, which is enlarging a scan almost four times.

So the sheet is on a surface and its corner comes to the middle, which reads as
a document being handled rather than photographed. `--bed R,G,B` sets that
surface; the default is `28,32,44`. Beat 3 is full bleed, because the number row
is in the middle of the page.
