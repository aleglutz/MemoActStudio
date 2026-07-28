# GAPS.md — stock-node compromises hit during P1

Per SPEC.md §0/§6.1.5: every point where a stock / Cloud-supported node forces a compromise is recorded **as it is hit**. This file is the P2 backlog for `comfyui-memoacts`.

> **Caveat on what this file is a backlog *for* (SPEC v3.1 §10).** Students are now permanently on Comfy Cloud, where `comfyui-memoacts` cannot be installed. So these gaps are only "backlog" for the video-series production tool; for the students they are **permanent properties of the workflow they are taught**. That distinction is unresolved and changes how several rows below should be prioritised — a gap that blocks students is worth solving *within* stock nodes, a gap that only affects production is worth solving in the pack.

Withdrawn rows are struck through rather than deleted — the evidence stays useful if scope changes back.

| # | Function | Stock-node compromise | Impact in the PoC | P2 implication |
|---|---|---|---|---|
| 1 | ~~Subtitle burn-in, non-Latin (RU, HY)~~ **— WITHDRAWN 2026-07-28 (SPEC v3.1)** | `DrawText+` ships one Latin-only font (Share Tech Mono); RU and HY render as tofu boxes (verified 2026-07-24). No font-install path on Cloud, no libass anywhere. **Still true — no longer a gap:** translation left project scope, so English is the only language and Share Tech Mono covers it | **None.** `DrawText+` live burn-in is now the intended path, not a fallback. The PNG-strip workaround (PIL + Noto, composited via `ImageCompositeMasked`) is abandoned unused | ~~`nodes_subs.py` justified by font control~~ — this justification is gone; #3 (per-frame cost) is now the *sole* argument for libass in P2. Revive this row only if translation re-enters scope |
| 2 | Per-shot memory | List-map crux **passed** (not a compromise), but one 240-frame shot costs ~11.5 GiB server RAM — source-res crop intermediates are held for the whole shot before resize collects | Chunk shots to ≤60 frames on Cloud (Cloud RAM **unmeasurable**, see #5); per-shot RAM scales with *source* image resolution, not output | P2 motion engine renders frame-streaming through ffmpeg, never materialising a shot as tensors — this measurement is the justification |
| 3 | Subtitle overlay on batches | `DrawText+` with a **batched** `img_composite` collapses the batch to a single frame (verified 2026-07-24: 60-frame chunk → 1-frame segment) | Run `DrawText+` in **list domain** (before `ImageListToBatch+`) — same text mapped per frame. Works, but renders text N times: full demo render 139 s vs 54 s without text (~2.6×). Confirmed to transfer to Cloud 2026-07-28 **RESOLVED in P2, 2026-07-28.** libass burn-in measured on the same demo_en material: **23.0 s with subtitles vs 23.1 s without** — free, within noise, against P1's 139 s vs 54 s (~2.6×). Cost is now per *cue*, not per frame, so it no longer scales with frame count. Bonus P1 could not do at all: libass wraps a long caption onto two lines, where `DrawText+` ran it off the frame. `memoacts_core/subs.py` + `render.encode(ass=...)` |
| 4 | Getting source images onto Cloud | `POST /api/upload/image` is **content-addressed**: it ignores the requested `filename` and stores the file under its SHA-256 digest (verified 2026-07-28: `01_big.png` → `a003f3b5…c5e.png`). Bare-filename `LoadImage` references therefore never resolve on Cloud | Every exported chunk graph must have its `LoadImage.image` rewritten to the digest the upload returned, *after* upload — the graph is not submittable as exported. Breaks the "upload under the exact filename" assumption in `manifest.json` and the hand-build path in `docs/PARTICIPANT_GRAPH_RECIPE.md` (a facilitator uploading via the Cloud UI gets a hash they must paste back into every `LoadImage`) | Submission tooling owns an upload→digest map and patches graphs before submit; the manifest should carry a `cloud_name` field per image. Facilitator recipe needs an explicit "your filename will change" step |
| 5 | Run instrumentation on Cloud | Cloud deliberately zeroes resource telemetry: `/api/system_stats` returns `devices: []`, `ram_total: 0`, `ram_free: 0`, and `/api/jobs/{prompt_id}` carries **no memory field**. No credits/usage endpoint is exposed to the MCP token either | **Peak RAM is not measurable on Cloud** — the ~11.5 GiB figure in #2 and the ≤60-frame chunk ceiling stay justified by *local* measurement only, never confirmed against Cloud hardware. Cost must be derived from wall-clock: `/api/jobs/{prompt_id}` does give `create_time` / `execution_start_time` / `execution_end_time` | Budget modelling (SPEC §6.1.4) uses execution-window seconds as the GPU-second proxy; the RAM ceiling that drives chunk sizing remains an unvalidated assumption on Cloud and must be re-derived empirically (bisect chunk size until OOM) if chunking is ever relaxed |

## P2 findings — carried over from P1 code, found while building the pack

**Resolution guard was incomplete (found 2026-07-28, fixed in `render.py`).**
`schedule.compute` clamps the zoom *rate* so motion never digs below the output
width, and flags `clamped`. But a source can be too small **before any zoom**:
demo_en's `03_small.png` (800×1000) yields a 562px-wide 9:16 window against a
1080px output, so every frame is enlarged 1.92× — and P1 did this silently, in
both the local and Cloud renders. Clamping the rate cannot fix it; the rate had
already been clamped to zero, which is also why that shot renders completely
static (344 of 415 unique frames, not 415).

This violated a stated non-negotiable ("never silently upscale", CLAUDE.md /
SPEC §5.2). `render.py` now enforces the SPEC-specified policy at render time —
`on_upscale = warn` (default) | `error` | `allow`.

Consequence to keep in view: **the guard is only as good as the shot's image
assignment.** Warning at render time is late — by then the creator has already
chosen that image for that shot. The P2 GUI should surface `max_zoom` per shot
*at selection time* (SPEC §5.2 wants a live preview anyway), so the warning
becomes a choice rather than a report.

## Cloud validation run — 2026-07-28 (P1_GRAPH verification step 4)

First real Cloud execution of the frozen chain. `shot_01_c1` (36 frames), submitted
via the `comfy-cloud` MCP, `prompt_id 1cd9ef5f-e7bd-422e-be3c-27450af063e7`.
Graph byte-identical to `projects/demo_en/cloud_graphs/shot_01_c1.json` except the
`LoadImage.image` digest rewrite forced by #4.

**Both hypothesised failure modes were negative — no fallback is needed.**

- **Not a batch collapse.** Output is **36 frames**, not 1 → Cloud honours the
  list domain, so the #3 workaround transfers intact. `P1_GRAPH` fallback 2 stays
  unused.
- **Not a static segment.** All 36 decoded frames are unique (framemd5), and the
  zoom is visible frame 0 → 35 → the list-map broadcast **does** transfer.
  `P1_GRAPH` fallback 1 (coarse-step motion) stays unused.
- Output is 1080×1920, 30 fps, 1.200 s, h264/yuv420p — matches the local render.
  `DrawText+` burn-in rendered correctly in Share Tech Mono (EN).

Timing (from `/api/jobs/{prompt_id}`, the only cost signal Cloud exposes — see #5):

| Measure | Value |
|---|---|
| Queue wait (`create` → `execution_start`) | 2.709 s |
| **Execution window** (`execution_start` → `execution_end`) | **20.724 s** |
| Graph execution (`execution_start` → `execution_success` msg) | 19.527 s |
| Total (`create` → `execution_end`) | 23.433 s |
| Per frame (graph exec ÷ 36) | 0.542 s |

Extrapolation, **not yet measured**: the full 9-chunk / 415-frame `demo_en` reel
projects to ~225 s of graph execution (415 × 0.542) plus ~9× per-chunk overhead
(~1.2 s teardown + ~2.7 s queue each) ≈ **4–4.5 min of billable window**. Confirm
against the real 9-chunk run before it feeds the SPEC §6.1.4 cohort budget —
per-frame cost may not be flat across chunk sizes, and queue wait is not ours to
control.
