# workshop_starter

A short example project, used as the first exercise of the September workshop.
Its script describes what the pipeline is doing to it while it runs, so a
first-time user can compare what they read with what they see.

Media is not versioned (see `.gitignore`), so this file lists what has to be
added before the project will run. **These are facilitator steps, done once per
machine image.**

## Files required in `sources/`

| File | Requirement | Purpose |
|---|---|---|
| `narration.wav` | The six blocks of `script.md`, read aloud. About 50 seconds | Alignment needs a recording of the script. Recording it on the workshop machine is sufficient |
| `images/01_wide.jpg` | Landscape, at least 2000 px wide | Has horizontal headroom, so shots 1 and 4 pan |
| `images/02_tall.jpg` | Portrait, at least 2000 px tall | Has headroom for a zoom, so shots 2 and 5 push in |
| `images/03_small.jpg` | **Deliberately undersized**, about 800x1000 | Triggers the resolution guard. The shot report flags it, the shot-table editor shows `max_zoom` below 1.00, and the render warns with the enlargement factor |

The subject of the images does not matter; their dimensions do. If a starter
image is ever reused in published material, record its source in
`sources/SOURCES.md` first.

## Running it

1. Copy the four files into `sources/` as listed above.
2. Open `example_workflows/reel_stills.json`, select `workshop_starter` in the
   Project node, and run.

## Expected result

- 6 shots, and a drift of a few milliseconds between video and narration.
- The frame count is the recording's duration times 30 — a 50-second reading
  gives roughly 1500 frames. There is no fixed number to check against; the
  check is that the reel matches the recording.
- One warning naming `03_small.jpg`, with an enlargement factor near 1.9x. This
  is expected behaviour, not a fault.
- The captions reproduce `script.md` exactly.

A large drift means the recording and the script have diverged. Re-record the
block that drifted rather than adjusting timings.
