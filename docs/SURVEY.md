# SURVEY.md — Existing-node survey & Comfy Cloud coverage

**Per SPEC.md §3.** Date: 2026-07-24. Status: **draft for review — no adoption is final until its license/deps line is verified where marked (TBV).**

Method: ComfyUI Registry + GitHub + comfy.org Cloud supported-node index, per function of the Branch A flow. Decision vocabulary: **adopt** (use as-is), **wrap** (use behind our node/API), **build** (nothing fits).

---

## 1. Decisions per function

| # | Function (spec ref) | Existing candidates examined | Decision | Rationale |
|---|---|---|---|---|
| 1 | Video I/O: load footage, frame batches, preview (§5.2, §5.7) | **VideoHelperSuite (VHS)** — mature, maintained, ffmpeg-based; `Load Video` has `skip_first_frames` / `frame_load_cap` (= frame-range trim); on Comfy Cloud | **Adopt** | Exactly its job; de-facto standard; also Cloud-side. GPL-3.0 — fine at graph level (we depend on it as a running neighbour node, never link/copy its code). |
| 2 | Ken Burns motion on stills (§5.2–5.3) | **ImageMotionGuider** (needs Hunyuan Video → GPU+model, violates Branch A); **dream-video-batches** (crop-based pan/zoom utilities, integer crops → the §8 jitter class); **Simple-video-effects** (22 nodes incl. zoom/pan/shake — but AGPL-3.0, ~0 adoption, torch crop-based); **FFMPEGA** (ffmpeg `zoompan` preset = the exact jitter path §5.3 forbids as primary) | **Build** | Nothing does float-precision eased subpixel crops with anchor control, resolution guard, and per-shot preview. This is the core product; §5.3 approach stands. |
| 3 | Video shot: trim / 9:16 reframe / speed (§5.2) | VHS load-trim (adopted, #1); static crop/resize in **ComfyUI_essentials** / **KJNodes**; no node does *animated-anchor* 9:16 reframe or per-shot speed retiming | **Wrap + build** | VHS for ingest/trim; build a thin reframe+speed node sharing the crop engine from #2 (reframe pan ≈ Ken Burns pan on moving frames). |
| 4a | Grain (§5.4) | **ComfyUI-ProPost** `FilmGrain` (MIT, port of Filmgrainer, procedural, 4 grain types, image-tensor domain) | **Wrap (preview) + build (render)** | ProPost usable for in-graph still previews; final composite is the ffmpeg layer stack (looping grain *clips* per spec, which ProPost doesn't do). |
| 4b | Grade / LUT (§5.4) | ProPost `ApplyLUT` (.cube 3D LUTs); `radiance` (Cloud, 32-bit grading) | **Wrap (preview) + build (render)** | Same split: preview via ProPost, render via ffmpeg `lut3d` (same .cube files both paths — consistency check in tests). |
| 4c | Texture layer = looping video (§5.4) | none found | **Build** | ffmpeg `blend` + seamless loop/stretch to timeline duration. |
| 4d | Frame overlay (alpha PNG) (§5.4) | core `ImageCompositeMasked`; LayerStyle | **Adopt (preview) + build (render)** | Trivial both sides; render via ffmpeg `overlay`. |
| 4e | Shake (§5.4) | Simple-video-effects has one (AGPL-3.0, see #2) | **Build** | Parametric shake is ~50 lines on top of the #2 crop engine; not worth an AGPL dependency. |
| 4f | Sharpen (§5.4) | core / essentials `ImageSharpen` | **Adopt** | Done. |
| 5a | Known-text alignment → shot table (§5.1) | **No ComfyUI node for forced alignment exists at all** (all audio-text nodes are ASR-first) | **Build** | `nodes/align.py` wrapping the aligner selected in ALIGNERS.md. |
| 5b | Subtitle burn-in (§5.5) — ~~multilingual passes~~ **single EN pass (v3.1)** | **ComfyUI-Whisper** (yuvraj108c) & forks draw text per-frame via PIL — no `.ass` styling, no safe zones, no sidecars | **Build** | `.ass` + ffmpeg libass per spec. Existing nodes solve a different problem (ASR captioning of generated clips). **Weaker case since v3.1:** the multilingual and font-control arguments are gone; libass must now justify itself on render cost (`GAPS.md` #3, ~2.6×) and styling/safe-zones alone. |
| 5c | ASR subtitling showcase `teaching_subs.json` (§5.1) | **ComfyUI-Whisper** (maintained, tested 06/2026, SRT export; **CC BY-NC-SA 4.0 — not open-source, flag ⚠**); **ComfyUI-WhisperX** (adds diarization; license TBV); **Whisper-Boyo** fork (inherits NC) | **Adopt for teaching only** | Fine to *demonstrate* in the intensive; nothing NC-licensed enters our pack or gets redistributed. If the open-source commitment must extend to showcased third-party nodes, WhisperX-node license needs verifying first (⚠ decision point). |
| 6a | Narration passthrough, SFX placement, ducking (§5.6) | core audio nodes (load/save); **AudioTools** (Cloud) = STT + stem separation, not mixing | **Build (thin)** | Gain/ducking as numpy envelope or ffmpeg `sidechaincompress`; small surface. |
| 6b | SFX generation (§5.6 path 2) | **ComfyUI core Stable Audio Open workflow** — stock nodes, open-weight, prompt→SFX up to ~47 s, trained largely on Freesound CC0 | **Adopt** | On-message for the course. License = Stability AI Community License (open weights, terms ⚠ verify against grant conditions). GPU helpful → run on Cloud or the trainer machine; never a Branch A *requirement*. |
| 7 | Encode with platform profiles (§5.7) | **VHS `VideoCombine`** — custom format JSONs can expose arbitrary ffmpeg args (a 12 Mbps/faststart H.264 profile is definable) | **Wrap (previews) + build (delivery)** | Preview encodes via VHS are fine. Delivery needs burn-in + audio mux + profile in one deterministic ffmpeg pass → `nodes/encode.py` owns it. |

**Net build surface** (the pack earns its existence here): motion engine + resolution guard, shot table + alignment, layer-stack compositor, `.ass` subtitles (**EN only since v3.1**), thin audio/encode nodes. Everything routine is adopted.

---

## 2. Comfy Cloud supported-node coverage (P1 gating deliverable, SPEC §3)

Source: comfy.org/cloud/supported-nodes per-pack pages (fetched 2026-07-24; node-level, from Cloud `object_info`).

**Key discovery: Cloud supports per-pack *subsets*, not whole packs.** Image-Filters is 3 nodes (constant color + latent offset — useless to us); ComfyUI_LayerStyle's subset has **no** blend modes, no TextImage, no transforms — utility nodes only. Never assume a function exists because its pack is "supported"; check the node.

Verdict per SPEC §3 gating question:

| # | Function | Verdict | Evidence (exact nodes) | P1 workaround where absent/partial |
|---|---|---|---|---|
| 1 | Video / image-sequence I/O | **available** | VHS: `VHS_LoadImages(Path)`, `VHS_LoadVideo(Path/FFmpeg)`, `VHS_VideoCombine`; core `RepeatImageBatch`, `ImageBatch` | — |
| 2 | Audio ingest + mux | **available** | core `LoadAudio`; `VHS_LoadAudio(Upload)`; `VHS_VideoCombine` optional audio input; AudioTools `Trim Audio`/`Gain`/`Mix`/`Show Audio Info` | — |
| 3 | Image transforms for Ken Burns | **partial → workaround CONFIRMED** | Static-parameter crop/resize only: essentials `ImageCrop+`/`ImageResize+`, WAS `Image Crop Location`/`Image Resize`. **No animated pan/zoom node anywhere on the list** | **Verified locally 2026-07-24:** `StringSplitDataList → CastToInt` data lists map-execute `ImageCrop+` (single image broadcasts, no RepeatImageBatch) → `ImageResize+` → `ImageListToBatch+` → `VHS_VideoCombine`. 240-frame eased zoom in 48 s. Caveat: ~11.5 GiB RAM per 240-frame shot (source-res intermediates) → chunk to ≤60 frames on Cloud. Cloud **node availability confirmed 2026-07-28** (see pre-flight below); execution semantics still to re-validate on Cloud |
| 4 | Text / subtitle overlay | **available for the project's needs (rescoped v3.1)** | essentials `DrawText+` (bitmap text). No `.ass`/libass path anywhere (expected). Tested 2026-07-24: the pack's single font (Share Tech Mono) is Latin-only — RU and HY render as tofu; no font-install path on Cloud | **English is now the only language (SPEC v3.1)**, so `DrawText+` covers the requirement outright and the PNG-strip workaround is abandoned unused. `GAPS.md` #1 withdrawn accordingly. Note the *separate*, still-live constraint: `DrawText+` must run in list domain (`GAPS.md` #3) |
| 5 | Compositing / blend modes | **partial** | WAS `Image Blending Mode` / `Image Blend (by Mask)` (LayerStyle subset has **none**) | Not needed for P1 (effects are P2); WAS suffices for a demo blend |
| 6 | LUT application | **partial** | essentials `ImageApplyLUT+` exists, but needs `.cube` files in `models/luts` — whether Cloud accepts user files there is unverified | P1 skips grade (not required §6.1). Alternative to test later: `radiance` grading nodes (74 on Cloud, unexamined) |
| 7 | Encode control | **partial** | `VHS_VideoCombine`: `frame_rate`, `crf`, `pix_fmt=yuv420p`, h264/mp4 formats, audio mux | crf instead of 12 Mbps bitrate profile — fine for P1; platform-profile encode stays P2 (`nodes/encode.py`) |
| 8 | Speech / alignment | **absent** (as predicted) | No forced-alignment node exists. AudioTools has `Speech-to-Text + SRT (Whisper)` — ASR only, the error class we reject for production | Prepared-inputs model per SPEC §4: `stable-ts` runs outside the graph → `shots.json` (+ crop CSVs) uploaded as input assets. AudioTools Whisper is a bonus: the ASR-vs-alignment teaching contrast can be shown **on Cloud** |

### 2.1 Pre-flight: node-level Cloud availability of the frozen P1 chain

Checked 2026-07-28 against the per-pack Cloud subset pages (`comfy.org/cloud/supported-nodes/<pack>`), because §2's key discovery is that Cloud carries *subsets*. Every node class emitted by `tools/run_p1_local.py::build_chunk_workflow` (identical to `docs/example_shot_chunk_api.json`):

| Node class (API) | Pack | Cloud |
|---|---|---|
| `LoadImage` | core | ✅ |
| `Basic data handling: StringSplitDataList` ("split (to data list)") | basic_data_handling (258 of 309 nodes on Cloud) | ✅ |
| `Basic data handling: CastToInt` ("to INT") | basic_data_handling | ✅ |
| `ImageCrop+` | ComfyUI_essentials (62 nodes on Cloud) | ✅ |
| `ImageResize+` | ComfyUI_essentials | ✅ |
| `DrawText+` | ComfyUI_essentials | ✅ (EN only — GAPS #1) |
| `ImageListToBatch+` | ComfyUI_essentials | ✅ |
| `VHS_VideoCombine` | VideoHelperSuite | ✅ |

**No node substitution is needed for the Cloud run.** What this does *not* prove, and what the validation run (verification step 4) still has to establish: (a) that Cloud's executor applies the same list-map broadcast semantics, (b) that a ≤60-frame chunk fits Cloud RAM (unknown, GAPS #2), (c) GPU-seconds per chunk. The fallbacks in P1_GRAPH.md remain live until (a) is observed.

**Net P1 verdict:** a stock-node reel graph is feasible — I/O, audio, encode, text are there. The single genuine risk is #3 (per-frame motion). It is a testable hypothesis, not a blocker: verify list-map crop locally (same stock nodes) before any Cloud credits are spent; if it fails, that is the first and defining `GAPS.md` entry and the strongest possible argument for the P2 pack.

**Conclusion (confirms §3 deployment split):** nothing on Cloud covers alignment or production subtitling; no Branch A function silently migrates. Cloud remains right for P1 (reduced set above), Branch B, SFX generation, and the AudioTools ASR demo.

---

## 3. License ledger for touched third-party packs

| Pack | License | Status |
|---|---|---|
| VideoHelperSuite | GPL-3.0 | verified — graph-level use OK |
| ComfyUI-ProPost | MIT | verified |
| ComfyUI-Whisper (yuvraj108c) | CC BY-NC-SA 4.0 | verified — **teaching-demo only, never a dependency** |
| ComfyUI-Simple-video-effects | AGPL-3.0 | verified — not adopted |
| ComfyUI_essentials, KJNodes, ComfyUI-WhisperX | TBV | check before any adoption beyond preview use |
| **pedalboard** (Spotify) 0.9.19 — a *declared dependency of this pack*, not a neighbour | **GPL-3.0** | **verified 2026-09-03** from the installed wheel's own metadata. Adopted for `nodes/voice.py`: Rubber Band time-stretch, and the JUCE compressor and gate. GPLv3 is the strongest obligation in this ledger because we **import** it rather than sit beside it in a graph — and it is satisfied by construction: this pack is GPL-3.0-or-later already, for the same reason (ComfyUI's API). The bundled Rubber Band library carries the same licence. Nothing here may be re-licensed more permissively while this import stands |
| **pyloudnorm** 0.1.1 | **MIT** | **verified 2026-09-03** from the installed wheel. ITU-R BS.1770 integrated loudness, the meter in the voice graph. No obligation beyond attribution |
| Stable Audio Open 1.0 weights (+ `t5_base` text encoder) | Stability AI Community License | ⚠ **still to verify against the Zuwendungsbescheid**, and now load-bearing enough to need an answer: it is the model `docs/SOUND_DESIGN.md` is written against, and the one `example_workflows/sound_design.json` opens with. Free for research and for commercial use under the licence's revenue threshold, but it is **not an OSI licence**, so it is not "open source end to end" in the sense the grant commits to. Two things keep this from being a blocker rather than a question: **the pack ships no weights** — the checkpoint is a file the user already has, named in a stock `CheckpointLoaderSimple` — and **the sound design does not depend on generation at all**. A row of `sfx.csv` whose `file` column names a CC0 recording plays identically to a generated one; the mixer never learns which it was. Swapping the model is swapping one filename in one node. |
| **ComfyUI-Olm-DragCrop** | **source-available, NOT open source** | ⚠ **installed 2026-08-10 — read this before relying on it.** The author's own words: "source-available, but not open-source under a standard open-source license, and not freeware." Using it is unrestricted and *"any results you create with it are yours"*, so the museum reel is unaffected. But **"redistribution … is strictly prohibited without explicit written permission"**, which collides with two planned uses: bundling it inside `comfyui-memoacts`, and shipping it in the cloned machine image for the September workshop. Neither is permitted as things stand — but as of **2026-08-29 the imaging question is moot**: the pack's own focus picker does the framing job, so the September image does not carry DragCrop (`docs/WORKSHOP_MACHINE_SETUP.md` §8). Three ways out, in order of cost: ask the author (he explicitly invites gray-area questions and this is a museum/education case); have each student install it themselves from the official repo, which is plain *use*; or write our own crop node, which is the fallback already named in `archive/handoffs/20260805_HANDOFF_comfy_threeband.md` §7. |

### Assets vendored into the pack (P2)

| Asset | License | Status |
|---|---|---|
| Share Tech Mono v1.003 (`assets/fonts/ShareTechMono-Regular.ttf`) | **SIL OFL 1.1** | **verified 2026-07-28** — read from the font's own name table, not assumed. © 2012 Carrois Type Design, Ralph du Carrois, Reserved Font Name "Share". `assets/fonts/OFL.txt` carries the licence as the OFL requires; its copyright line matches the font's embedded string exactly. Fully open — no conflict with the grant. **Reserved Font Name: a modified copy may not keep the name "Share".** |

| Special Elite (`assets/fonts/SpecialElite-Regular.ttf`) | **Apache-2.0** | **verified 2026-08-20**, licence text vendored as `LICENSE-SpecialElite.txt`. Fully open, commercial use permitted, no conflict with the grant. Set the typed sheet until Erika Ormig replaced it |
| Erika Ormig (`assets/fonts/erika-ormig.regular.ttf`) | **CC BY-ND 4.0** | **verified 2026-08-28**; terms and reasoning in `assets/fonts/LICENSE-ErikaOrmig.txt`. Peter Wiegel, via 1001fonts. Commercial use is permitted, so it clears the non-commercial bar — but it is **not an OSI licence**, and **NoDerivatives is the clause to watch**: setting type with it is use, modifying the file is not. No subsetting, no re-hinting, no format conversion. A future step that needs any of those must replace the font rather than cut it down. **Attribution travels with it: "Erika Ormig by Peter Wiegel, CC BY-ND."** Adopted because Erika was the Seidel & Naumann typewriter standard in German offices through the 1940s — the machine a Wehrmacht document of May 1945 was actually typed on — where Special Elite is an American face drawn from typed impressions. Measured as a drop-in: cap-height/advance 1.005 against Special Elite's 1.017, within 1.2%, so the page layout needs no retuning |

Share Tech Mono was copied in from `ComfyUI_essentials/fonts/` so P2 no longer depends on a hand-cloned pack it otherwise does not need; burn-in resolves it via `render.encode(fontsdir=...)`, defaulting to `assets/fonts/`. The two typewriter faces are not for captions — they are what the page nodes set type with.

§8 pitfall check (GPU/model creep via adopted nodes): VHS, essentials, ProPost, core compositing — none pulls models or requires GPU. The only model-bearing adoption is SFX generation, which is optional and Cloud-routable by design.
