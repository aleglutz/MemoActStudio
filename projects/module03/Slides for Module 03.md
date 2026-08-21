# Slides — Module 03

Two hours, strictly. The run sheet below is the contract; every slide carries
its minute budget.

**No hands-on building in this module.** Both exercises go home in `HANDOUT.md`,
and the time they would have taken goes into arguing about the four levels
instead — which is the part a room is actually needed for. Every level block
therefore ends with a discussion slide, and those slides carry real questions,
not rhetorical ones: each has at least two defensible answers.

| Time | Block | Slides | Min |
|---|---|---|---|
| 0:00 | Title, where we are, schedule | S1–S3 | 5 |
| 0:05 | **Screening: the reel** | S4 | 8 |
| 0:13 | **Visual identity + moodboard — designer** | S5 | 27 |
| 0:40 | The ladder, and the film itself | S6–S7 | 9 |
| 0:49 | Level 1 — quotes, **+ discussion** | S8–S10 | 13 |
| 1:02 | Break | — | 5 |
| 1:07 | Level 2 — sound, **+ discussion** | S11–S15 | 16 |
| 1:23 | Level 3 — sharpening, **+ discussion** | S16–S18 | 14 |
| 1:37 | Level 4 — colour, **+ discussion** | S19–S21 | 17 |
| 1:54 | Where would you have stopped | S22 | 4 |
| 1:58 | Homework | S23 | 2 |

Files to have open: `projects/legends_of_surrender/out/reel_with_hook.mp4`,
then `out/L1_quotes.mp4`, `out/L2_sound.mp4`, `out/L3_ab_zoom_30s.mp4`,
`out/L3_split_30s.mp4`, `stills/L3_models_close_00014.png`, `out/L4_ab.mp4`,
`stills/L4_ab_00300.png`, `stills/L4_ab_00660.png`.

> **Numbering note.** S1–S3 are unchanged. The screening is a new S4, and the
> homework slide that was S4 moves to the end as S23, where it belongs in a
> two-hour session. Everything from S6 on keeps the number it already had.

---

## S1 Module 03: Ethics and Techniques of Intervening in Archival Footage + Creating a Moodboard

## S2 The course structure

Educational modules come from the real short-video creation steps most creators
go through. Let's call it the

### Creator's Workflow

1. Idea and the topic
2. Research to collect and verify materials (facts and visuals)
3. **Decide how to present the document** — You Are Here.
4. Write a screenplay and record the voiceover
5. Assemble the visuals with tools that fit you
6. Polish the result: subtitles, visual effects and sound design
7. Pre-publishing screening and evaluation

## S3 Course Schedule

**14.08** – 01 Introduction and Finding the Focus
**18.08** – 02 Research Phase — AI-powered or AI-distorted
**21.08 – 03 Ethics and Techniques of Intervening in Archival Footage + Creating a Moodboard** – Today
**25.08** – 04 Editing as a Way of Thinking Through a Fragmented Reality. Making a script workshop
**27.08** – 05 Tools Implementation: Choose What Works For You or Build Your Own
**02.09** – 06 Production Process: Visual Effects and Sound Design
**07.09** – 07 Final Screening and Wrap Up Discussion

*(5 min for S1–S3.)*

---

## S4 Screening — what the end of the workflow looks like

**Play `projects/legends_of_surrender/out/reel_with_hook.mp4`** — 2:49, 1080×1920,
twenty shots, cut to a recorded narration. *Signed After Midnight*, made for
Museum Berlin-Karlshorst.

Three things to name **after** it plays, not before:

- **Every subtitle in it is verbatim from the script.** Not one line was
  transcribed off the audio by a machine. That is the same rule you will meet
  again in an hour, at level 1.
- **At 1:01 it uses the archival film we are about to take apart** — the German
  delegation arriving at Tempelhof, from the same Karlshorst reel.
- **And it refuses to enlarge it.** Cropping that shot to vertical would need a
  2.4× blow-up, so it sits full width with bands above and below instead. The
  edit note in `shots.csv` says exactly that. **A decision from today's session
  is already visible in the finished thing** — and the honest option was the one
  that looks less impressive.

> **Say:** You are looking at step 5 and 6 of the workflow. We are at step 3.
> The reason to show you the end first is so that today's arguments are not
> abstract: every one of them left a mark on that file.

---

## S5 Visual identity and the moodboard — 27 min, designer

The idea behind the project's visual identity, and how it connects to the
students' own films. Slides supplied separately.

> **Hand-over cue:** you have just seen one project's answer to "how should this
> look". Now the reasoning behind it — and how you build the same thing for your
> own subject.
>
> **Hand-back cue:** a moodboard decides *how* the document will look on screen.
> The rest of the session is about *how far you are allowed to change it* to get
> there.

---

## S6 Four levels of intervention

Each level changes the record more than the one above it. That order is the
argument of the whole session.

| Level | What it adds | Stack | Runs on |
|---|---|---|---|
| **1. Quotes** | Nothing to the image; words from a document | `VHS_LoadVideo → DrawText+ → VHS_VideoCombine` | CPU |
| **2. Sound** | A soundtrack that never existed | `CheckpointLoaderSimple` + `CLIPLoader` → `KSampler` → `VAEDecodeAudio` → mix outside | 6 s GPU per layer |
| **3. Upscale** | Twice the pixels, and texture no camera recorded | `UpscaleModelLoader → ImageUpscaleWithModel → ImageScaleBy` | ~55 min GPU / 30 s |
| **4. Colour** | Colour — and, unguarded, the whole image | Qwen-Image-Edit (Apache-2.0) + our own LAB recombination | ~2 min GPU **per frame** |

> **Two corrections to the draft stack, both worth a sentence on the day.**
> Level 2 can be run through Cloud's `stable_audio_3_medium` subgraph, but what
> we tested and what the handout describes is **Stable Audio Open 1.0** — open
> weights, trained largely on the CC0 Freesound library, which is why it is a
> sound-effects model and not a music model. Level 4's **Lightning-8-steps
> LoRA** is untested by us: we measured that 6 and 10 steps *without* it do not
> converge and go green, so the LoRA may well be the thing that makes this level
> affordable. Say it as an open question, not as a result.

## S7 The film, and three facts that decide everything

Museum Berlin-Karlshorst, 7:36. Our cut: **04:14–04:44**, the signing.

1. **It is pillarboxed.** The transfer is 1280×800; the picture inside is
   1068×800. Work from the padded frame and you carry black bars all the way to
   the output.
2. **It is silent — not quiet.** The audio track measures **−91 dB mean *and*
   max**, every sample in one histogram bin. There is nothing to preserve.
3. **It already carries the museum's own burned-in captions** elsewhere in the
   reel. Our captions would argue with them. This stretch is clean, which is
   part of why it was chosen.

> **Say:** Notice that fact 1 is a decision someone already made, and so is the
> warm tint you will see in a moment — "black and white" is not a neutral
> state, it is a scanning choice. You are never intervening in raw material.
> You are intervening in someone else's intervention.

*(9 min for S6–S7.)*

---

## S8 Level 1 — the rule that comes before the tool

The three quotes you are about to see are transcribed from the **signed English
copy of the Act of Military Surrender**. Not from the footage. Not from memory.
Not from a paraphrase.

> **The document is the ground truth. A workflow decides *when* a line appears.
> It never decides *what* it says.**

> **Say:** This is the one rule that separates this workflow from the
> auto-subtitle button in any editor. An automatic transcript reads the film and
> guesses. We read the document and time it. If you take one thing from today
> into your own project, take this.

## S9 Level 1 — screening, and what the stock node cannot do

**Screen `out/L1_quotes.mp4`** — then show the same three quotes built from the
graph.

Two limits, and both are the argument for building your own tool later:

- **One `DrawText+` node holds one string over one frame range.** Three captions
  are three separate runs. Moving a caption half a second earlier means editing
  a number and rendering that range again.
- **`background_color` draws no real plate** — only a drop shadow stands between
  white text and the picture.

> **Say — and this is the good part.** On *this* film the second limit never
> shows. We measured the strip where the caption sits, every half second across
> the whole cut: it runs 14 to 65 out of 255. Dark everywhere. So the captions
> look fine, the defect is real, and your test footage is hiding it. **A flaw
> your material happens to conceal is the expensive kind** — it surfaces on the
> next film, in front of an audience.

## S10 Level 1 — discussion

**Three questions. None of them has one answer.**

1. **A caption is a verbatim quote from a real document. Does putting it over a
   different moment of the film make it a lie?** Nothing in the words changed.
   Where exactly does timing stop being editing and start being a claim?
2. **This reel already carries the museum's own burned-in captions.** If yours
   contradicts theirs on the same frame, whose survives — and who gets to
   decide?
3. **Does a quote belong on screen if you cannot also show where it came from?**
   The reel has room for a source line. A thirty-second vertical video does not.

> **Say:** Level 1 adds nothing to the image, and it is still the level where
> you can mislead most cheaply. Every later level is more visible and therefore
> easier to challenge.

**Take home:** `HANDOUT.md`, Exercise 1 — three nodes, three runs, twenty
minutes, no GPU. What you will find is three clips of eight seconds, **not a
captioned film**: the stretches between quotes are in none of them, and joining
them is editing work outside ComfyUI. That gap is the subject of module 05.

*(13 min for S8–S10. Then 5 min break.)*

---

## S11 Level 2 — the film is silent, so everything you hear is invented

−91 dB, end to end. Nothing to rescue, nothing to duck under.

> **Say:** Sound is the cheapest level and the least-challenged fabrication in
> the whole museum practice. **Nobody captions a room tone.** A generated hall
> murmur is received as atmosphere rather than as content, and it passes
> unchallenged in places where an invented image would be caught immediately.
> That asymmetry is worth more discussion than the technique.

**Screen `out/L2_sound.mp4`.** Ask before explaining anything: *did that sound
like a recording?* Then say that not one sample of it existed an hour ago.

---

## S12 Level 2 — how it is made, in eight nodes

Everything is already on Cloud: no downloads, no Hugging Face account, no
licence to accept. This is the graph you get in the handout — read it here,
build it at home.

| # | Node | Set |
|---|---|---|
| 1 | **Load Checkpoint** | `stable-audio-open-1.0.safetensors` |
| 2 | **Load CLIP** | `t5_base.safetensors`, type **`stable_audio`** |
| 3 | **CLIP Text Encode** (positive) | the layer's prompt |
| 4 | **CLIP Text Encode** (negative) | `music, melody, singing, instruments, rhythm, beat, speech, dialogue, narration` |
| 5 | **Empty Latent Audio** | `seconds` per layer, `batch_size` 1 |
| 6 | **KSampler** | steps 50, cfg 4.98, `dpmpp_3m_sde_gpu`, `exponential`, denoise 1.0 |
| 7 | **VAE Decode Audio** | VAE from node 1 |
| 8 | **Save Audio (Advanced)** | `format` `flac` |

> **The trap, and you will hit it when you build this at home.** Both text
> encoders take CLIP from **node 2**, not from the checkpoint. The checkpoint has the model and the VAE but
> **no text encoder** — wire CLIP from node 1 and you get `CLIP = None` and an
> error that blames the checkpoint file.
>
> Also: plain "Save Audio" is deprecated on Cloud. Use **Save Audio (Advanced)**.

## S13 Level 2 — four layers, and what they cost

| Layer | Sec | Seed | Prompt |
|---|---|---|---|
| bed | 32 | 550919 | Ambience of a crowded hall: many men murmuring quietly at a distance, low indistinct voices, occasional cough and chair creak, reverberant, no music. |
| paper | 14 | 220805 | A single sheet of stiff dry paper lifted from a wooden table, held, turned over, and set down again. Close, dry, detailed, in a quiet room. |
| cameras | 16 | 880431 | Sharp mechanical camera shutter clicks and clacks, film advance ratchet winding, a flashbulb pop, spaced out with silence between them, recorded in a large reverberant room. Dry transient clicks, no continuous tone. |
| steps | 12 | 440108 | A heavy wooden chair scraping back on a parquet floor, then several slow leather-soled footsteps on parquet in a large echoing room. Close and dry. |

**Cost does not grow with length.** Six seconds of GPU per layer whether you ask
for twelve seconds of audio or thirty-two. Four layers ≈ **three cents**. This
is the one level thirty people could run at once — which is why it is the one
to try first when you get home.

## S14 Level 2 — judging takes ears

Two of those four prompts are **second attempts**, and the rewriting is the real
skill here.

- The first **bed** came back flat broadband hiss — the sound of a bad recording
  rather than of a room. The rewrite named what was *in* the room: *many men
  murmuring quietly at a distance… occasional cough and chair creak.*
- The first **cameras** came back a tonal hum where shutter clacks belonged. The
  rewrite named the **shape of the sound in time**, not just its source: *spaced
  out with silence between them… Dry transient clicks, no continuous tone.*

> **Say:** When a layer is wrong, do not just roll the seed. Ask what the model
> misheard, and say the missing thing. Both fixes here were words, not numbers.

## S15 Level 2 — what the graph cannot do, and discussion

**Nothing in it places a sound at a timecode.** The model makes material; a
person still decides when the shutter fires, how loud the room sits under it,
and whether the footsteps land on the man who is walking.

In the version you heard, those decisions were made afterwards in an audio
editor — and they are why it sounds like a scene instead of four clips playing
at once.

> **The model makes material. A person makes the cut.** That is the honest
> description of every level in this module, and the answer to "will this
> replace an editor".

**Discussion — three questions:**

1. **Nobody captions a room tone. Should they?** What would an honest sound
   credit even look like on a thirty-second video — and would anyone read it?
2. **The narration in the reel you saw is a real recorded human voice.** If it
   were synthetic, would you disclose that? Does your answer change for the
   crowd murmur? If it does, what is the difference you are actually pointing at?
3. **Stable Audio Open is trained largely on Freesound's CC0 library** — sounds
   people recorded and gave away. So whose coughs are in that 1945 hall? Does it
   matter that they are real recordings of real rooms, just not *that* room?

*(16 min for S11–S15. Cut the eight-node table first if the room is slow — it is
in the handout anyway.)*

---

## S16 Level 3 — what an upscaler actually does

Two things happen, and only one is the one people expect.

1. **Edges get sharper** — buttons, braid, the line of a cap.
2. **The grain disappears**, because to the model grain looks like noise.

> **The grain is the film.** Replacing it with smooth cloth and clean skin is a
> decision about how the record should look. It is not a repair.

**Screen `out/L3_ab_zoom_30s.mp4`** — same patch of the signing table, plain
enlargement left, restored right. Then `out/L3_split_30s.mp4` if there is time.

## S17 Level 3 — which model decides how much gets invented

Five models on the same face, measured for fine detail added. Plain lanczos is
the baseline because it invents nothing — it only makes existing pixels bigger.

| | detail | over baseline |
|---|---|---|
| lanczos (baseline) | 2.27 | — |
| `4x_foolhardy_Remacri` | 2.34 | +3 % |
| `4xlsdirplus_v1` | 2.35 | +4 % |
| `4x-UltraSharp` | 2.51 | +11 % |
| `4x_NMKD-Siax_200k` | **3.19** | **+41 %** |

**Show `stills/L3_models_close_00014.png`.** NMKD-Siax paints speckled grain
across a cap and a forehead that have none, and turns an eyebrow into a thick
dark bar. Remacri brings out the brow line and leaves the skin alone.

## S18 Level 3 — the part worth saying out loud

**These faces are about twenty pixels tall in the original.** No model can
recover a face that small. It can only make one up. Everything on the previous
slide is a choice about how much invention to accept.

And then the awkward part: **Remacri is not available on Comfy Cloud.**
`4x-UltraSharp` and `4x_NMKD-Siax` — the two we just rejected — are.

> **Say:** The platform's default is not the careful choice. It rarely is. If
> you cannot name why you picked a model, you did not pick it.

**Discussion — three questions:**

1. **The grain is the film. Is removing it restoration, or retouching?** The
   same operation is called both, depending on who is selling it.
2. **Your platform offers you two upscalers, and both invent grain on skin that
   has none. You cannot install the careful one.** Do you use what is there, or
   do you not upscale at all? Answer as if the deadline is tomorrow.
3. **Jackson's argument is legibility**: at native size and speed, nobody
   watches, so nobody learns anything. Is that worth the invention? Notice that
   the reel you saw this morning answered *no* — and lost half its frame to
   bands for it.

*(14 min for S16–S18.)*

---

## S19 Level 4 — asked to colourise, the model redrew

**Show `stills/L4_ab_00300.png`.** Frame 300 came back as a different man: a new
face, re-invented medals, no film grain, the room re-lit — a plausible modern
photograph standing where a document had been.

And there is **no setting in between**. At lower denoise the archival frame
survives intact and almost no colour arrives; the instruction barely applies.
Colour needs full denoise, and full denoise is what makes it redraw.

## S20 Level 4 — so we demote the model

Keep the archival frame's **luminance** untouched. Take **only the colour** from
the generation. No edge, no face and no grain can move, because the shapes come
from the film, not from the model.

**Screen `out/L4_ab.mp4`** — three panels: the film, the redraw, the restrained
version. Then `stills/L4_ab_00660.png`, where the model put red on men's backs
and the method faithfully preserves the wrong colour with crisp edges.

> **Say:** This does not fix a colour that landed on the wrong object. Bleeding
> is fixable; misplacement is not. Showing the failure is the point — cropping
> around it would be the dishonest edit.

## S21 Level 4 — the flicker, and where it is worst

Nothing enforces consistency between frames, so each frame picks its own
palette. Measured across twenty consecutive frames against the film's own
frame-to-frame noise as the floor:

| | flicker vs the film's own noise |
|---|---|
| tunic | 4× |
| face | 4.6× |
| **blank plaster wall** | **17.6×** |

> **Say:** The model is least stable exactly where it is most free. Where there
> is nothing to colour, there is nothing to anchor the invention. That is not a
> bug to apologise for — it is the argument, visible and measurable.

**Discussion — three questions:**

1. **The model returned a plausible modern photograph where a document had been,
   and reported success.** Nothing failed. What in *your* process would have
   caught it? Be concrete: name the step.
2. **Our fix keeps the film's own luminance, so no shape can move.** Does that
   make the colour honest — or does it only make the invention harder to see?
   The colours on frame 660 are still wrong; they are just wrong with crisp
   edges now.
3. **The blank wall flickers 17.6× the film's own noise.** Is that instability a
   defect to fix — or the only visible sign the viewer gets that this is
   generated? Would you smooth it if you could?

*(17 min for S19–S21. This is the block with the most room; let it run.)*

---

## S22 Where would you have stopped?

Four levels, one film, rising intervention:

1. Added nothing to the image; took its words from a document.
2. Manufactured something the film never carried — and nobody will question it.
3. Invented texture inside the image, and removed the grain that was evidence.
4. Invented the image.

**No tool anywhere in today's session told you that a line had been crossed.**
Every one of them reported success.

**Round the room, one sentence each: which level is the last one you would
have used on your own subject — and what would you have to write down for the
next person to trust it?**

*(4 min.)*

---

## S23 Homework — two films that made opposite choices

**They Shall Not Grow Old** — recommended in full; required excerpt **22:18–32:52**
**Babi Yar. Context** — recommended in full; required excerpt **52:46–1:08:36**

> **Say:** These are not two examples of the same thing. Jackson takes the
> footage as far as it can go — he slows it to a natural speed, sharpens it,
> colours it, and hires lip-readers so the men can speak. Loznitsa cleans the
> image and builds an entire soundtrack for silent material, and then stops: no
> colour, no voice, no narrator telling you what you are seeing.
>
> Both are defensible. Both are choices. **You have just made the same four
> choices yourselves.** Come to module 04 able to say, for each film, which of
> the four levels its makers used and which they refused — and whether you
> agree.

**Exercise 1 is yours to run** — `HANDOUT.md`, twenty minutes, no GPU.

*(2 min.)*
