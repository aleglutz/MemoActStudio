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

## L2 — `L2_sfx_api.json` · sound

`CheckpointLoaderSimple + CLIPLoader → CLIPTextEncode ×2 → EmptyLatentAudio →
KSampler → VAEDecodeAudio → SaveAudio`. Stable Audio Open 1.0, open weights,
trained largely on Freesound's CC0 library — which is why it is a sound-effects
model and not a music model, and why `SURVEY.md` §6b adopted it.

Cost does not scale with frame count: each layer took **6 s of GPU** regardless
of whether it was asked for 12 seconds of audio or 32. That is what makes this
the one level a room of thirty students can run at once.

**Two obstacles, both worth knowing before a seminar.** The weights are behind a
licence gate on Hugging Face, so a student needs an account and an accepted
licence — except that the model itself is mirrored ungated at
`Comfy-Org/stable-audio-open-1.0_repackaged`, and only the T5 text encoder has
to come from the gated Stability repo. And the repackaged checkpoint carries the
diffusion model and the VAE but **no text encoder**, so `CheckpointLoaderSimple`
returns `CLIP = None` and the graph fails at the first `CLIPTextEncode` with a
message that blames the checkpoint. T5 is loaded separately, by `CLIPLoader` with
type `stable_audio`.

**The footage is silent — not quiet, silent.** Its AAC track measures −91 dB mean
*and* max end to end, every sample in one histogram bin. So nothing here is
restored. Every sound in the result is manufactured, and manufactured sound is
the least-flagged fabrication in museum practice, because it registers as
atmosphere rather than as content. Nobody captions a room tone.

Four layers are generated and mixed in ffmpeg — bed, paper, press cameras, chair
and footsteps — because nothing places a sound at a timecode inside the graph.
That mix is the level's honest admission: the model makes material, an editor
still decides when the shutter fires.

**Judging takes ears, and a spectrogram is only evidence.** The first `cameras`
take came back with horizontal harmonic bands — a tonal hum rather than shutter
clacks — and was rejected on that reading and re-rolled; of three new seeds the
one with spaced, isolated transients was kept and the suspiciously metronomic one
was not. The same pass replaced a `bed` that was flat broadband hiss. Seeds are
recorded in the mix recipe so both the keepers and the rejects can be reproduced.

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

**Asked to colourise, the model does not colourise — it redraws.** At denoise 1.0
frame 300 came back as a different man: a new face, re-invented medals, no film
grain, the room re-lit, delivered as a plausible modern photograph standing
where a document had been. That frame is kept as the first half of the level.

**And there is no setting between the document and the colour.** At denoise 0.6,
0.4 and 0.25 the archival frame survives intact — exactly what was wanted — but
almost no colour arrives; the instruction barely applies. Colour needs full
denoise, and full denoise is what makes it redraw. Dropping resolution fails the
same way: below roughly a megapixel the edit is not applied and the frame
returns near-neutral. Ten or six steps do not converge and the whole image goes
green. 1068×800 at twenty steps is the floor.

So the model is demoted instead. `tools/module03_colorize.py` keeps the archival
frame's L channel untouched and takes only a/b from the generation: no edge, no
face and no grain can move, and the model drops from author to colour
suggestion. The chroma is blurred four pixels, because colour is low-frequency
anyway and the generation does not land pixel-on-pixel with its source — it
moved things while redrawing, and unblurred a/b smears a shoulder board's red
onto the collar beside it. Where the model recomposed a frame outright, that
bleed is visible and no blur hides it. That is the method's honest limit.

**The flicker is worst where the image carries least.** Nothing in the pipeline
enforces temporal consistency, so each frame decides its own palette. Measured
across twenty consecutive frames, against the source's own frame-to-frame noise
as the floor: the tunic swings 4×, the face 4.6× — and the blank plaster wall
**17.6×**. Where there is nothing to colour, there is nothing to anchor the
invention, and the model is least stable exactly where it is most free. That is
not a defect to apologise for; it is the argument, visible and measurable.

**Cost.** 117–156 s per frame warm on a 3090 Ti, which is why the clip is twenty
frames shown at 10 fps rather than thirty seconds. See `HARDENING.md` before
trusting any faster figure: `--use-sage-attention` quadruples the speed and
renders black.
