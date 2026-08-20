# Continuing the reel on another machine

Written 2026-08-12, to move `legends_of_surrender` from the Windows ComfyUI
install to a MacBook and carry on there. Nothing here is Mac-specific except
`brew`; the same steps work on any machine with Python and ffmpeg.

## The short answer about subtitles

**Subtitles are not adjusted by hand, and re-timing is not a separate job.**
Replace the narration file, re-run the generator, re-render. Alignment recomputes
every shot boundary and every word timing from the new audio; `memoacts_core.subs`
cuts captions at those word timings, so the caption track re-fits itself. There
is no timing stored anywhere that survives the new read.

    python tools/generate_shots.py --project projects/legends_of_surrender --lang en
    python tools/render_reel.py    --project projects/legends_of_surrender

The edit decisions live in `shots.csv` and are keyed to script cues, not to
seconds, so none of them move when the timing does.

## What has to travel, and what does not

The repository is **316 KB** and holds everything decided: the code, `script.md`,
`shots.csv`, `SOURCES.md`, the vendored caption font, and the Natural Earth
geodata. Media is deliberately not versioned (`.gitignore`), so it travels
separately — but most of it does not need to travel at all:

Since 2026-08-12 the code syncs through a private GitHub repository, so only
media has to be carried by hand. The `git bundle` route below still works if
you would rather not clone.

| | Size | Travels? |
|---|---|---|
| The repository, full history | 316 KB | **no** — `git clone`, or a `git bundle` file |
| `images/` | 18 MB | **yes** — sources, not reproducible |
| `video/MBK_KAPFILM_FINAL.mp4` | 169 MB | **an excerpt is enough**; the reel uses 6.68 s from 0:40 |
| `maps/*.mp4` | 4.6 MB | no — regenerate, see below |
| `composites/S14_three-band.mp4` | 18 MB | no — regenerate, see below |
| `narration.wav` | 6.9 MB | no — being replaced |

The generated clips are rebuilt from the images plus `assets/geo/`, which is in
the repository. Regenerating is also the honest habit: they are outputs, and a
copied output can silently disagree with the inputs it claims to come from.

## Setting up

The code lives in a private repository, so the clone is ordinary:

```bash
git clone https://github.com/aleglutz/memoacts-studio.git MemoActStudio
cd MemoActStudio

brew install ffmpeg                  # libx264 and libass; both are required

python3 -m venv .venv
source .venv/bin/activate
pip install stable-ts num2words numpy pillow
```

`stable-ts` pulls in torch and a Whisper model — a few GB, and the model
downloads on first run. It is the aligner (`ALIGNERS.md`), and the only heavy
dependency. **ComfyUI is not needed** for either command above; the node layer
exists for the GUI, and the CLI path is complete without it.

Then put the media back:

    projects/legends_of_surrender/images/      <- copied across
    projects/legends_of_surrender/video/       <- the excerpt
    projects/legends_of_surrender/narration.wav  <- the NEW read

## Rebuilding the generated clips

Both are checked into no repository and must exist before a render.

```bash
python tools/render_map.py --out projects/legends_of_surrender/maps \
    --name map_baltics --frames 360 \
    --highlight Latvia Estonia Lithuania

python tools/render_map.py --out projects/legends_of_surrender/maps \
    --name map_poland_ukraine --frames 360 \
    --highlight Poland Ukraine --already Latvia Estonia Lithuania

python tools/render_bands.py --project projects/legends_of_surrender \
    --name S14_three-band --frames 360 \
    --band GIoS_Wehrmacht_Signed_Ru.jpg:0.277:zoom_in:0.08 \
    --band Wehrmacht_in_Karlshorst.jpg:0.482:pan_lr:0.10 \
    --band GIoS_Wehrmacht_Signed_En.jpg:0.530:zoom_out:0.08
```

360 frames is 12 s at 30 fps, comfortably longer than either shot needs. A clip
shorter than its shot is an error, not a freeze — `memoacts_core.video` says how
much footage was wanted and from where.

## Reading the result

`generated/report.txt` is the thing to read after the new alignment:

- **`confidence`** per shot — now meaningful. Every current figure is `0.00`
  because the reel has only ever been generated with `--no-align` against a
  Kokoro scratch read.
- **`[DRIFT ±Ns]`** — how far the aligned start sits from the cue written in
  `script.md`. Today it reaches −10 s, purely because the scratch read is paced
  differently from the cues. With the real read it should collapse; if it does
  not, the cues in `script.md` are stale and worth rewriting (they are advisory
  — alignment overrides them).
- **`[CLAMPED]`** and the render's `x… enlargement` warnings — unchanged by a new
  read; they are properties of the images. Six are known and listed in the
  session notes, the largest being the Treptow frame at ×2.24.

## Open items that travel with the project

- `SOURCES.md` — the Loznitsa frame at 1:59 is neither public domain nor ours,
  and needs clearance or a deliberate quotation with an on-screen credit.
- Shot 1:10 uses a Potsdam photograph (16 July) under a line about 8 May.
- `Karlshorst_Signing.jpg` appears three times and enlarges ×1.37.
- `GIoS_Wehrmacht_Signed_Ru_p1.jpg` is the "klein" scan; a full-size one would
  let the shot crop rather than band.
