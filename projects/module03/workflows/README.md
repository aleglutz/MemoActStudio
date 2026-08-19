# Module 03 workflows — what each graph does and what it costs

Four graphs, one thirty-second piece of archival film, four rising degrees of
intervention. All of them read `module03_master_30s.mp4`, which must sit in
ComfyUI's `input/` folder (see `../REBUILD.md`).

They are API-format, so `tools/module03_render.py` can submit them directly and
so they can be dropped into the Cloud UI, which converts API format on drop.
There are no comment keys inside the JSON: ComfyUI validates every top-level key
as a node and rejects anything else, so the commentary lives here instead.

## L1 — `L1_quote_api.json` · contextualisation

`VHS_LoadVideo → DrawText+ → VHS_VideoCombine`. No model, no GPU.

The quoted lines are transcribed from the signed English copy of the Act of
Military Surrender in this repository (`projects/legends_of_surrender/images/
GIoS_Wehrmacht_Signed_En.jpg`). Nothing is paraphrased and nothing is machine-
read off the footage. That is the project's standing rule — the document is
ground truth, alignment only decides *when* a line appears — and level 1 is the
place to say why the rule exists before three later levels start inventing.

**What the stock graph cannot do, and why that matters.** One `DrawText+` holds
one string over one frame range, so three quotes are three runs concatenated,
and moving a caption by half a second means editing `skip_first_frames` and
re-rendering that range. `background_color` draws no real plate, so a caption
over a bright frame has only its shadow to survive on. This is `GAPS.md` #3 from
the inside: it is the argument for `nodes_subs.py` and libass, not a detail.

The production path renders the same three quotes properly — `../quotes.ass`
through ffmpeg's libass filter, all timing in one file, real plate, one pass.
Compare the two on screen; the comparison *is* the lesson.

> On this machine ffmpeg's `drawtext` segfaults (broken fontconfig), so the
> libass filter is not merely preferred, it is the only text path that runs.

## L2 — Comfy Cloud template `audio_stable_audio_3_medium` · sound

Not a local graph: Stable Audio 3 Medium, open weights, run on Cloud from the
stock template, one job per layer. Cost is independent of frame count, which is
what makes this the one level a room of thirty students can actually run.

The footage is silent — not quiet, *silent*: its AAC track measures −91 dB mean
and max end to end, every sample in one histogram bin. So nothing here is being
restored. Every sound in the result is manufactured, and manufactured sound is
the least-flagged fabrication in museum practice, because it registers as
atmosphere rather than as content. Nobody captions a room tone.

`use_reprompt` is set false on purpose: with it on, an LLM rewrites the prompt
before the audio model sees it, and a teaching artifact should run the words
that are written down.

`ElevenLabsTextToSoundEffects` is also on Cloud and is better at discrete foley
hits. It is a partner API, so under SPEC §5 it is admissible as a demonstration
and never inside the pack — and it must be named on screen when shown.

## L3 — `L3_restore_api.json` · upscale / restoration

`VHS_LoadVideo → UpscaleModelLoader → ImageUpscaleWithModel → ImageScaleBy →
SaveImage`. Eight frames per submission.

Chunked because one 4272×3200 float32 intermediate is 164 MB and a 900-frame
batch is not a thing any machine holds. Eight is not a guess — thirty ran fine
cold and then failed ninety frames in, and the retry at eight took the whole
server down with a segfault inside the upscale node. The allocation is on the
*host*, not the card, and two things were eating the host: this build pins
24.5 GB for dynamic VRAM, and the node cache holds every chunk's output. So the
server runs with `--disable-pinned-memory --cache-none` (which restored 54 GB of
54 free) and `tools/module03_render.py` calls `/free` between chunks. Chunking
bounds one chunk's peak; only the `/free` bounds their sum.

`--cache-none` fixes a second thing that had been silently wrong: with caching
on, re-submitting an identical graph is a cache hit, and a cache hit skips
`SaveImage` — so the first chunk of a re-run writes no files at all and the gap
only shows up as a frame count that is thirty short.

Measured: ~2.2 s/frame warm on a 3090 Ti, so the full thirty seconds is about
half an hour.

The 4× result is scaled back to native size, so nothing is enlarged past what
the film holds — the project's "never silently upscale" rule is about silence,
not abstinence (`docs/UPSCALE.md`). What changes is texture, and texture is
invented.

**The model choice is the content of this level.** `docs/UPSCALE.md` measured
five 4× models and picked `4x_foolhardy_Remacri` because it invents least while
still recovering real detail; it disqualified `4x-UltraSharp` and
`4x_NMKD-Siax` for archival faces, which they rework into waxy invented
features. Those two are among the models Comfy Cloud carries — and **Remacri is
not on Cloud at all**. The honest tool is the one the students cannot reach by
default. Say that out loud rather than around it.

## L4 — `L4_colorize_api.json` · colourisation

Qwen-Image-Edit (Apache-2.0) as an instruction editor, one frame per submission.

**There is no colouriser on Comfy Cloud** — no DDColor, no DeOldify; searching
returns only ControlNet *Recolor* preprocessors, which are not colourisers. So
this level runs locally, and its Cloud version is a still, not a clip.

Two fabrications stack here, and only one of them is obvious. The first is that
colour is invented. The second is in the prompt itself: it *tells* the model
which colours are correct — olive-brown tunics, gold shoulder boards, field
grey. That is a historical claim, typed by the operator, laundered through a
model, and delivered as if the film had recorded it.

Per-frame editing has no temporal consistency, so a thirty-second render
flickers: each frame decides its own colours. The flicker is not a defect to
apologise for. It is the argument, visible.
