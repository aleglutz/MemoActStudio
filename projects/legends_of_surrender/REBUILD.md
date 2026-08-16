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
measured length of the first shot. The page sizes differ, so `s` differs to
keep the sheet the same size on the bed: page 1 is the 1024x1410 "klein" scan
at 1:1, pages 2 and 3 are 1860x2560 at 0.55. Both give a sheet about 1023 px
wide.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru_p2.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 344 --ease linear \
        --key 0.000:0.950,0.400,1.00,1 \
        --key 0.070:0.500,0.470,1.00 \
        --key 0.190:0.500,0.470,1.00 \
        --key 0.244:0.150,0.560,1.00 \
        --key 0.245:0.880,0.360,0.55,2 \
        --key 0.310:0.500,0.480,0.55 \
        --key 0.410:0.500,0.480,0.55 \
        --key 0.472:0.180,0.640,0.55 \
        --key 0.473:0.860,0.320,0.55,3 \
        --key 0.545:0.480,0.490,0.55 \
        --key 0.700:0.480,0.490,0.55 \
        --key 0.790:0.430,0.560,0.55 \
        --key 0.860:0.400,0.600,0.55 \
        --key 0.861:0.400,0.620,1.00 \
        --key 0.982:0.4665,0.6665,1.00 \
        --key 1.000:0.4665,0.6665,1.00

Reading it: each page slides in fast, holds about a second and a half, and is
nudged out — a sheet being repositioned, measured off the reference reel, where
translation runs 400-800 px/s and there is no zoom at all. The page changes are
cuts, at 2.81 s and at 5.42 s. The last change of *scale* is a cut too, at
9.87 s: the framing gets closer without a zoom, and the final 1.4 s is a short
slide that centres Keitel's signature in the upper third.

The clip is 344 frames against the 338 the two shots consume, so the settle
lands at the end of the second shot rather than after it. **If the narration is
ever re-recorded, both numbers move**: read the new shot lengths out of
`generated/report.txt`, set `--frames` to their sum plus six, and update the
`in` value on the 1:32 row of `shots.csv`.
