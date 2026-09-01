# Rebuilding this project's generated media

Media is never versioned, so everything here is an *output*: rebuilt from
`sources/`, not copied between machines. Run from the repository root.

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
