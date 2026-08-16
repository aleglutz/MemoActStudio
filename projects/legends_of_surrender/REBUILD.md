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

## The act, handled — 1:26 to 1:38

One clip, two shots: 1:26 reads it from 0, 1:32 from 5.420 s, which is the
measured length of the first shot.

**The page fills the frame at every key** — no edge, no bed. That is what sets
`s`, and it is not free: covering 1080x1920 needs the page at least 1.36x its
own pixels for the 1024x1410 page 1, and 0.75x for the 1860x2560 pages 2 and 3.
Going a little past that minimum is what buys room to move: at the values below
each page has roughly 400 px of horizontal and 130 px of vertical travel while
still covering.

So page 1 is magnified 1.45x and the closing framing magnifies page 3 the same
amount. **This is a deliberate, recorded enlargement** — `UPSCALE.md`'s rule is
that it must never be silent, and the tool prints it at every run. It is plain
Lanczos: nothing is invented, the pixels are simply larger. A proper upscale of
the scans is planned separately.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru_p2.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 344 --ease linear \
        --key 0.000:0.660,0.520,1.45,1 \
        --key 0.055:0.400,0.470,1.45 \
        --key 0.190:0.400,0.470,1.45 \
        --key 0.244:0.460,0.530,1.45 \
        --key 0.245:0.620,0.533,0.80,2 \
        --key 0.330:0.620,0.467,0.80 \
        --key 0.430:0.360,0.480,0.80 \
        --key 0.472:0.330,0.520,0.80 \
        --key 0.473:0.350,0.470,0.80,3 \
        --key 0.560:0.550,0.520,0.80 \
        --key 0.700:0.550,0.520,0.80 \
        --key 0.860:0.620,0.500,0.80 \
        --key 0.861:0.520,0.900,1.45 \
        --key 0.982:0.450,0.945,1.45 \
        --key 1.000:0.450,0.945,1.45

Each page moves differently, which is the point — the same gesture three times
reads as a loop rather than as handling:

| | page | movement |
|---|---|---|
| 0.0–2.8 s | 1 | shoved left, fast, then dead still for a second and a half, then a small settle back |
| 2.8–5.4 s | 2 | rises from below, then drifts left across the frame, then a nudge — no hold at all |
| 5.4–9.9 s | 3 | enters diagonally, settles, holds longest, drifts right |
| 9.9–11.5 s | 3 | the framing goes close **on a cut**, then a slow 110 px/s slide centres Keitel's signature |

The reference reel has no zoom in it: translation runs 400–800 px/s and every
change of scale happens on a cut. This follows that.

**After the scans are upscaled**, keep the displayed size and divide: a page
upscaled 4x wants `s` a quarter of the value above (1.45 becomes 0.3625, 0.80
becomes 0.20). The framing is unchanged; only the number of source pixels
behind it grows.

The clip is 344 frames against the 338 the two shots consume, so the settle
lands at the end of the second shot rather than after it. **If the narration is
ever re-recorded, both numbers move**: read the new shot lengths out of
`generated/report.txt`, set `--frames` to their sum plus six, and update the
`in` value on the 1:32 row of `shots.csv`.
