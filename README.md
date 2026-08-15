# comfyui-memoacts — running a reel

The short version of `docs/CONTINUE_ON_MAC.md`: what to type, in order, from a
cold start. Every command runs from the repository root.

ComfyUI is **not** needed for any of this. The node layer exists for the GUI;
the command line path is complete on its own.

---

## 0. Every session: activate the virtual environment first

```bash
cd ~/Documents/MemoActs/MemoActStudio
source .venv/bin/activate
```

The prompt changes to `(.venv) …`. **This is per terminal window** — a new tab
starts without it, and then `python` is macOS's own interpreter, which has none
of the dependencies. That is what a `ModuleNotFoundError: stable_whisper`
means, every time.

Check it took:

```bash
python -c "import stable_whisper, num2words, numpy, PIL; print('ok')"
```

`deactivate` leaves the environment when you are done.

## 1. One-time setup on a new machine

```bash
brew tap homebrew-ffmpeg/ffmpeg          # see below — not the core formula
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install stable-ts num2words numpy pillow
```

**Not `brew install ffmpeg`.** Homebrew's core formula no longer lists libass
among its dependencies, so the ffmpeg it installs has no `subtitles` filter at
all, and the render dies with `No such filter: 'subtitles'` — after every frame
has been generated, which is the expensive place to find out. The
[homebrew-ffmpeg](https://github.com/homebrew-ffmpeg/homebrew-ffmpeg) tap builds
it in by default. If the core formula is already installed, `brew unlink ffmpeg`
first so the tap's binary is the one on PATH.

Verify before rendering anything, not after:

```bash
ffmpeg -version | grep -o libass         # must print libass
ffmpeg -filters | grep -w subtitles      # must print one line
```

`stable-ts` pulls in torch, and the Whisper model downloads on first alignment
(a few hundred MB, cached in `~/.cache/whisper`). It is the only heavy
dependency.

## 2. Put the media in place

Media is never versioned, so it arrives separately:

```
projects/legends_of_surrender/
    images/         stills
    video/          MBK_KAPFILM_FINAL.mp4
    narration.wav   the read
    sources/        masters and originals (ignored by git)
```

**Exactly one `narration.*` file** belongs in the project folder. The generator
looks for `narration.mp3` first and otherwise takes whichever `narration.*` it
finds — two files make the choice arbitrary. Keep the others in `sources/`.

## 3. Rebuild the generated clips

Maps and stacked-frame composites are outputs, not sources: they are rebuilt
rather than copied, so they cannot silently disagree with the images they claim
to come from. Both must exist before a render.

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

360 frames is 12 s at 30 fps — longer than any of those shots needs. A clip
shorter than its shot is an error, not a freeze.

## 4. Align the narration

```bash
python tools/generate_shots.py --project projects/legends_of_surrender --lang en
```

Reads `script.md` and `narration.wav`; writes `generated/shots.json`,
`generated/crops/*.csv` and `generated/report.txt`. Nothing is transcribed —
the script is ground truth and alignment computes timings only.

## 5. Read the report before rendering

```bash
open projects/legends_of_surrender/generated/report.txt
```

Three things to look at:

| | meaning |
|---|---|
| `confidence` | mean word probability per shot. Low means the read and the script disagree there. |
| `[DRIFT ±Ns]` | how far the aligned start sits from the cue written in `script.md`. Cues are advisory; alignment wins. A large drift means the cues are stale, not that the timing is wrong. |
| `[CLAMPED]`, `x… enlargement` | properties of the images, not of the read. A source too small for the frame. |

`shots.json` is a plain file, meant to be read and edited between the two
steps.

## 6. Render

```bash
python tools/render_reel.py --project projects/legends_of_surrender
```

Writes `out/reel.mp4` at 1080×1920, 30 fps, with the `.ass` and `.srt` tracks
beside it. Useful flags: `--no-subs`, `--sub-size 56`, `--plate 0.55`
(subtitle plate opacity), `--on-upscale warn|error|allow`, `--crf 19`.

## 7. Re-recording the narration

Replace `narration.wav` and re-run steps 4 and 6. Nothing else moves:
alignment recomputes every shot boundary and every word timing, captions are
cut at the new word timings, and `shots.csv` is keyed to script cues rather
than to seconds. No timing is stored anywhere that survives the new read.

---

## When it goes wrong

| symptom | cause |
|---|---|
| `ModuleNotFoundError: stable_whisper` | the environment is not active — step 0 |
| `command not found: python` | same; macOS ships `python3` only |
| `ffmpeg: command not found` | step 1 |
| `No such filter: 'subtitles'` | ffmpeg built without libass — step 1, and note it is *not* the core Homebrew formula |
| `No option name near …` in a filter | ffmpeg 8 rejects quoted filter values; `memoacts_core.render` escapes them instead — update the repository |
| every shot reports `cue … matches no block in script.md` | `shots.csv` keys no longer match `script.md`; re-key one of the two |
| `confidence` is `0.00` everywhere | alignment fell back to proportional timing; the log above says why |
| a shot renders as its default | its media is missing — the generator warns by name and carries on |

## Known gap

`shots.csv` references three stacked-frame stills — `S01-02_two-band.png`,
`S07_two-band_bw.png`, `S18_three-cities_bw.png` — that no script in this
repository builds. They were made in ComfyUI with Olm-DragCrop on the Windows
install (`docs/THREEBAND_TOOL.md`). Until they are either copied across or
`render_bands.py` learns to emit stills, those three shots fall back to their
defaults and the render warns.
