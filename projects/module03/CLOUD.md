# Module 03 on Comfy Cloud — what is there and what it costs

Survey of 2026-08-20. **Nothing was run and no credits were spent.** Every
timing below is measured locally on a 3090 Ti; the Cloud figures are arithmetic
on top of those. Where a number would have to be measured on Cloud, it says so.

## The short answer

All four levels have their nodes and their models on Cloud. Three things change:
the upscaler we chose is not there, there is no colouriser at all, and the
caption font is whatever Cloud ships.

## The machine and the price

Cloud runs on an **RTX Pro 6000, 96 GB**. Local is a 3090 Ti, 24 GB. The memory
ceiling that forced eight frames at a time locally is far away there.

Billing counts **GPU seconds**, not the time a browser tab is open. July's
invoice was **$2.19 for 1 694.5 GPU-seconds** — that is **$4.66 an hour, about
0.13 cents a second**.

| Level | Work | GPU time at local speed | Cost |
|---|---|---|---|
| 1 — quotes | 901 frames, no model | minutes | pennies |
| 2 — sound | 6 s per layer | 24 s for four layers | **~3 ¢ per student** |
| 3 — restoration | 901 frames × 3.6 s | ~54 min | ~$4.20 (10 s clip: ~$1.40) |
| 4 — colourisation | ~130 s per frame | 20 frames ≈ 43 min | ~$3.40 (~17 ¢ a frame) |

The Cloud card is faster than ours, so treat these as ceilings.

## A claim of ours that the evidence contradicts

`docs/PARTICIPANT_GRAPH_RECIPE.md` warns that Cloud kills any job running past
roughly 21–44 seconds, and sizes the participant chunks around that. The billing
feed does not support it as a rule: on 5 July, jobs consumed **165, 254 and 359
GPU-seconds**. A job killed at 44 seconds cannot bill six minutes of GPU.

Both observations are real — the failures on 28 July happened. The likely
reading is instability or contention rather than a time limit, which is what the
warning itself half-says. It matters, because if there is no hard limit then
level 3 is not barred from Cloud at all.

**This is a hypothesis, not a correction.** One deliberate long job settles it
and costs about fifty cents. Until it is run, keep the chunking.

## Level 1 — quotes

- `VHS_LoadVideo`, `VHS_VideoCombine`, `DrawText+` — all present.
- **`DrawText+` on Cloud has one font: `ShareTechMono-Regular.ttf`.** Locally we
  chose Courier New. Both are typewriter faces, so the look survives, but on
  Cloud it is not a choice, and a student cannot bring a font.
- **There is no subtitle node on Cloud of any kind** — nothing reads `.ass` or
  `.srt`, nothing burns a caption track. The production path stays outside
  ComfyUI, exactly as it does locally.

So on Cloud a student can build the poor half of the comparison, and only that
half. The good half is shown, not built. That is not a shortcoming to hide: the
level exists to demonstrate the gap.

## Level 2 — sound

- `stable-audio-open-1.0.safetensors` — present.
- `t5_base.safetensors` — **present as a Cloud model.**

That second line is the important one. Locally, the text encoder had to come from
a licence-gated Hugging Face repository: an account, an accepted licence, a
token, per student. On Cloud that obstacle is gone. **Level 2 is now genuinely
handable to thirty people at once**, at about three cents each.

Two notes for the port:

- `SaveAudio` is deprecated on Cloud. Use **`SaveAudioAdvanced`**, which takes a
  `format` (flac / mp3 / opus).
- Cloud also carries **`stable_audio_3_small_sfx`**, a newer model built for
  sound effects rather than music. We have not tested it and have not read its
  licence. Worth one look before September; not before the seminar.

## Level 3 — restoration

Nodes are all present. Models are the problem, and it is the one we predicted.

**Twelve upscalers, and Remacri is not among them.** Neither is `4xlsdirplus`.
Two of the twelve are `4x-UltraSharp` and `4x_NMKD-Siax` — the two that
`docs/UPSCALE.md` rejects for archival faces, because they paint grain onto skin
that has none.

One option exists that we have never tried: **`RealESRGAN_x2plus`, a native 2×
model.** Our delivery is 2×. Locally we reach it by running a 4× model and
shrinking. A native 2× would drop that step. Whether it treats a
twenty-pixel-tall face better or worse than Remacri-then-lanczos is unmeasured —
and it can be measured locally, for nothing, since the model is downloadable.

## Level 4 — colourisation

The whole chain is on Cloud: `qwen_image_edit_bf16` (also 2509 and 2511),
`qwen_2.5_vl_7b`, `qwen_image_vae`, `TextEncodeQwenImageEdit`.

**There is still no colouriser.** No DDColor, no DeOldify. Searching returns
ControlNet *Recolor* preprocessors, which are a different thing.

That does not block the level, because our method never used one. The step that
keeps the archival frame's luminance and takes only the model's colour is our own
script, and it runs after ComfyUI on any machine. What Cloud gives a student is
the redraw — the warning half of the level.

## What actually blocks a handoff

Not the GPU, and possibly not the clock either.

- **Our node pack cannot be installed on Cloud.** Unchanged, and the reason P1
  used stock nodes.
- **Uploads are renamed.** Every uploaded file is stored under a long
  hexadecimal name, so a graph must reference the hashed name, not the one the
  student uploaded. Always pick the file from the dropdown. This is the single
  likeliest way a participant's run goes wrong.
- **Credits are per workspace.** Thirty students on level 2 is about a dollar.
  Thirty students on level 4 would be a hundred, which is why level 4 is a
  screening with one frame handed over.
