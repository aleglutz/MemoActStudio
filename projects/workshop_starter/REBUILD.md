# Rebuilding `workshop_starter`

The first project of the September workshop: short on purpose, and about
itself. A student renders this before touching their own material, so that when
their own material goes wrong they have already seen what right looks like.

Media is never versioned (`.gitignore`), so this file is how the project comes
back. **Everything below is a facilitator task, done once per machine image.**

## What has to be in `sources/`

| File | What it must be | Why that and not something else |
|---|---|---|
| `narration.wav` | the six blocks of `script.md`, read aloud, ~50 s | The reel is cut to a voice. A recording made on the workshop machine is fine and takes two minutes |
| `images/01_wide.jpg` | a landscape photograph, at least 2000 px wide | Wide sources have room to travel sideways, so shot 1 pans and shot 4 pans back |
| `images/02_tall.jpg` | a portrait photograph, at least 2000 px tall | Tall sources have room to push in, so shots 2 and 5 zoom |
| `images/03_small.jpg` | **deliberately too small** — around 800×1000 | This is the teaching one. The shot report flags it, the editor shows `max_zoom` below 1.00, and the render warns. A student should meet the resolution guard on the first project, not on their own |

Any three pictures will do. They are not the subject; the subject is the
pipeline. Rights are unfussy here precisely because nothing leaves the room —
if a starter image ever appears in published material, put it in `SOURCES.md`
first.

## Making it

1. Drop the four files in as above.
2. Open the workflow (`example_workflows/reel_stills.json`), pick
   `workshop_starter` in the Project node, and run.

That is the whole procedure, and it is the same one the students follow. There
is no command to type.

## What a correct run looks like

- **6 shots**, and a drift of a few milliseconds. The frame count is not a
  fixed number to check against — it is your recording's length times 30, so a
  50-second read gives about 1 500 frames. That the reel matches the recording
  is the check; how long the recording is, is your business.
- One warning naming `03_small.jpg` and an enlargement factor near 1.9×.
  **That warning is the point**, not a fault to fix.
- The captions read exactly what `script.md` says.

If the drift is large, the recording and the script have diverged — re-read the
block that drifted rather than editing the timings.
