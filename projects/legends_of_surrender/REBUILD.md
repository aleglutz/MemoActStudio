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

Page 2 is not in the reel: one turn, page 1 to page 3. The scans differ (1024x1410
and 1860x2560), so `s` differs to hold one reading size — 2.60 and 1.43 both give
a sheet about 2660 px wide, 27 text lines in frame, the reference's own framing.
**Page 3 is at one scale for its whole section**, which is what removes the seam:
the camera reaches Keitel by travelling, never by getting closer.

Magnification is real — 2.6x on the klein scan — and deliberate: `UPSCALE.md`
forbids silent enlargement, not enlargement, and the factor is printed every run.
It is plain Lanczos, which invents nothing. When the scans are upscaled, divide
every `s` by the upscale factor; the framing does not move.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 344 --ease cosine \
        --key 0.000:0.500,0.950,2.60,1 --key 0.035:0.500,0.950,2.60 \
        --key 0.122:-0.231,0.950,2.60 --key 0.166:-0.231,0.950,2.60 \
        --key 0.279:1.231,0.863,2.60  --key 0.314:1.231,0.863,2.60 \
        --key 0.384:0.550,0.780,2.60 \
        --key 0.414:0.550,0.780,1.43 \
        --key 0.528:-0.066,0.204,1.43 --key 0.567:-0.066,0.204,1.43 \
        --key 0.672:0.796,0.309,1.43  --key 0.715:0.796,0.309,1.43 \
        --key 0.942:0.328,0.929,1.43  --key 1.000:0.328,0.929,1.43 \
        --turn 0.384,0.414,2

| time | | speed |
|---|---|---|
| 0.0–0.4 s | held on the head of page 1 | |
| 0.4–1.4 s | the sheet goes left | 790 px/s |
| 1.4–1.9 s | **held on the "10" in blue pencil**, top right | |
| 1.9–3.2 s | back right and down, a whip | 1220 px/s |
| 3.2–3.6 s | **held on the tape and punch holes** at the left margin | |
| 3.6–4.4 s | one more shift left, to mid-page | 840 px/s |
| **4.4–4.75 s** | **the page is turned over** — 0.34 s, and page 3 is underneath | |
| 4.75–6.05 s | down to de Lattre de Tassigny, bottom right | 990 px/s |
| 6.05–6.5 s | held | |
| 6.5–7.7 s | left to Spaatz, bottom left | 790 px/s |
| 7.7–8.2 s | held | |
| 8.2–10.8 s | the long rise to Keitel's autograph | 500 px/s |
| 10.8–11.5 s | held on it | |

The two detail beats are the reason the sequence reads as someone handling a
document rather than a camera executing a move: a pencilled "10" that some
archivist wrote, and the tape somebody used to reinforce the punch holes. The
signatures are what the shot is about; those two say the thing is an object that
has been filed, lent and repaired.

Coordinates on the page, if a beat ever needs re-aiming: the "10" sits at
(0.95, 0.035), the tape at (0.035, 0.31); on page 3, de Lattre (0.73, 0.655),
Spaatz (0.38, 0.60), Keitel (0.57, 0.275). A key that centres page point
(px, py) is `cx = 0.5 + (0.5 - px) * pw / 1080`, `cy = 0.5 + (0.5 - py) * ph / 1920`,
clamped so the sheet still covers the frame.

### The turn

`--turn t0,t1,page` folds the sheet over instead of swapping the image. A cut
between two scans says "another page"; it does not say a hand. What says a hand
is the crease: a seam crossing the frame, the lifted part of the sheet mirrored
back over itself and foreshortened, its underside darkening as it leans, and a
shadow thrown on the page it uncovers. Each sheet keeps its own scale through
the turn — they differ only because the scans do, and interpolating between them
would shrink the page while it turns, which is the one thing paper does not do.

The clip is 344 frames against the 338 the two shots consume, so the settle
lands at the end of the second shot rather than after it. **If the narration is
re-recorded**, read the new shot lengths from `generated/report.txt`, set
`--frames` to their sum plus six, and update `in` on the 1:32 row of
`shots.csv`.
