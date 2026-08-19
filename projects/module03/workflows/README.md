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
SaveImage`. Eight frames per run.

**What it makes.** The film is 1068×800. This doubles it, to 2136×1600. Remacri
is a 4× model, so it runs at 4× — the size it was trained for — and then a plain
lanczos reduction brings the result down to 2×. The reduction invents nothing;
it is ordinary arithmetic.

> An earlier version reduced all the way back to 1068×800. That was pointless.
> The reason to run an upscaler is to get more pixels. Give them back and all
> you keep are the model's side effects.

**Why only eight frames at a time.** Inside the chain each frame briefly exists
at 4272×3200, which is 164 MB. Thirty of those at once is 4.9 GB in one block,
and the computer could not find it: the first attempt failed part-way through,
and the retry killed the whole ComfyUI process. The memory is ordinary system
RAM, not the graphics card. Two things were using it up — this build reserves
24.5 GB for itself, and ComfyUI keeps every finished frame in a cache. Start the
server with `--disable-pinned-memory --cache-none` and 54 GB of the 60 come
back. `tools/module03_render.py` also clears memory between runs.

> `--cache-none` fixes a second, quieter problem. With the cache on, sending the
> same graph twice counts as a repeat, and a repeat skips saving the file. The
> only symptom is a folder with fewer frames in it than you asked for.

Cost: about 3 seconds a frame on a 3090 Ti, so ten seconds of film takes roughly
fifteen minutes.

**What an upscaler actually does to archival film.** Two things, and only one of
them is what people expect. It sharpens edges — buttons, insignia, the line of a
cap. And it removes the grain, because grain looks like noise to it. The grain
is the film. Taking it out and replacing it with smooth skin and clean cloth is
a decision about what the record should look like. It is not a repair.

**Which model.** Four 4× models were run on the same face and measured for how
much fine detail they add. Plain lanczos is the baseline because it adds none —
it only makes the existing pixels bigger. Measured on the frame as delivered, at
2136×1600:

| | detail added | over baseline |
|---|---|---|
| lanczos (baseline) | 2.27 | — |
| `4x_foolhardy_Remacri` | 2.34 | +3 % |
| `4xlsdirplus_v1` | 2.35 | +4 % |
| `4x-UltraSharp` | 2.51 | +11 % |
| `4x_NMKD-Siax_200k` | **3.19** | **+41 %** |

`stills/L3_models_close_00014.png` shows what the numbers mean. NMKD-Siax paints
speckled grain across a cap and a forehead that have none, and turns an eyebrow
into a thick dark bar. Remacri brings out the brow line and leaves the skin
alone. This is what `docs/UPSCALE.md` decided in writing; here it is on screen.

> The gap depends on how much of the enlargement you keep. An earlier version of
> this level shrank the result back to the original 1068×800, and there every
> model landed within about one percent of the untouched frame — the invention
> was still there, just too small to see. Keep the pixels and the choice becomes
> visible. Give them back and a bad upscaler leaves nothing anyone can point at.

**The part worth saying out loud in the seminar.** These faces are about twenty
pixels tall in the original. No model can recover a face that small — it can
only make one up. Everything above is a choice about how much invention to
accept, and the honest option is the one Comfy Cloud does not offer: **Remacri
is not on Cloud**, while `4x-UltraSharp` and `4x_NMKD-Siax` — the two
`docs/UPSCALE.md` rejects for archival faces — are.

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
suggestion.

The chroma still has to be conditioned, because the generation does not land
pixel-on-pixel with its source. The default is a **guided filter** that fits the
chroma to the *document's* own luminance, so colour breaks where the film says
an edge is rather than where the generation thought one was. The alternative,
`--method blur`, is a plain Gaussian that hides misregistration by smearing
everything; it is kept because the comparison teaches something.

Guided wins clearly where the generation stayed roughly registered. On frame 120
the plain blur left a pink cast over Keitel's face and over the document in his
hands; the guided version returns natural skin and white paper. **It does not fix
a colour that landed on the wrong object.** On frame 660 the model recomposed the
crowd, put red where men's backs are, and the guided filter renders that wrong
colour with crisper edges rather than removing it. Bleeding is fixable,
misplacement is not, and that is the method's honest limit — worth showing
rather than cropping around.

> There is no separate half-resolution "clip" graph. One existed and was deleted:
> it ran 536×400 at ten steps, and both settings were later shown not to
> colourise at all. A graph in the repository that silently produces a neutral
> frame is worse than no graph.

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
