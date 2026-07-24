# HARDENING.md — deferred portability / offline items (P3, September)

Per SPEC.md §0: these never block an implementation decision now. They are the checklist for the September offline workshop and general portability.

## Aligner / models

- [ ] `nodes_align.py` accepts an explicit local model path (no forced auto-download at runtime).
- [ ] Documented offline install: model directory copied from USB; 16 participants must not download the model simultaneously over museum Wi-Fi.
- [ ] Bake-off question, informational only: does Whisper `base` (~145 MB) suffice, or is `small` (~484 MB) needed? We measure timing accuracy, not transcription quality, so the smaller model may well be enough — but do not compromise PoC accuracy to find out.
- [ ] Armenian narration alignment — only relevant if a participant narrates in HY for their own project. Candidate path: MMS-class aligner (see ALIGNERS.md §3; note CC-BY-NC weights).

## Environment parity

- [ ] Log of behavioural differences between local ComfyUI and Comfy Cloud observed while iterating locally / validating on Cloud (SPEC.md §0). *(none recorded yet)*

## Install surface

- [ ] Dependency audit for participant machines (unknown hardware, offline): count install steps on a clean Windows venv; document the ComfyUI-Easy-Install embedded-Python path.
