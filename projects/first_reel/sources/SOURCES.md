# Sources — first_reel

Every project in this repository carries this file, because a reel made of
other people's material has to be able to say whose. This one is the easy case
and it is deliberately the easy case: **nothing here came from anywhere else.**

## Pictures

`images/01_script.jpg`, `02_timings.jpg`, `03_caption.jpg`, `04_folder.jpg`

Four typed sheets, drawn by this pack. The paper is synthesised —
`memoacts_core.page.paper()` builds it out of value noise, so there is no scan
behind it and no archive to credit. The type is set in Special Elite
(`assets/fonts/SpecialElite-Regular.ttf`, Apache-2.0, licence vendored beside
the font). The text on each sheet is in `pages/`, in git, and `REBUILD.md`
regenerates the pictures from it in about fifteen seconds.

**Licence: GPL-3.0-or-later, the same as the code that drew them.** They may be
copied, altered and published with the repository, which is exactly what an
example has to allow.

## Recording

`narration.wav` — the four scenes of `script.md`, spoken. 20.31 s, mono,
24 kHz, 24-bit PCM, written by **MemoActs — Set Narration**, which is why it
kept the rate and channel count it was made at.

**Synthesised, not recorded**, with **Kokoro** (`kokoro-onnx` 0.4.2, through
`custom_nodes/comfyui-kokoro`). Kokoro-82M's weights are Apache-2.0 and its
voices ship with them, so the audio carries no separate claim and travels with
this repository like the code does.

That choice is the example's, not the pipeline's. A synthetic voice is a
convenience for a fixture that has to live in git and be regenerable by
anybody; nothing in the pack prefers one, and forced alignment does not care —
it is measuring a waveform against a text it was given either way. A student's
own voice is the ordinary case and the workshop's.

## Sound effects

`sfx/` is empty, and the reel has no `sfx.csv`. The sound design is a separate
stage (`docs/SOUND_DESIGN.md`) and this example does not use it.
