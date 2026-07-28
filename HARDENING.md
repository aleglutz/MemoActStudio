# HARDENING.md — deferred portability / offline items (P3, September)

Per SPEC.md §0: these never block an implementation decision now.

> **Heavily reduced 2026-07-28 (SPEC v3.1 §3).** Most of this file existed because participants were assumed to run ComfyUI on their own machines. They do not — **online students run on Comfy Cloud**, precisely to avoid depending on personal hardware. Participant install surface, USB model distribution and museum-Wi-Fi contention are therefore no longer project concerns. What remains applies to the *facilitator's* and the *production* machine only.
>
> This does **not** cover the September in-person offline workshop, if one still happens on local machines — that is a different delivery with different constraints, and the struck items below should be revived wholesale if it is confirmed. Flagged as an open question in SPEC §10.

## Aligner / models — facilitator + production machine only

- [ ] `nodes_align.py` accepts an explicit local model path (no forced auto-download at runtime). *(Still wanted: reproducibility, not portability.)*
- [ ] Bake-off question, informational only: does Whisper `base` (~145 MB) suffice, or is `small` (~484 MB) needed? We measure timing accuracy, not transcription quality. Lower stakes now — one machine, not sixteen.
- [x] ~~Documented offline install: model directory copied from USB; 16 participants must not download simultaneously over museum Wi-Fi.~~ **Dropped** — students are on Cloud and never install the aligner.
- [x] ~~Armenian narration alignment.~~ **Dropped** — Armenian left project scope entirely (v3.1).

## Environment parity

- [ ] Log of behavioural differences between local ComfyUI and Comfy Cloud (SPEC.md §0). **Now the most load-bearing section in this file**, since Cloud is the students' delivery target rather than just a validation surface. Recorded so far, both 2026-07-28, both in `GAPS.md`:
  - #4 Cloud `/api/upload/image` is content-addressed — uploaded filenames become SHA-256 digests, so graphs exported against bare filenames are not submittable unchanged.
  - #5 Cloud zeroes resource telemetry (`system_stats` → `ram_total: 0`, `devices: []`), so no memory measurement is possible there; only wall-clock from `/api/jobs/{prompt_id}`.

## Install surface

- [x] ~~Dependency audit for participant machines (unknown hardware, offline).~~ **Dropped for students** (Cloud). Retained only as a facilitator-machine concern; the ComfyUI-Easy-Install embedded-Python path is documented in `CLAUDE.md`.
