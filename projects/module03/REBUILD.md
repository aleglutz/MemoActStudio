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

Four layers, through `workflows/L2_sfx_api.json`. The graph carries only the
bed's first prompt; the other three, and the two rewrites, were typed at run
time and are recorded here — without them this section regenerates nothing.

| layer | seconds | seed | prompt |
|---|---|---|---|
| bed | 32 | 550919 | Ambience of a crowded hall: many men murmuring quietly at a distance, low indistinct voices, occasional cough and chair creak, reverberant, no music. |
| paper | 14 | 220805 | A single sheet of stiff dry paper lifted from a wooden table, held, turned over, and set down again. Close, dry, detailed, in a quiet room. |
| cameras | 16 | 880431 | Sharp mechanical camera shutter clicks and clacks, film advance ratchet winding, a flashbulb pop, spaced out with silence between them, recorded in a large reverberant room. Dry transient clicks, no continuous tone. |
| steps | 12 | 440108 | A heavy wooden chair scraping back on a parquet floor, then several slow leather-soled footsteps on parquet in a large echoing room. Close and dry. |

Negative prompt for all four:
`music, melody, singing, instruments, rhythm, beat, speech, dialogue, narration`.

**Bed and cameras are second attempts, and the prompt changed, not only the
seed.** The first bed (seed 114509, the graph's own text) was flat broadband
hiss; the first cameras (seed 330512) was a tonal hum where shutter clacks
belonged. Both rewrites work by naming what the first version missed — the bed
gained the men and the coughs, the cameras gained the silence between the
clicks. The rejects are still on disk and are worth playing beside the keepers.

> **Which file is which.** The rejected first takes are
> `<ComfyUI>/output/module03/L2/bed_00001.flac` and `.../cameras_00001.flac`;
> the takes that were mixed are `.../L2alt/bed_s1_00001.flac` and
> `.../L2alt/cameras_s2_00001.flac`. `paper` and `steps` are the L2 ones. The
> mix command below names them `bed.flac`, `cameras.flac` and so on — copy or
> rename the four keepers to those names first. Every generated file carries its
> own graph in its metadata, so `ffprobe -show_entries format_tags` on any of
> them recovers prompt and seed.

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

Then, about 3.7 seconds a frame on a 3090 Ti — 55 minutes for the whole cut.
`--start` resumes, so a run that dies costs one chunk, not the hour:

```
python tools/module03_render.py        projects/module03/workflows/L3_restore_api.json        --frames 901 --chunk 8 --prefix module03/L3/        --server http://127.0.0.1:8189
```

Frames land in `<ComfyUI>/output/module03/L3/`, already in the right order by
filename. Count them before encoding — 901 is right, and anything short means a
run failed quietly.

The frames do not form a plain number sequence — each chunk restarts its counter
— and **this ffmpeg cannot glob** ("globbing is not supported by this
libavformat build"). Both problems go away with a list file, which also fixes
the order explicitly instead of trusting a wildcard:

```
cd <ComfyUI>/output/module03/L3
ls *.png | sort | awk -v d="$PWD/" '{print "file '" d $0 "'"; print "duration 0.0333333"}' > list.txt
ls *.png | sort | tail -1 | awk -v d="$PWD/" '{print "file '" d $0 "'"}' >> list.txt
```

Write Windows paths (`C:/...`) into it, not git-bash paths (`/c/...`) — ffmpeg
is a native binary and does not understand the second kind. The last file is
repeated on purpose: the concat demuxer gives the final entry no duration.

```
ffmpeg -f concat -safe 0 -i list.txt -r 30 -frames:v 901        -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p        projects/module03/out/L3_restored_30s.mp4
```

`-frames:v 901` is not decoration. The repeated last entry and the rounding of
`0.0333333` against a true 1/30 add up to two extra frames, and the clip comes
out 30.10 s against the master's 30.03. Cutting it to the master's own frame
count keeps the two files comparable frame for frame. The two comparisons need the same
guard plus `fps=30` in the filter chain: fed by `concat`, ffmpeg negotiated
**50 fps** for them and wrote every frame twice. The duration looked right, which
is exactly why it was easy to miss — check `r_frame_rate`, not the length.

For the comparison, the original has to be enlarged too — otherwise you are
comparing sizes instead of methods. Enlarge it with lanczos, which invents
nothing, and that becomes the honest baseline:

```
ffmpeg -i sources/master_30s.mp4        -vf "scale=2136:1600:flags=lanczos"        -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -an        out/L3_native_2x_30s.mp4
```

### The two comparisons

Whole frames side by side are useless on a projector — at this size each half
lands too small to read. Both comparisons therefore work on the same patch of
picture, `1000×800` at `x=600, y=300`, which holds the signing table.

Side by side, plain enlargement left, restored right:

```
ffmpeg -f concat -safe 0 -i list.txt -r 30 -i sources/master_30s.mp4 -filter_complex        "[1:v]scale=2136:1600:flags=lanczos,crop=1000:800:600:300[a];         [0:v]crop=1000:800:600:300[b];[a][b]hstack,fps=30"        -r 30 -frames:v 901 -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -an        out/L3_ab_zoom_30s.mp4
```

One frame cut down the middle, plain left, restored right, with a line on the
seam so nobody has to guess where it is:

```
ffmpeg -f concat -safe 0 -i list.txt -r 30 -i sources/master_30s.mp4 -filter_complex        "[1:v]scale=2136:1600:flags=lanczos,crop=1068:1600:0:0[a];         [0:v]crop=1068:1600:1068:0[b];[a][b]hstack,         drawbox=x=1067:y=0:w=2:h=1600:color=white@0.5:t=fill,fps=30"        -r 30 -frames:v 901 -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -an        out/L3_split_30s.mp4
```

> The ten-second versions of all four files — `L3_restored.mp4`,
> `L3_native_2x.mp4`, `L3_ab_zoom.mp4`, `L3_split.mp4` — are still in `out/` and
> stay there. Nothing in that folder is deleted; see the module README.
