# GAPS.md — stock-node compromises hit during P1

Per SPEC.md §0/§6.1.5: every point where a stock / Cloud-supported node forces a compromise is recorded **as it is hit**. This file is the P2 backlog for `comfyui-memoacts`.

| # | Function | Stock-node compromise | Impact in the PoC | P2 implication |
|---|---|---|---|---|
| 1 | Subtitle burn-in, non-Latin (RU, **HY** — mandated course languages) | `DrawText+` (essentials) ships exactly one font, Share Tech Mono, **Latin-only** — verified 2026-07-24: RU and HY render as tofu boxes. No font-install path on Cloud (pack dir read-only); no libass anywhere | Cloud-side text rendering works for EN only. Workaround: subtitle strips pre-rendered outside the graph (PIL + Noto Sans/Noto Sans Armenian) as per-shot transparent PNGs, composited via core `ImageCompositeMasked`; EN track may use `DrawText+` live for the teaching demo | `nodes_subs.py` with ffmpeg libass + explicit font control is confirmed necessary, not speculative; Armenian shaping test moves to P2 acceptance |
| 2 | Per-shot memory | List-map crux **passed** (not a compromise), but one 240-frame shot costs ~11.5 GiB server RAM — source-res crop intermediates are held for the whole shot before resize collects | Chunk shots to ≤60 frames on Cloud (Cloud RAM **unmeasurable**, see #5); per-shot RAM scales with *source* image resolution, not output | P2 motion engine renders frame-streaming through ffmpeg, never materialising a shot as tensors — this measurement is the justification |
| 3 | Subtitle overlay on batches | `DrawText+` with a **batched** `img_composite` collapses the batch to a single frame (verified 2026-07-24: 60-frame chunk → 1-frame segment) | Run `DrawText+` in **list domain** (before `ImageListToBatch+`) — same text mapped per frame. Works, but renders text N times: full demo render 139 s vs 54 s without text (~2.6×) | `nodes_subs.py` burns subtitles once per segment via libass, not per frame — second justification after #1 |
| 4 | Getting source images onto Cloud | `POST /api/upload/image` is **content-addressed**: it ignores the requested `filename` and stores the file under its SHA-256 digest (verified 2026-07-28: `01_big.png` → `a003f3b5…c5e.png`). Bare-filename `LoadImage` references therefore never resolve on Cloud | Every exported chunk graph must have its `LoadImage.image` rewritten to the digest the upload returned, *after* upload — the graph is not submittable as exported. Breaks the "upload under the exact filename" assumption in `manifest.json` and the hand-build path in `docs/PARTICIPANT_GRAPH_RECIPE.md` (a facilitator uploading via the Cloud UI gets a hash they must paste back into every `LoadImage`) | Submission tooling owns an upload→digest map and patches graphs before submit; the manifest should carry a `cloud_name` field per image. Facilitator recipe needs an explicit "your filename will change" step |
| 5 | Run instrumentation on Cloud | Cloud deliberately zeroes resource telemetry: `/api/system_stats` returns `devices: []`, `ram_total: 0`, `ram_free: 0`, and `/api/jobs/{prompt_id}` carries **no memory field**. No credits/usage endpoint is exposed to the MCP token either | **Peak RAM is not measurable on Cloud** — the ~11.5 GiB figure in #2 and the ≤60-frame chunk ceiling stay justified by *local* measurement only, never confirmed against Cloud hardware. Cost must be derived from wall-clock: `/api/jobs/{prompt_id}` does give `create_time` / `execution_start_time` / `execution_end_time` | Budget modelling (SPEC §6.1.4) uses execution-window seconds as the GPU-second proxy; the RAM ceiling that drives chunk sizing remains an unvalidated assumption on Cloud and must be re-derived empirically (bisect chunk size until OOM) if chunking is ever relaxed |

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
