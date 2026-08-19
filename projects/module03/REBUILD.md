# Rebuilding Module 03's media

Nothing under `sources/`, `out/` or `stills/` is in git — the same rule the
other projects live under. Everything here regenerates from one archival file
plus the graphs and the caption source that *are* versioned.

## What has to travel

`MBK_KAPFILM_FINAL.mp4` — 177 MB, 7:36, from Museum Berlin-Karlshorst. It lives
at `projects/legends_of_surrender/video/`. It is the only input that cannot be
rebuilt; every path below starts from it.

## 1. The thirty-second master

```
ffmpeg -ss 254 -t 30 -i projects/legends_of_surrender/video/MBK_KAPFILM_FINAL.mp4 \
       -vf "crop=1068:800:106:0" -an \
       -c:v libx264 -crf 12 -preset slow -pix_fmt yuv420p \
       projects/module03/sources/master_30s.mp4
```

`254` is 04:14, where Keitel reads the act. The crop removes the pillarbox: the
transfer is 1280×800 but the picture inside it is 1068×800 at x=106, which
`cropdetect` agrees on across the whole file. `-an` drops the audio track, which
carries nothing — it measures −91 dB mean *and* max end to end.

Then put it where ComfyUI can see it:

```
cp projects/module03/sources/master_30s.mp4 \
   <ComfyUI>/input/module03_master_30s.mp4
```

## 2. Level 1 — quotes

Production path, one pass, all three quotes and their timing in `quotes.ass`:

```
ffmpeg -i sources/master_30s.mp4 -vf "ass=quotes.ass" \
       -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -an \
       out/L1_quotes.mp4
```

Run it from `projects/module03/` so the relative `ass=` path resolves — and do
not add `fontsdir`, which git-bash rewrites into nonsense. On this machine
ffmpeg's `drawtext` filter segfaults on a broken fontconfig; the libass filter
is unaffected and is the project's own subtitle path anyway.

The course-facing version of the same idea is `workflows/L1_quote_api.json`,
run per quote through the graph rather than per file.

## 3. Level 3 — restoration

The server needs two flags or it will not survive the run (`workflows/README.md`
explains why):

```
python -I ComfyUI/main.py --windows-standalone-build \
       --disable-pinned-memory --cache-none
```

Then, ~30 minutes on a 3090 Ti:

```
python tools/module03_render.py \
       projects/module03/workflows/L3_restore_api.json \
       --frames 900 --chunk 8 --prefix module03/L3/
```

Frames land in `<ComfyUI>/output/module03/L3/`, sorted by name, and assemble
with:

```
ffmpeg -framerate 30 -pattern_type glob -i "<ComfyUI>/output/module03/L3/*.png" \
       -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p \
       projects/module03/out/L3_restored.mp4
```

Check the frame count before encoding. 900 is right; anything short means a
chunk failed quietly.
