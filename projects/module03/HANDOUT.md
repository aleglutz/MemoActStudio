# Module 03 — the two you build yourself

You will be shown four ways of working an archival film: quoting it, sounding
it, sharpening it, colouring it. Two of them you run yourself on Comfy Cloud
during the seminar. They are the first two, and that is not an accident — they
are the two that fit inside a shared cloud machine and a seminar hour.

The film is thirty seconds from the surrender at Karlshorst, 8 May 1945, held by
Museum Berlin-Karlshorst.

## Before you start

You need a Comfy Cloud account and nothing else. **Every model these two
exercises use is already hosted on Cloud** — nothing to download, no Hugging
Face account, no licence to accept.

The facilitator gives you one file, `module03_master_30s.mp4`. Upload it once,
through the Load Video node's upload button.

> **Your file will be renamed.** Cloud stores every upload under a long
> hexadecimal name — `module03_master_30s.mp4` becomes something like
> `a003f3b5….mp4`. **Always pick the file from the dropdown; never type a
> name.** Typing the name you uploaded fails with an error that blames the
> file. This is the likeliest way an exercise goes wrong.

---

# Exercise 1 — put a quote from the document onto the film

## The rule that comes first

The words you are about to put on screen are transcribed from the signed English
copy of the Act of Military Surrender. Not from the footage, not from memory,
not from a paraphrase. **The document is the ground truth.** A workflow decides
*when* a line appears; it never decides *what* it says.

That rule is why this workflow beats an automatic-subtitle button, and it is
worth holding onto before the later levels start inventing things.

## Three nodes

| # | Node (search this name) | Set |
|---|---|---|
| 1 | **Load Video (Upload)** | your uploaded file; `force_rate` 0, `select_every_nth` 1; `skip_first_frames` and `frame_load_cap` per the table below |
| 2 | **🔧 Draw Text** (`DrawText+`) | text per table; `size` 34, `color` white, `background_color` `#00000055`, `shadow_distance` 2, `shadow_blur` 2, `shadow_color` black, align **center** / **bottom**, `offset_y` −60. Wire node 1's IMAGE into **`img_composite`** |
| 3 | **Video Combine** | `frame_rate` 30, `format` `video/h264-mp4`, `pix_fmt` `yuv420p`, `crf` 18, `filename_prefix` as in the table |

Font: Cloud carries exactly one, `ShareTechMono-Regular.ttf`. It is a typewriter
face, which suits a 1945 document, but it is not a choice you get to make.

## Three runs

One caption is one run. Change three fields between runs and queue again.

| Run | `skip_first_frames` | `frame_load_cap` | Text | `filename_prefix` |
|---|---|---|---|---|
| 1 | 24 | 216 | This Act is drawn up in the English, / Russian and German languages. | `module03/L1/quote1` |
| 2 | 270 | 225 | The English and Russian / are the only authentic texts. | `module03/L1/quote2` |
| 3 | 540 | 225 | Signed at Berlin / on the 8th day of May, 1945 | `module03/L1/quote3` |

The `/` marks where the line breaks — type a real newline there, inside the text
box.

## What you get, and what you don't

Three clips of seven or eight seconds, each with one caption. **You do not get a
captioned film.** The stretches between the quotes are in none of them, and
joining the pieces back into thirty seconds is editing work that happens outside
ComfyUI.

That is the finding, not a mistake you made:

- **One Draw Text node holds one string over one frame range.** Three captions
  are three runs. Moving a caption half a second earlier means editing a number
  and rendering that range again.
- **`background_color` draws no real plate.** Nothing but a drop shadow stands
  between white text and the picture. On *this* film it never hurts: the strip
  where the caption sits stays dark for the whole thirty seconds — measured
  every half second, it never rises above 65 of 255. So your captions will look
  fine, and the limitation will still be there, waiting for footage with a
  bright lower third. **A defect your test material happens to hide is the
  expensive kind.**

In the screening you will see the same three quotes done properly — one file,
all the timing inside it, a real plate behind the text, one pass. Compare the
two. **The comparison is the lesson**: it is the argument for the tool the
September workshop builds.

## Try changing

- `offset_y` — where the caption sits.
- `background_color` — the last two characters are opacity. `#00000055` is
  faint; try `#000000CC`.
- The frame range — put a quote over a different moment and ask whether it still
  means the same thing. Usually it does not. That is the subject of the module.

**Cost:** no model runs here. Pennies.

---

# Exercise 2 — make sound for a film that has none

## The film is silent, not quiet

Its audio track measures −91 dB from beginning to end — every sample in one
histogram bin. There is nothing faint to rescue. **Everything you are about to
hear is manufactured.**

Keep that in view, because manufactured sound is the least-flagged fabrication
in museum practice. Nobody captions a room tone. A generated hall murmur is
received as atmosphere rather than as content, and it passes unchallenged in
places where an invented image would not.

## Eight nodes

| # | Node | Set |
|---|---|---|
| 1 | **Load Checkpoint** | `stable-audio-open-1.0.safetensors` |
| 2 | **Load CLIP** | `t5_base.safetensors`, type **`stable_audio`** |
| 3 | **CLIP Text Encode** (positive) | the layer's prompt, from the table |
| 4 | **CLIP Text Encode** (negative) | `music, melody, singing, instruments, rhythm, beat, speech, dialogue, narration` |
| 5 | **Empty Latent Audio** | `seconds` per table, `batch_size` 1 |
| 6 | **KSampler** | `steps` 50, `cfg` 4.98, sampler `dpmpp_3m_sde_gpu`, scheduler `exponential`, `denoise` 1.0, seed per table |
| 7 | **VAE Decode Audio** | VAE from node 1 |
| 8 | **Save Audio (Advanced)** | `format` `flac` |

> **The trap, and you will hit it.** Both text encode nodes take their CLIP from
> **node 2**, not from the checkpoint. The checkpoint carries the model and the
> VAE but **no text encoder**, so wiring CLIP from node 1 gives you `CLIP = None`
> and an error message that blames the checkpoint file. Load the text encoder
> separately.
>
> Also: the node called plain "Save Audio" is deprecated on Cloud. Use **Save
> Audio (Advanced)**.

## Four layers

Run the graph four times, changing three fields each time.

| Layer | Seconds | Seed | Prompt |
|---|---|---|---|
| bed | 32 | 550919 | Ambience of a crowded hall: many men murmuring quietly at a distance, low indistinct voices, occasional cough and chair creak, reverberant, no music. |
| paper | 14 | 220805 | A single sheet of stiff dry paper lifted from a wooden table, held, turned over, and set down again. Close, dry, detailed, in a quiet room. |
| cameras | 16 | 880431 | Sharp mechanical camera shutter clicks and clacks, film advance ratchet winding, a flashbulb pop, spaced out with silence between them, recorded in a large reverberant room. Dry transient clicks, no continuous tone. |
| steps | 12 | 440108 | A heavy wooden chair scraping back on a parquet floor, then several slow leather-soled footsteps on parquet in a large echoing room. Close and dry. |

**Cost does not grow with length.** Each layer takes about six seconds of GPU
whether you ask for twelve seconds of audio or thirty-two. Four layers is under
a minute of machine time — roughly three cents. This is the one level thirty
people can run at once.

## Judging takes ears

Two of those four prompts are second attempts, and the rewriting is the real
craft in this exercise.

- The first **bed** came back flat broadband hiss — the sound of a bad recording
  rather than of a room. The rewrite named what was in the room: *many men
  murmuring quietly at a distance… occasional cough and chair creak.*
- The first **cameras** came back a tonal hum where shutter clacks belonged. The
  rewrite named the shape of the sound in time, not only its source: *spaced out
  with silence between them… Dry transient clicks, no continuous tone.*

So when a layer is wrong, do not just change the seed. Ask what the model
misheard, and say the missing thing.

## What the graph cannot do

**Nothing in it places a sound at a timecode.** The model makes material; an
editor still decides when the shutter fires, how loud the room sits under it,
and whether the footsteps land on the man who is walking. In the version you
will hear, those decisions were made afterwards in an audio editor, and they are
why it sounds like a scene rather than four clips playing at once.

That division — the model makes material, a person makes the cut — is the honest
description of every level in this module.

---

# What you are shown but do not run

**Level 3, sharpening.** About an hour of GPU for thirty seconds of film, and
the upscaler chosen for archival faces is not available on Cloud. Two of the
ones that are available are the two rejected for painting invented grain onto
skin that has none.

**Level 4, colour.** Roughly two minutes of GPU **per frame**, and there is no
colouriser on Cloud at all. Thirty people running it would cost about a hundred
dollars for a couple of seconds of film each.

You get a single frame from each to handle, so the thing on screen is not only
on screen.

---

# For the facilitator

Prepare before the session:

- Upload `module03_master_30s.mp4` once yourself and see what the dropdown label
  looks like, so you can tell participants what to look for.
- Build both graphs once in the Cloud UI and save them. Importing
  `workflows/L1_quote_api.json` may work and may not: our local `DrawText+`
  carries a `direction` field that Cloud's build of the node does not have.
  Try the import first, by all means — but have the hand-built graph saved
  before the session rather than finding out in front of thirty people.
- Run one level-2 layer to confirm node availability, for the price of six GPU
  seconds. Never open a session with an untested graph.

Budget: level 2 is about three cents a head, so thirty participants is around a
dollar; level 1 runs no model. Anything beyond that is a screening, by design —
`CLOUD.md` is where each of these figures comes from.
