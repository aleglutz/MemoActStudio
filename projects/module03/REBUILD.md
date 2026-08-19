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

## 2b. Level 2 — sound

Weights, once each:

```
# ungated
curl -L -o <ComfyUI>/models/checkpoints/stable-audio-open-1.0.safetensors   https://huggingface.co/Comfy-Org/stable-audio-open-1.0_repackaged/resolve/main/stable-audio-open-1.0.safetensors

# gated -- accept the licence at huggingface.co/stabilityai/stable-audio-open-1.0
# first, then authenticate. The `hf` CLI will not run on the embedded Python
# (it imports venv, which the embeddable distribution omits); call login directly:
#   python -c "import huggingface_hub; huggingface_hub.login()"
curl -L -H "Authorization: Bearer $HF_TOKEN"   -o <ComfyUI>/models/text_encoders/t5_base.safetensors   https://huggingface.co/stabilityai/stable-audio-open-1.0/resolve/main/text_encoder/model.safetensors
```

Four layers, through `workflows/L2_sfx_api.json` with these seeds and lengths —
the two marked *kept* replaced first takes that were rejected on their
spectrograms (a tonal hum where shutter clacks belonged, and a flat-hiss bed):

| layer | seconds | seed | |
|---|---|---|---|
| bed | 32 | 550919 | kept, second take |
| paper | 14 | 220805 | |
| cameras | 16 | 880431 | kept, third seed |
| steps | 12 | 440108 | |

Then the mix — placement and level are editorial, not generated:

```
ffmpeg -i bed.flac -i paper.flac -i cameras.flac -i steps.flac -filter_complex " [0:a]atrim=0:30,asetpts=PTS-STARTPTS,volume=2.2[bed]; [1:a]atrim=0:5,asetpts=PTS-STARTPTS,volume=0.55,adelay=3400|3400[p1]; [1:a]atrim=6:12,asetpts=PTS-STARTPTS,volume=0.45,adelay=15200|15200[p2]; [2:a]atrim=0:13,asetpts=PTS-STARTPTS,volume=0.30,adelay=17000|17000[cam]; [3:a]atrim=0:6,asetpts=PTS-STARTPTS,volume=0.22,adelay=11000|11000[st]; [bed][p1][p2][cam][st]amix=inputs=5:normalize=0:duration=first, loudnorm=I=-20:TP=-2:LRA=11,atrim=0:30,asetpts=PTS-STARTPTS[out]"  -map "[out]" -ar 48000 -ac 2 sources/L2_mix.wav

ffmpeg -i sources/master_30s.mp4 -i sources/L2_mix.wav -map 0:v -map 1:a        -c:v copy -c:a aac -b:a 192k -shortest out/L2_sound.mp4
```

`normalize=0` matters: `amix` otherwise divides every input by the number of
inputs, and the carefully-set levels above all collapse together.

## 3. Level 3 — restoration

The film is 1068×800 and this level doubles it to 2136×1600. That enlargement is
the point of the level, so nothing here shrinks it back.

Start the server with two flags, or it will not survive the run
(`workflows/README.md` says why):

```
python -I ComfyUI/main.py --windows-standalone-build        --disable-pinned-memory --cache-none
```

Then, about fifteen minutes on a 3090 Ti for ten seconds of film:

```
python tools/module03_render.py        projects/module03/workflows/L3_restore_api.json        --frames 300 --chunk 8 --prefix module03/L3/        --server http://127.0.0.1:8189
```

Frames land in `<ComfyUI>/output/module03/L3/`, already in the right order by
filename. Count them before encoding — 300 is right, and anything short means a
run failed quietly.

```
ffmpeg -framerate 30 -pattern_type glob -i "<ComfyUI>/output/module03/L3/*.png"        -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p        projects/module03/out/L3_restored.mp4
```

For the comparison, the original has to be enlarged too — otherwise you are
comparing sizes instead of methods. Enlarge it with lanczos, which invents
nothing, and that becomes the honest baseline:

```
ffmpeg -i sources/master_30s.mp4 -t 10        -vf "scale=2136:1600:flags=lanczos"        -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -an        out/L3_native_2x.mp4
```
