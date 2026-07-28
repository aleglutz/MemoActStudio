# HARDENING.md — deferred portability / offline items (P3, September)

Per SPEC.md §0: these never block an implementation decision now.

> **Rewritten 2026-07-28 (SPEC v3.1 §0).** This file assumed participants would run ComfyUI on their own machines. They will not. The curriculum has two parts:
>
> - **August online, 30 students → Comfy Cloud.** No local install at all, so participant install surface is not a project concern for Part 1.
> - **September offline, 16 students → local ComfyUI on TWO RENTED MACHINES.** Local install *is* a concern for Part 2 — but for two project-controlled machines, provisioned once and cloned, not for sixteen unknown personal ones.
>
> That distinction retires most of the original content. USB model distribution, museum-Wi-Fi download contention and a dependency audit against unknown hardware were all solving the sixteen-personal-machines problem, which no longer exists. What replaces them is an ordinary provisioning checklist.
>
> **Lead time warning:** the machines must be *specified and booked* before they can be provisioned. That is the earliest hard deadline in this file — see SPEC §10.

## Workshop provisioning — two rented machines (September, P3)

- [ ] **Specify the machines before booking.** Input: `GAPS.md` #2 — ~11.5 GiB RAM for a 240-frame shot, scaling with *source* image resolution, not output. Size RAM from the intended workshop project, then add headroom for the chunking ceiling being relaxed. Per SPEC §6.2.8 no GPU is required by construction; treat one as opportunistic, never as a rental requirement. Disk: ComfyUI + embedded Python + Whisper model + project media.
- [ ] **Provision once, clone.** Build machine A completely, verify a full reel render end to end, then image it onto machine B. Do not hand-install twice — divergence between the two machines is the failure mode that costs workshop time.
- [ ] **Rotation reality: ~8 students per machine.** Renders must not monopolise a machine. Measure a realistic workshop-sized render on the actual hardware and, if it is too slow to share, cut scope (shorter exercise project, fewer frames) rather than discovering it live. `GAPS.md` #3's ~2.6× text cost is the first thing to look at.
- [ ] **Shared-machine hygiene:** where project files live, how a student's work is kept separate from the next student's, and how the machine is reset between rotations.

## Aligner / models — facilitator, production, and the two rented machines

- [ ] `nodes_align.py` accepts an explicit local model path (no forced auto-download at runtime). *(Reproducibility, and it makes pre-seeding the rented machines trivial.)*
- [ ] Pre-seed the Whisper model into the machine image so no download happens during the workshop. This is the *useful* remnant of the old USB item — same goal, but solved once at provisioning instead of sixteen times on the day.
- [ ] Bake-off question, informational only: does Whisper `base` (~145 MB) suffice, or is `small` (~484 MB) needed? We measure timing accuracy, not transcription quality. Low stakes now — the model ships inside the machine image.
- [x] ~~Documented offline install: model directory copied from USB; 16 participants must not download simultaneously over museum Wi-Fi.~~ **Retired** — two provisioned machines, not sixteen personal ones. Superseded by the pre-seeding item above.
- [x] ~~Armenian narration alignment.~~ **Dropped** — Armenian left project scope entirely (v3.1).

## Environment parity

- [ ] Log of behavioural differences between local ComfyUI and Comfy Cloud (SPEC.md §0). **Now the most load-bearing section in this file**, since Cloud is the students' delivery target rather than just a validation surface. Recorded so far, both 2026-07-28, both in `GAPS.md`:
  - #4 Cloud `/api/upload/image` is content-addressed — uploaded filenames become SHA-256 digests, so graphs exported against bare filenames are not submittable unchanged.
  - #5 Cloud zeroes resource telemetry (`system_stats` → `ram_total: 0`, `devices: []`), so no memory measurement is possible there; only wall-clock from `/api/jobs/{prompt_id}`.

## Install surface

- [x] ~~Dependency audit for participant machines (unknown hardware, offline).~~ **Retired** — there is no unknown hardware. Replaced by the provisioning checklist above.
- [ ] Reproducible install procedure for the two rented machines: count and script the steps on a clean Windows box, documenting the ComfyUI-Easy-Install embedded-Python path (`CLAUDE.md`). This is what gets executed on machine A before imaging.
- [ ] Pin what is currently hand-added and unrecorded anywhere: `ComfyUI_essentials` (cloned into `custom_nodes`, heavy requirements deliberately not installed), `stable-ts`, `num2words`. Today these exist only on the dev machine by hand — they must be in a written install procedure before September, or the rented machines will not match the environment everything was verified against.
- [ ] **Ship the subtitle font inside the pack** (`assets/fonts/`). Burn-in currently resolves Share Tech Mono out of `ComfyUI_essentials/fonts/` — a hand-cloned pack that P2 otherwise does not need, and a silent dependency that would produce differently-styled captions (or a fallback font) on a machine without it. `render.encode(fontsdir=...)` already takes the directory, so this is a packaging step, not a code change. Check the font licence into `SURVEY.md` per SPEC §2.5 while doing it.
- [ ] Confirm ffmpeg on the rented machines is built `--enable-libass`. The dev machine's is; a build without it fails the subtitle filter at render time, not at install time, which is the worst moment to find out.
