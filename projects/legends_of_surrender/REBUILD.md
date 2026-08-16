# Rebuilding this project's generated media

Media is never versioned, and everything below is an *output*: it is rebuilt
from `images/` plus `assets/geo/`, not copied between machines. A copied output
can silently disagree with the inputs it claims to come from, which is why the
commands live here rather than the files living in git.

Run from the repository root with the environment active (`README.md` §0).
Nothing here needs ComfyUI, torch or a GPU — only Pillow, numpy and ffmpeg.

## Map plates — palette `ink` (SOURCES: sampled from the act scans)

    python tools/render_map.py --out projects/legends_of_surrender/maps \
        --name map_baltics --frames 360 --palette ink \
        --highlight Latvia Estonia Lithuania

    python tools/render_map.py --out projects/legends_of_surrender/maps \
        --name map_poland_ukraine --frames 360 --palette ink \
        --highlight Poland Ukraine --already Latvia Estonia Lithuania

    python tools/render_map.py --out projects/legends_of_surrender/maps \
        --name map_france_reims --highlight France --context 1.5 --scale 2 \
        --palette ink --marker "4.0317,49.2583,Reims"

`--scale 2` is what lets the 0:23 shot push in 2.5x without enlarging anything;
the tool prints the `focus` triple that `shots.csv` uses, so it is never
measured off the finished image by eye.

## Stacked frames

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S01-02_two-band --still \
        --band Reims-Signing.jpg:0.5 --band Karlshorst_Signing.jpg:0.5

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S18_three-cities_bw --still --mono \
        --band London.jpg:0.5 --band Berlin.jpg:0.5 --band Moscow.jpg:0.5

`S14_three-band.mp4` is **retired**: 1:32 now belongs to the page move below.
The command is kept in git history if the shot ever comes back.

## The act, read — 1:26 to 1:38

One clip, two shots: 1:26 reads it from 0, 1:32 from 5.420 s, the measured
length of the first shot.

### What the reference actually does

Measured off the reel frame by frame (phase correlation at 10 fps, cut
detection on correlation and frame difference), not described from memory:

| | |
|---|---|
| segments between cuts | 28 in 40 s — median **1.05 s** |
| of those | 24 moves, 4 holds; a hold is **0.8 s** median |
| speed while moving | median **374 px/s** at 720 wide, range 75–1241 |
| direction | horizontal dominates: 11 right, 6 left, 5 diagonal, 1 vertical |
| speed within a segment | *not* constant — it accelerates and settles |
| closeness | **27 text lines** fill the height in the wide beats, **10–11** in the close ones |

Two things follow that the earlier passes got wrong. The framing is a *reading*
framing — 27 lines, not a whole page — and it goes twice closer than that at
the close beats. And the movement eases: `--ease linear` was wrong, the sheet
arrives and settles rather than stopping dead.

### The path

Page 1 is the 1024x1410 "klein" scan and pages 2 and 3 are 1860x2560, so `s`
differs to hold one reading size: 2.60 and 1.43 both give a page about 2660 px
wide, which is 27 lines in the frame. The close beat on page 3 runs at 2.00.

Magnification is therefore real — up to 2.6x on page 1 — and **deliberate**:
`UPSCALE.md` forbids silent enlargement, not enlargement, and the tool prints
the factor at every run. It is plain Lanczos, which invents nothing. When the
scans are upscaled, divide every `s` by the upscale factor and the framing is
unchanged.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru_p2.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 344 --ease cosine \
        --key 0.000:0.500,0.950,2.60,1 --key 0.044:0.500,0.950,2.60 \
        --key 0.140:0.100,0.940,2.60 --key 0.201:0.100,0.940,2.60 \
        --key 0.305:0.620,0.760,2.60 --key 0.340:0.620,0.760,2.60 \
        --key 0.401:0.550,0.700,1.43 --key 0.471:0.180,0.660,1.43 \
        --key 0.541:0.180,0.660,1.43 --key 0.637:0.600,0.520,1.43 \
        --key 0.698:0.550,0.500,1.43 --key 0.750:0.550,0.500,1.43 \
        --key 0.855:0.150,0.560,1.43 --key 0.856:0.520,1.090,2.00 \
        --key 0.959:0.431,1.033,2.00 --key 1.000:0.431,1.033,2.00 \
        --turn 0.340,0.401,2 --turn 0.637,0.698,3

Read as beats, at the reference's rhythm — nine of them in 11.5 s, none longer
than 1.3 s:

| time | |
|---|---|
| 0.0–0.5 s | held on the head of page 1: the title and the opening clause |
| 0.5–1.6 s | the sheet goes left, ~390 px/s |
| 1.6–2.3 s | held |
| 2.3–3.5 s | diagonally right and up, ~550 px/s — reading down the page |
| 3.5–3.9 s | held |
| **3.9–4.6 s** | **the page turns**, and page 2 is underneath |
| 4.6–6.2 s | left, then held across the shot cut at 5.42 s |
| 6.2–7.3 s | right and up |
| **7.3–8.0 s** | **the second turn**, to page 3 |
| 8.0–9.8 s | held, then left |
| 9.8 s | closer, **on a cut** — the reference never zooms |
| 9.8–11.5 s | a slow slide that ends on Keitel's signature |

### The turn

`--turn t0,t1,page` folds the sheet over instead of swapping the image. A cut
between two scans says "another page"; it does not say a hand. What says a hand
is the crease: a seam crossing the frame, the lifted part of the sheet mirrored
back over itself and foreshortened, its underside darkening as it leans, and a
shadow thrown on the page it uncovers. It is all 2D compositing — the sheet is
never modelled — which holds up at 0.7 s per turn.

The clip is 344 frames against the 338 the two shots consume, so the settle
lands at the end of the second shot rather than after it. **If the narration is
re-recorded**, read the new shot lengths from `generated/report.txt`, set
`--frames` to their sum plus six, and update `in` on the 1:32 row of
`shots.csv`.
