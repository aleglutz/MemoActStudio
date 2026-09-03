# REBUILD — first_reel

The example the README walks. **This is the one project whose media is in
git**, because a quickstart that cannot be run is not a quickstart: a stranger
clones the repository, opens two graphs and gets a film, and that same walk is
how a September machine is smoke-tested.

Everything below regenerates from files that are in git. Nothing here needs a
scan, a stock library or anybody's archive.

## What it is

Four scenes, 22.2 seconds, 665 frames at 1080×1920. The script is about what
the tool does, so the example teaches while it demonstrates, and each picture
is the document the scene is talking about.

## The size budget: 4 MB

Stated here so the next person knows the constraint exists rather than
discovering it. Current: four pictures at ~470 KB each (1.84 MB) plus a
22-second mono recording (~0.95 MB) — about 2.8 MB. **A picture that pushes the
project past 4 MB does not belong in this example**; make a second project for
it and leave this one small.

That is why the pictures are JPEG at quality 88 and not PNG: the same four
sheets as PNG are 3.2 MB *each*, because synthesised paper is noise and noise
does not compress.

## Pictures — `sources/images/*.jpg`

Sources are in `sources/pages/*.md`, typed verbatim onto synthesised paper
(`memoacts_core/page.py`). From the repository root:

```
python_embeded\python.exe tools\render_page.py ^
    --page projects\first_reel\sources\pages\S01_script.md ^
    --out  <scratch>\S01_script.png
```

…and the same for `S02_timings`, `S03_caption`, `S04_folder`. Then convert to
JPEG, which is the step that keeps the project inside its budget:

```python
from PIL import Image
Image.open("<scratch>/S01_script.png").convert("RGB").save(
    "projects/first_reel/sources/images/01_script.jpg",
    quality=88, optimize=True, subsampling=0)
```

**The sheet is 1500×2400 on purpose.** A 9:16 window inside it is 1350 px wide
— 1.25× the 1080 px output, so nothing is ever enlarged — and the 31-character
column fits inside that window with its left margin, which a wider sheet does
not: the first attempt was 2400×3400 and the reel cut the first two characters
off every line.

## Recording — `sources/narration.wav`

The four scenes of `script.md`, read aloud, mono. Made the way the README tells
a stranger to make one: `example_workflows/voice.json`, with **MemoActs — Set
Narration** at the end of the chain writing into this folder.

## Generated — `generated/`, `out/`

Both are ignored by git and both are deletable. To remake them:

```
python_embeded\python.exe tools\generate_shots.py --project projects\first_reel --lang en
python_embeded\python.exe tools\render_reel.py   --project projects\first_reel
```

Or, which is the point of the example, the same two steps as graphs:
`example_workflows/voice.json` then `example_workflows/reel_stills.json`, with
the edit made in the **Storyline** panel.

Expect: 4 shots, 665 frames, 22.167 s of video against 22.156 s of narration —
drift +11 ms — 12 subtitle cues, and no enlargement warnings, every shot at
`max_zoom 1.25x`.

## The edit — `shots.csv`

Four rows, and between them they cover most of what the column set can say:

| shot | picture | motion | why |
|---|---|---|---|
| 1 | `01_script.jpg` | `static` | it is meant to be read |
| 2 | `02_timings.jpg` | `zoom_in` + `focus` | the reel's one focus, ending on the timings table |
| 3 | `03_caption.jpg` | `static` | the caption underneath says the same words |
| 4 | `04_folder.jpg` | `zoom_out` | pulls back off the file list as the reel ends |

The focus on shot 2 is `0.43 0.30 0.72`: centre at 43 % across and 30 % down,
ending on 72 % of the sheet's width. The other three take the whole sheet,
which is the widest a 9:16 window can be inside it.
