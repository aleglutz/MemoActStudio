# P1 graph — Cloud PoC from stock nodes

Status: **approved 2026-07-24** (Option 1, verification order, EN subtitle track, generator as `memoacts_core` seed) **with three amendments applied below:** memory-aware chain (no whole-reel batches), HY+RU font testing, frozen generator contract. Per SPEC §0/§6.1. Companion to SURVEY.md §2 (coverage verdicts).

**Memory rule (governs the whole graph):** IMAGE tensors are float32 `[B,H,W,3]` — one 1080×1920 frame ≈ 25 MB, 240 frames ≈ 6 GB, the full 4500-frame reel ≈ 112 GB. Never materialise more than one shot (chunked to ~60 frames if needed) as a batch; never build one batch for the whole reel.

## Inputs (prepared outside the graph, SPEC §4)

Facilitator-side script (the seed of `memoacts_core`, run locally, one command):

```
narration.mp3 + script.md
  → normalise text (digits→spoken form, RU-inflected; SPEC §5.1)
  → stable-ts align()
  → shots.json                       # {shot_id, text, t_start, t_end, n_frames}
  → per-shot crop schedules (CSV)    # motion preset + image resolution → x;y;w;h per frame,
                                     #   eased, shot_lead_ms applied, resolution guard enforced
```

Uploaded to Cloud as input assets: images, `narration.mp3`, and the crop CSVs (pasted or as files). Everything the graph can't compute is precomputed — the graph only executes.

Note: motion math (easing, anchors, guard) lives in the *generator script* from day one — this is P2's `memoacts_core` motion engine being written early in its simplest form, not throwaway code.

**Generator output is a contract.** `shots.json` + crop CSVs are handed to participants as prepared inputs, so the schema is **frozen and versioned** (`schema_version` field; documented in `docs/SHOTS_SCHEMA.md`). Every run also emits a human-readable per-shot report: duration, image file, max achievable zoom for that image, clamp applied y/n.

## Graph structure — Option 1 (recommended): shot subgraph × N

One **"MemoActs Shot (stock)"** subgraph (core ComfyUI subgraph feature), duplicated per shot:

```
LoadImage (still, source resolution)
  → ImageCrop+           ← x,y,w,h as per-frame INT lists (crop CSV → split (to LIST)
                            → to INT [basic_data_handling]); list-mapping broadcasts the
                            single image across the param list — NO RepeatImageBatch
  → ImageResize+         (→ 1080×1920, still in list domain — resize BEFORE batching,
                            never after: batch only ever holds 1080p frames)
  → DrawText+            (subtitle text, STILL IN LIST DOMAIN — with a batched
                            img_composite it collapses to one frame, GAPS.md #3;
                            safe-zone y-margin)
  → ImageListToBatch+    (essentials — collect; ≤ 60 frames per chunk)
  → VHS_VideoCombine     (frame_rate=30, crf≈19, yuv420p, h264/mp4, no audio)
  → shot_NN.mp4          (per-shot video segment)
```

Top level: **no in-graph concat.** Each shot subgraph emits its own segment; assembly happens outside:

```
[outside the graph]  ffmpeg concat demuxer (-c copy, no re-encode) over shot_01…NN.mp4
                     → mux narration.mp3 in the same pass → reel.mp4
```

This keeps peak memory at one shot's 1080p batch (~1.5–6 GB) instead of the reel's ~112 GB, and the segment concat is lossless. The concat/mux step joins the facilitator-side tooling next to the schedule generator.

- **Participant exercise: ~5 shots** (subgraphs make each shot one readable block; swap an image = open subgraph, change one LoadImage). Full 18-shot Sidur graph is the facilitator's validation run.
- Subtitle track: **EN** by default (font/Cyrillic risk, SURVEY §2.4); RU if `DrawText+` renders Cyrillic on Cloud.
- Canvas 1080×1920 directly in P1 (no 4K supersampling — credit cost; quality is a P2 concern).
- P1 §6.1.3 satisfied: motion = zoom/pan from crop schedules; subtitles = DrawText+.

## Option 2 (experiment only): fully data-driven single chain

One global per-frame table (frame → image index + crop rect) driving a single pipeline via list ops — no per-shot duplication. Elegant, but stacks list-semantics assumptions (image-list indexing via `get item`, per-frame text switching) and is opaque to participants. Try only after Option 1 works; not on the critical path.

## Verification order (iterate locally, validate on Cloud — SPEC §0)

1. **Local, day 1 — the crux (SURVEY §2.3):** does a LIST of ints map-execute `ImageCrop+` with a single broadcast image, and does `ImageListToBatch+` collect it? **Run at 240 frames, not 3** — the 3-node version proves the mechanism, not the memory profile. Record peak RAM alongside pass/fail.
   **✅ PASSED 2026-07-24 (local, ComfyUI 0.27.0):** 240-frame eased zoom-in from a 3000×4000 still → 1080×1920\@30fps h264 in 48 s wall. `StringSplitDataList → CastToInt` data lists drive `ImageCrop+`; single image broadcasts; `ImageListToBatch+` collects; `VHS_VideoCombine` encodes. Motion visually verified (frame 0 ≈ full window, frame 239 ≈ 60 %, centered). **Memory: +11.5 GiB server RSS for the one shot** — source-resolution crop intermediates dominate, exactly why the ~60-frame chunk rule exists; on Cloud (unknown RAM) chunking is mandatory, and per-shot RAM scales with *source* image size, not output size.
2. Local: single-shot subgraph end-to-end (image → moving, subtitled ~8-s segment; narration muxed by the external concat step). **Font test here: `DrawText+` with Cyrillic AND Armenian** — HY is a mandated course language and the harder case; if the Cloud font stack can't render it, Cloud-side burn-in is dead for a mandated language → that goes in `GAPS.md` immediately, not in P2.
   **✅/⚠ DONE 2026-07-24:** EN renders; **RU and HY are tofu** (single Latin-only bundled font) → `GAPS.md` #1; P1 subtitle track = EN, RU/HY via pre-rendered PNG strips. Second finding: batched `img_composite` collapses to one frame → DrawText+ moved into list domain (`GAPS.md` #3).
3. Local: full multi-shot chain + external assembly, sync check.
   **✅ DONE 2026-07-24** on `projects/demo_en` (4 shots, TTS narration, one deliberately under-resolved image): generator → 9 chunked segments (`tools/run_p1_local.py`, 139 s) → concat+mux (`tools/assemble_reel.py`) → **415 frames, 13.833 s vs narration 13.831 s**; verbatim digits on screen; `[CLAMPED]`/`[DIGITS]`/confidence flags all exercised. One fix recorded: no `-shortest` in the mux (drops the final frame when audio is ms-shorter than video). RU alignment validation still pending real Sidur narration (no RU TTS voice on this machine).
4. Cloud: same graph, one validation run → measure GPU-seconds → credit budget ×cohort vs Sachkosten (§6.1.4).
   **Pre-flight ✅ 2026-07-28:** all 8 node classes of the frozen chain exist in the Cloud per-pack subsets (`SURVEY.md §2.1`) — no substitution needed. Ready-to-load graphs for every `demo_en` chunk: `python tools/run_p1_local.py --project projects/demo_en --export-all <dir>` (offline, no server). Order on the day: **one chunk first** (`shot_01_c1`, 36 frames — the cheapest that still exercises list-map + crop + text + encode), read peak RAM/GPU-s, only then the remaining 8.
5. Cloud: Sidur 18-shot facilitator run.
6. Every stock-node compromise hit → `GAPS.md` at the moment it's hit.

## Fallbacks if the crux fails (in order)

1. **Coarse-step motion:** K discrete crop positions per shot (K≈4–6 duplicated `ImageCrop+` nodes, no lists), each held for n/K frames — visible stepping, but *is* motion; crude is acceptable, absent is not (§6.1.3).
2. **Static shots + cuts only**, motion demonstrated in the local companion workflow at seminar — last resort, records the defining `GAPS.md` entry for P2.
3. Explicitly rejected: diffusion img2vid (Wan/LTX) for motion on historical stills — Branch B ethics rules, never in the reel pipeline.

## Deliberately not in P1 (SPEC §6.1)

Six effect families, multilingual burn-in, video fragments, resolution guard *in-graph* (it runs in the generator script instead), per-shot GUI editing beyond image/text swap.
