# MemoActs Reel Renderer — Technical Specification v3.1

**For:** Claude Code
**Project:** MemoActs 2026 · Phase 7 "How do wars end?" + Online Intensive curriculum
**Date:** 2026-07-28 · supersedes v3 (2026-07-24), which superseded v2, the v2.1 review patch, and the PoC-target addendum (originals archived in `docs/archive/`)
**Language:** English (repo language; course instruction language is English)

**Changelog v3 → v3.1 (roadmap correction, 2026-07-28):** three scope decisions by the project owner —

1. **Subtitles are English-only, for an English script and English narration.** Translation into RU / DE / HY is **removed from this project's scope entirely** — it is a separate task performed outside this workflow with local DeepL + whisperX. Consequences: §2.4 "visuals render once, languages are passes" is withdrawn; §5.5 multilingual burn-in is out of scope; §5.1 alignment is EN-only; RU inflected number normalisation (§10) is closed as not-applicable; Armenian rendering and alignment leave the plan (§9.6, `HARDENING.md`). `GAPS.md` #1 is rescoped accordingly — `DrawText+`'s Latin-only font stops being a blocker and becomes the intended path.
2. **`projects/sidur` is no longer the development test project.** It was a planning example, not a dev fixture. A new **English** script + narration recording will be supplied by the project owner; acceptance §6.2 retargets to it. Until it arrives, `projects/demo_en` remains the only working fixture.
3. **Comfy Cloud is the students' environment, by decision and not by convenience.** Online participants cannot be made to depend on their own hardware — local installs risk system differences and conflicts that have nothing to do with the course. This makes Cloud the delivery target for everything student-facing, and turns the pack's Cloud-incompatibility (§3) into a live roadmap question rather than a P3 footnote — see §10.

**Changelog v2 → v3 (per v2.1 patch + PoC addendum):** priority principle added — working PoC beats portability (§0); build order reversed: P1 Cloud PoC from stock nodes precedes the custom pack, PoC target decided as option (b) Comfy Cloud stock-node graph (§0, §3); prepared-inputs model for P1 alignment (§4); stable-ts confirmed as primary aligner behind an `Aligner` interface, bake-off narrowed to stable-ts vs whisperx on RU+EN, Armenian off the critical path (§5.1); text-normalisation pre-pass required before alignment (§5.1); `shot_lead_ms` control added (§5.2); acceptance criteria split into P1 and P2 sets, §6.8 amended — aligner speech model permitted, no GPU/diffusion checkpoints (§6); NC licences tolerable for demos/fallbacks only (§3); working-method principle added (§2.6); `GAPS.md` and `HARDENING.md` introduced (§0, §3).

---

## 0. Priority principle and phasing

**A working end-to-end PoC beats portability.** Where a choice is between shipping a working reel sooner and keeping the install light, offline-capable, or maximally portable — choose the working reel. Portability and offline deployment are **September hardening tasks with their own checklist (`HARDENING.md`)**, not gates on the July prototype. Do not let install weight, model size, or offline-install concerns block or slow any implementation decision now: note them in `HARDENING.md` and move on.

**PoC target (decided): option (b)** — the PoC is assembled **on Comfy Cloud from stock / Cloud-supported nodes only**, accepting reduced functionality, so that intensive participants can run it in the environment they are being taught in. This reverses the v2 build order; it does **not** cancel the custom pack.

| Phase | Target | Environment | Purpose |
|---|---|---|---|
| **P1 — now** | Cloud PoC from stock nodes | Comfy Cloud | Teaching artifact for the August online intensive; establishes what stock nodes actually cover |
| **P2 — after P1** | `comfyui-memoacts` pack | Local ComfyUI | Fills the gaps P1 exposed; production quality for the video series **and** the September workshop |
| **P3 — Sept+** | Hardening, workshop provisioning, Registry publication | Two rented machines | September offline workshop, portability |

### Curriculum delivery — the two audiences (added v3.1, 2026-07-28)

The course has two parts with **different environments, different sizes, and different depth**. This is the structural fact that drives deployment (§3) and hardening (`HARDENING.md`):

| | **Part 1 — August online intensive** | **Part 2 — September offline workshop** |
|---|---|---|
| Students | **30** | **16** (a subset of the same 30) |
| Format | 8 lessons | Hands-on workshop |
| Depth | Overview / orientation — principles and open-source content tooling, Comfy-in-the-Cloud among them | **Practical / production** |
| Environment | **Comfy Cloud** | **Local ComfyUI on two rented machines** |
| Hardware risk | None — no dependence on personal machines, which is exactly why Cloud was chosen | Low and *controlled* — two machines the project provisions, not 16 unknown personal ones |

Two consequences worth stating explicitly, because both were open questions until now:

1. **The pack is not production-only.** §3's tension — students permanently capped at stock Cloud nodes — **is resolved**: `comfyui-memoacts` reaches students in September, on the rented machines. The Cloud ceiling binds Part 1 only, and Part 1 is deliberately an overview, so a reduced feature set is appropriate there rather than a compromise.
2. **The September workshop is a real phase, and its provisioning problem is small.** Sixteen unknown personal machines would have been the hard version; two project-controlled machines is a setup task, done once and cloned. `HARDENING.md` is rewritten around this — the USB/museum-Wi-Fi/unknown-hardware items were solving a problem that no longer exists.

**Ratio to keep in view:** 16 students on 2 machines is ~8 per machine, so the workshop runs in rotation. That is a scheduling constraint, not a technical one — but it means a single render must not monopolise a machine for long, which makes render *latency* (not just correctness) a workshop requirement. `GAPS.md` #3's ~2.6× text-rendering cost is the first place that bites.

**The gaps are discovered empirically, not predicted.** Build P1 first, record every point where a stock node forces a compromise in **`GAPS.md`** as it is hit, and let that list define the pack's scope in P2 — we stop guessing which functions are worth writing.

Milestone reality: the online intensive is running **now** (July–August); the video series goes into production **October–November**. P1 has weeks, P2 has months. Scope P1 accordingly — it is allowed to be crude.

**Iterate locally, validate on Cloud.** Cloud runs consume credits per GPU-second; a 2.5-minute render iterated dozens of times is a real cost. Develop graph logic against a local ComfyUI using the same stock nodes; use Cloud runs for validation and the participant-facing version. Note any behaviour that differs between the two in `HARDENING.md`.

---

## 1. What this is

A **ComfyUI-based production workflow that replicates the subset of CapCut functionality actually used in historical vertical video production** — and only that subset, chosen for two purposes: producing the "How do wars end?" series, and teaching the online intensive.

Not a general automation tool. Not headless. The creator works in a GUI, sees the visuals, and decides — which image goes with which sentence, which effect fits, where a cut lands. Choosing and placing is part of creation and stays with the human. What the workflow removes is the *mechanical cost* of those decisions: hand-keyframing every zoom, regenerating subtitles to move one caption, re-exporting to check a change, paying for auto-subtitle quota.

**Functional coverage target (the CapCut subset being replicated — full coverage is the P2 target; P1 covers the reduced set in §6.1):**

| CapCut function used | Equivalent |
|---|---|
| Timeline from audio + stills/clips | Shot table derived from narration, editable in GUI |
| Manual keyframes for zoom / Ken Burns | Motion presets per shot, selectable + tunable, previewable |
| ~20 effects (grain / texture / frame / grade / shake / sharpen) | Six parameterised effect families with named presets |
| Video texture layer over full timeline | Looping texture layer node |
| Auto-subtitles (limited, error-prone, paid quota) | Known-text alignment + editable subtitle track, unlimited, **English only** (v3.1) |
| Sound effects from built-in library | CC0 library and/or generated in ComfyUI |
| Export MP4 H.264 1080×1920 30 fps 12 Mbps | Encode node with platform profiles |
| Video clips on the timeline (trim, speed, reframe) | Video shot support: trim + 9:16 reframe |

Out of coverage deliberately: CapCut's trend-sound library, direct platform posting, body effects, template marketplace.

---

## 2. Design principles

1. **GUI for judgement, automation for mechanics.** Every creative decision is visible and reversible in the ComfyUI graph; every mechanical consequence (keyframe math, subtitle timing, format juggling) is computed.
2. **The narration is the master clock — as a default, not a cage.** Shot boundaries are *proposed* from sentence alignment and then human-editable. The creator can split, merge, and nudge boundaries; the system recomputes downstream.
3. **Mixed media is native.** A shot holds either a still (Ken Burns motion) or a video fragment (trim + reframe + speed). One timeline model for both. This covers the MBK capitulation-ceremony footage (1280×800 → 9:16) alongside archival stills. *(P2 — video fragments are not in the P1 PoC.)*
4. ~~**Visuals render once, languages are passes.**~~ **Withdrawn in v3.1.** Translation is out of project scope (handled separately with local DeepL + whisperX), so there is one language — English — and one burn-in pass. Keep the *shape* of the design honest anyway: nothing may hard-code English or fuse text into the visual intermediate in a way that would forbid a second pass, because re-adding languages must stay a scope decision rather than a rewrite.
5. **Open-source end to end.** The Zuwendungsbescheid commits the project to open-source AI tools; every model and component in the workflow must be open-weight / open-source or replaceable by one. Non-commercially-licensed components (e.g. MMS weights, the ComfyUI-Whisper teaching node) are **tolerable for demonstration and fallback use only** — nothing on the critical path of any production function may depend on them. Every adopted component's licence is recorded in `SURVEY.md`.
6. **The spec is not authoritative on verifiable facts.** v1 listed `aeneas` as the preferred aligner; the survey correctly established it as a dead end. Anything in this spec marked "verify" or "evaluate" is a hypothesis to test, not an instruction to follow. Surfacing a contradiction is a deliverable, not a delay.

---

## 3. Architecture

**P1 is a Comfy Cloud graph built from stock / Cloud-supported nodes only** (§0). The architecture below is the **P2 product** — its scope is refined by what P1 records in `GAPS.md`.

**Primary interface (P2): a ComfyUI custom node pack (`comfyui-memoacts`).**
**Under the hood: a Python core package (`memoacts_core`) that the nodes call.**
**Rendering and encoding: ffmpeg wherever it is the optimal executor** (Ken Burns frame rendering, compositing, subtitle burn-in, encode) — invoked by the nodes, invisible to the user.

The core package exists so that logic is testable without a GUI and reusable in batch contexts (and so P1 can run alignment outside the graph, §4); the development target and acceptance environment for P2 is the ComfyUI graph.

```
comfyui-memoacts/           # custom node pack — the P2 deliverable
  ├── nodes_align.py        # narration+script → editable shot table
  ├── nodes_shot.py         # per-shot assembly: media, motion, effects
  ├── nodes_layers.py       # grain/texture/frame/grade/shake families
  ├── nodes_subs.py         # subtitle track, styling, multilingual burn-in
  ├── nodes_audio.py        # narration passthrough, SFX placement/generation hook
  ├── nodes_video.py        # video shots: trim, reframe 9:16, speed
  ├── nodes_encode.py       # ffmpeg encode, platform profiles
  └── memoacts_core/        # shared logic, GUI-independent, unit-tested
example_workflows/
  ├── reel_poc_cloud.json   # P1: stock-node Cloud PoC graph
  ├── reel_stills.json      # P2: canonical stills-only reel graph
  ├── reel_mixed.json       # P2: stills + video fragments (KAPFILM case)
  └── teaching_subs.json    # showcase: existing Comfy subtitling workflows
assets/                     # luts, grain, frames, textures, sfx (+ licence manifest)
projects/sidur/             # first test project
GAPS.md                     # P1: every compromise forced by stock nodes → P2 backlog
HARDENING.md                # deferred portability/offline items → September (P3)
```

**Node survey: completed 2026-07-24** — findings and adopt/wrap/build decisions per function in `SURVEY.md`; aligner evaluation in `ALIGNERS.md`. **`SURVEY.md`'s Cloud-coverage section is now the gating deliverable for P1 scope.** It must answer concretely, per function, against the actual Comfy Cloud supported-node list:

- **Video / image sequence I/O** — is VideoHelperSuite (or equivalent) available? The single biggest determinant; without it, sequence assembly and encode become hard.
- **Audio loading and duration** — can the graph ingest the narration MP3 and mux it into the output?
- **Image transforms** — crop/scale/pan primitives sufficient for Ken Burns? At what precision, and can they be driven per-frame rather than per-run?
- **Text / subtitle rendering** — any node that draws styled text over frames? Any `.ass`/libass path, or only bitmap text overlay?
- **Compositing / blend modes** — overlay, soft-light, screen for grain and texture layers?
- **LUT application** — any `lut3d` equivalent?
- **Encode settings** — can output fps, bitrate and pixel format be controlled, or are they fixed?
- **Speech / alignment** — almost certainly **not** available (stable-ts is a Python library; ComfyUI-Whisper is a non-stock, NC-licensed custom node). Assume no, verify anyway.

Record each as: available / partially available / absent → and for absent, the P1 workaround (and a `GAPS.md` entry once hit in practice).

**Development environment (set up before writing code):**

1. **Install the ComfyUI custom-node skills plugin** for Claude Code (`jtydhr88/comfyui-custom-node-skills`, via plugin marketplace): 9 skills covering V3 node structure, inputs/outputs, datatypes, lifecycle, frontend extensions, migration, and packaging — source-verified against ComfyUI backend/frontend. Use them; do not reconstruct the node API from memory.
2. **Write the pack against the V3 API** (`io.ComfyNode`, `io.Schema`, `io.NodeOutput`) — not the V1 legacy API. Rationale: V3 is the recommended API the skills document first; its lifecycle hooks (`fingerprint_inputs`, `validate_inputs`, lazy evaluation) are exactly what per-shot cache invalidation (§8) needs; and V3-clean packaging is a precondition for the Registry publication (P3).
3. **MCP for the dev loop, split by environment:**
   - **Local:** run a ComfyUI MCP server against the local dev instance (e.g. `comfyui-mcp` or Comfy Pilot) so Claude Code can load the graph, execute, inspect outputs, and iterate agentically instead of via manual UI testing.
   - **Cloud:** connect the official **Comfy Cloud MCP** (`cloud.comfy.org/mcp`, OAuth from Claude Code; public beta) to build and run the P1 PoC and teaching graphs on Cloud GPUs — the same environment the intensive uses. Note beta caveats: generated assets may lack embedded workflow metadata; complex graphs may need retries.
4. Keep `SURVEY.md` findings (existing nodes, Cloud coverage) in the repo root next to this spec.

**Part 1 (August, 30 students) runs on Comfy Cloud — a constraint, not a preference.** Online participants cannot be made to depend on their own hardware: system differences and local install conflicts are failure modes that have nothing to do with the course, and there is no support channel for thirty unknown Windows machines. Everything in the online intensive therefore ships as a Cloud workflow, and its capability ceiling is whatever stock Cloud nodes provide — the P1 feature set. Since Part 1 is an overview (§0), that ceiling is appropriate to the teaching goal rather than a compromise forced on it.

**Part 2 (September, 16 students) runs local on two rented machines** — which is where `comfyui-memoacts` reaches students. The pack cannot be installed on Comfy Cloud (curated list only), but it does not need to be: the practical, production-oriented half of the curriculum is precisely the half that runs locally. This resolves what v3.1 initially recorded as an open architectural tension. Registry publication (§9.8) remains a P3 open-source commitment, not a delivery dependency.

**Provisioning follows from this and is small:** two machines, project-controlled, imaged once and cloned. Their specification is a real deliverable with a real input — the per-shot RAM measurement in `GAPS.md` #2 (~11.5 GiB for a 240-frame shot at source resolution) is what sizes the rental. Note that `GAPS.md` #5 established RAM is unmeasurable on Cloud; for the rented machines it is measurable and load-bearing, so the local figure regains its importance.

**Deployment strategy (verified 2026-07-24, decided):** Comfy Cloud supports only a curated list of popular custom nodes — arbitrary packs such as `comfyui-memoacts` cannot be installed there. Hence:

- **P1** runs on **Comfy Cloud, stock/Cloud-supported nodes only** (§0). Alignment runs outside the graph (§4).
- **Branch A** (this node pack: motion, effects, subtitles, encode — no models, no GPU dependency by construction) runs on **local ComfyUI** in P2. This is a consequence of the design, not a deployment condition: do not architect against a CPU-only constraint, simply avoid introducing GPU/model dependencies that the functionality doesn't need. Local installs may well have GPUs; use them opportunistically where it helps (e.g. OpenCV/torch-accelerated frame ops) without requiring them.
- **Branch B** (restoration / colourisation / img2vid, ethics-module teaching graphs) runs on **Comfy Cloud** with stock and Cloud-supported nodes (Wan, Flux, LTX class models are pre-installed there).
- **P3:** publish `comfyui-memoacts` to the ComfyUI Registry (see backlog) — the open-source route, and the only path by which Comfy Cloud might eventually support the pack ("expanded based on demand and compatibility"); not relied upon for September.

---

## 4. Input model

Media and text enter through loader nodes and widgets; the graph is the project. A saved workflow JSON + an assets folder *is* the project state, portable between participants.

**P1 prepared-inputs model.** Alignment cannot run on Comfy Cloud (no aligner node exists, stock or otherwise), so the PoC splits at `shots.json`:

```
[outside the graph]  narration.mp3 + script.md → stable-ts → shots.json
[Comfy Cloud graph]  shots.json + images + audio → reel
```

`shots.json` is uploaded as an input asset. This is acceptable and arguably good pedagogy: participants see the timing data explicitly as a file they can read and edit, rather than as a hidden step. For the intensive, `shots.json` can be produced by the facilitator for prepared exercises. In P2 it becomes a node (`nodes_align.py`).

Still recommended (not enforced) on-disk layout for tidiness:

```
projects/<name>/
  narration.mp3
  script.md          # + script.<lang>.md per language, block-matched
  images/            # stills, arbitrary formats — EXIF/CMYK/alpha handled
  video/             # optional footage fragments
  shots.json         # emitted by alignment, re-ingestible after hand edits
```

`script.md`: one shot per blank-line-separated block (unchanged from v1). A `mapping.csv` batch path from v1 remains supported in `memoacts_core` for power use, but the reference flow is GUI selection.

---

## 5. Workflow stages / node set

### 5.1 Alignment → editable shot table

**In:** narration audio + known script text. **Out:** shot table `{shot_id, text, t_start, t_end, media, motion, effects}` — in P1 a `shots.json` file produced outside the graph (§4); in P2 rendered as an editable node/panel.

We align *known text* to audio (forced alignment), which is precisely what produces the **timing**: the aligner returns start/end timestamps per sentence. We do not transcribe, so the observed CapCut error class — names, titles, dates rendered as «1е» or «семьдесят четвертый» instead of 1974 — cannot occur: the subtitle text is the script verbatim, only timestamps are computed.

- **Aligner (decided 2026-07-24, evaluation in `ALIGNERS.md`): stable-ts (`align()`) is primary** — it performs exactly our operation (known text + audio → timings) with no sequence-matching layer to write and maintain, and torch already ships with ComfyUI so the dependency increment is small. whisperx remains the accuracy benchmark; MMS_FA is dropped from the bake-off (see Armenian scope below); aeneas and MFA are rejected (see `ALIGNERS.md`).
- **The interface matters more than the engine.** Define the protocol first and build against it immediately; do **not** wait for the bake-off to start coding. Swapping engines must touch one file, never the node layer. The bake-off (stable-ts vs whisperx, RU + EN) runs **in parallel with** implementation, not before it.

  ```python
  # memoacts_core/align.py
  class Aligner(Protocol):
      def align(self, audio_path: Path, blocks: list[str], lang: str) -> list[Span]: ...
  # Span: {index: int, t_start: float, t_end: float, confidence: float, estimated: bool}
  ```

- **One language: English (v3.1).** Narration and script are English; there is exactly one alignment run and one subtitle track. Translation into RU / DE / HY happens outside this project (local DeepL + whisperX) and imposes no requirement here — no block-matched translation files, no per-language passes, no shot-boundary inheritance to maintain. Armenian alignment and rendering leave the plan entirely.
- **Normalisation before alignment (engine-independent).** Digits, dates and abbreviations must be expanded to spoken form before the text is handed to the aligner — "1974" → "nineteen seventy-four", "18" → "eighteen". The normalised text is used **for alignment only**; the verbatim script is what reaches the screen and the `.srt`/`.ass` files. Rationale: dates are the dominant error class in historical content, and unexpanded digits are where alignment drifts regardless of engine. **English makes this tractable** — `num2words` is sufficient, and the v3 open item about Russian case/number inflection is closed as not-applicable. Note that English years are read in pair form ("nineteen seventy-four", not "one thousand nine hundred seventy-four"), which `num2words` does not do by default — that is the one case worth handling explicitly. This pre-pass matters in P1 too: it runs wherever `shots.json` is generated.
- Alignment failure on a shot → proportional fallback + `timing: estimated` flag, never a failed run. Mis-normalisation degrades the same way.
- **Human-editable is a requirement, not a feature:** boundaries adjustable in the GUI (and in `shots.json` by hand); downstream nodes recompute on change.
- Separately, prepare `teaching_subs.json`: a showcase of existing ComfyUI subtitling workflows (ASR-based) for the curriculum — participants should see both approaches and understand when known-text alignment beats transcription and vice versa.

### 5.2 Shot assembly (the interactive heart)

Per shot, the creator chooses in the GUI:
- **Media:** one or more stills, or a video fragment. Multiple stills split the shot duration evenly (v1 behaviour) unless manually timed.
- **Motion (stills):** preset — `static / zoom_in / zoom_out / pan_lr / pan_rl / pan_ud / pan_du` + combinations; tunable rate and anchor (`center/top/face`); **live preview** of the shot before committing.
- **Video fragments:** in/out trim, speed (incl. slow-motion à la 0.4×), reframe 1280×800 or any aspect → 9:16 with anchor/pan control.
- **Effects:** per-shot toggles from the six families (below) or a named preset.

**Shot lead:** shot cuts lead the sentence onset by a configurable `shot_lead_ms` (suggested default 80–120 ms), exposed as a widget. An image appearing fractionally early reads as intentional; an image appearing late reads as a mistake. Cheaper than chasing the last milliseconds of aligner accuracy, and it gives the creator a control rather than a fixed behaviour.

Defaults must produce a decent reel with zero per-shot input (alternate motion direction, slow zoom ~4–8 % per shot), so the creator edits by exception, not by obligation — that is the CapCut time sink being removed.

**Resolution guard (unchanged from v1, it addresses a real complaint):** compute pixels needed for the requested zoom; if the source can't supply them, warn and clamp by default (`warn|clamp|upscale`), never silently upscale — the reference creator distrusts upscale quality, correctly.

### 5.3 Motion rendering

Compute per-frame crop rects in Python (float precision, eased), render via PIL/OpenCV → pipe to ffmpeg. Do not rely on ffmpeg `zoompan` as primary path (integer-rounding jitter — verify on target build); keep it as `--fast` preview with supersampling. Internal canvas 2160×3840, downsample at encode.

### 5.4 Effect families (layer stack)

Composite order: base → grade (lut3d) → grain (blend, looping clip) → texture (blend, looping video) → frame (alpha PNG) → shake (parametric). All optional, all previewable.

The reference creator's "~20 effects that work" are six families: **grain** (9 observed variants), **frame**, **texture**, **grade**, **shake**, **sharpen**. Implement families with parameters; ship her observed effects as named presets. No GPU, no diffusion anywhere in this branch.

**Texture is a looping video, not an image** (observed: ~65 s clip at 0.4× stretched across the timeline, same clip every project). Support seamless loop/stretch to full duration. Generating a project-owned seamless texture is a ComfyUI task for the design track (backlog item, feeds `assets/textures/`).

### 5.5 Subtitles

`.ass` generation from the shot table; burn-in via ffmpeg libass; `.srt` sidecars. Style fully configurable; neutral default (the reference creator's exact style: resolved as not needed). Safe-zone margins per platform, configurable, with a `--safe-zone-overlay` debug view; verify current platform guidance before fixing defaults.

**Multilingual burn-in: out of scope (v3.1).** Translation is a separate task outside this workflow (local DeepL + whisperX). No `script.<lang>.md` block-matching, no N-pass burn-in. The unlimited-and-free property still holds against CapCut's 2-per-month quota — it just applies to one language.

Font: **Latin/English coverage only.** This is the one requirement `DrawText+`'s bundled Share Tech Mono already satisfies, which is why `GAPS.md` #1 stops being a blocker. Armenian shaping and the EN/DE/FR/RU/HY coverage research leave the backlog.

### 5.6 Audio

Narration passes through untouched — never re-encoded avoidably, never time-stretched. SFX layer: placement per shot or timestamp, gain, simple ducking.

**SFX sourcing (de-blockered per review):** two parallel paths, either suffices —
1. Curated CC0/PD library in `assets/sfx/` with a licence manifest;
2. **Generation in ComfyUI** with an open-weight audio model (e.g. Stable Audio Open class) — which is also on-message for the course: participants generate their own SFX with open tools instead of borrowing a proprietary library. Evaluate quality for the typical needs of this format (whooshes, paper, projector, ambience).

CapCut's built-in SFX remain unusable outside CapCut either way — that constraint stands, only its severity changed.

### 5.7 Encode

Unchanged from v1: MP4, H.264, 1080×1920, 30 fps, 12 Mbps, yuv420p, AAC 192k stereo, `+faststart`; per-platform profiles in config. No interpolation needed — motion renders natively at 30 fps.

---

## 6. Acceptance criteria

### 6.1 P1 — Cloud PoC (judged on reproducibility by a participant, not output polish)

1. A participant opens the shared workflow on Comfy Cloud, loads prepared assets (`shots.json`, images, `narration.mp3`) and produces a vertical MP4 with correctly timed image changes.
2. Images change on sentence boundaries; audio is intact and in sync.
3. At least one motion treatment (even a crude zoom) and one subtitle track are present — crude is acceptable, absent is not.
4. The whole run completes within a credit budget that scales to the cohort (measure one run, multiply, check against Sachkosten before opening it to participants).
5. Every compromise forced by stock nodes is written down in `GAPS.md` as it is hit — this file is the P2 backlog.

Deliberately **not** required in P1: the six effect families, multilingual burn-in, video fragments, resolution guard, per-shot GUI editing. These are P2.

### 6.2 P2 — production pack

Test project (**retargeted in v3.1**): a new **English** script + narration recording supplied by the project owner — awaited as of 2026-07-28. `projects/sidur` was a planning example, never a dev fixture, and is **not** used for development or acceptance; it stays in the repo as reference material only. Until the English project arrives, `projects/demo_en` (4 synthetic stills, 4 shots, 13.8 s) is the only working fixture — sufficient for pipeline mechanics, insufficient for acceptance. Second pass: the same English project + one video fragment (KAPFILM excerpt) to exercise mixed media.

1. Opening `reel_stills.json` in ComfyUI, loading the Sidur assets, and running with **zero per-shot edits** produces a playable 1080×1920 MP4 matching narration duration ±0.2 s.
2. Changing one shot's image and motion preset in the GUI and re-running re-renders **without touching any other shot's configuration**.
3. Shot boundaries editable in the GUI; an edited boundary propagates to subtitles and motion timing.
4. Subtitles contain zero errors in names/dates (known-text alignment) in RU; `--lang ru,en` yields identical visuals, different burn-ins, one visual render.
5. Mixed workflow: a video fragment trimmed, slowed, reframed to 9:16 sits between still-shots seamlessly.
6. No silent upscaling; resolution guard warns and clamps.
7. Motion shows no visible jitter at 100 % playback.
8. The Branch A graph runs on a plain local ComfyUI install with **no GPU-class or diffusion checkpoints**. The aligner's speech model is permitted — **no size ceiling**; select whatever the bake-off shows to be accurate enough, preferring the smaller model only where accuracy is equal. Presence of a GPU is neither required nor harmful.
9. A course participant who has completed the intro seminars can, following a one-page guide, produce a reel from prepared assets in one session.

**Benchmark:** reference creator spends ~10 h per 2.5-min reel. Collecting and verifying images and deciding image-to-sentence fit remain human — that is why the GUI exists. Keyframing, effect application, subtitle generation/correction and re-export cycles are what the workflow absorbs.

---

## 7. Dependencies

ComfyUI (target: current stable + Comfy Cloud constraints per §3); Python 3.11+; ffmpeg with libx264, lut3d, blend, libass, overlay. Core: numpy, Pillow/opencv, pyyaml. Aligner: **stable-ts** (+ Whisper model, auto-fetched; permitted per §6.2.8) behind the `Aligner` interface (§5.1). Keep the surface small where it costs nothing — but per §0, install weight never blocks a decision now; offline/portability constraints for the September workshop live in `HARDENING.md`.

---

## 8. Known pitfalls

Unchanged from v1, still valid: `zoompan` jitter (verify); colour shift on grade+grain stacking (LUT before grain, consistent colour space); texture loop seams; odd dimensions (H.264 evenness); mixed input formats (EXIF rotation, CMYK, alpha, HEIC); non-Latin subtitle rendering (Armenian!).
From v2: shot-table state sync between GUI edits and re-runs (cache invalidation per shot, not per graph); accidental GPU/model dependencies creeping into Branch A via adopted third-party nodes — check each adopted node's requirements in the survey.
New in v3: RU digit/date normalisation quality (§5.1) — the dominant drift source regardless of engine; behavioural differences between local ComfyUI and Comfy Cloud when iterating locally and validating on Cloud (§0) — log them in `HARDENING.md`.

---

## 9. Backlog (out of current scope, priority order)

1. **Provenance ledger** — `file → source → archive → date → provenance_type → verification_status` → on-screen attribution plate + Statement of Intervention seed (ethics module §6). Source captions already carry attributions unstructured.
2. **Seamless video texture generation** (ComfyUI + design task) — replaces the borrowed clip.
3. **Image-to-sentence suggestion** (CLIP similarity) — suggestion only, never automatic.
4. **Script extraction helper** for mixed-content source docs (post text + captions + script).
5. **Cover-frame export** for the designer; optionally a generation path — *open question: Ideogram is proprietary, which cuts against the project's open-source commitment; prefer an open-weight image model or keep covers with the designer.*
6. ~~**Font coverage research** (EN/DE/FR/RU/HY) — Armenian rendering verified before the intensive.~~ **Dropped in v3.1** — English only; Share Tech Mono covers it. Revive only if translation ever re-enters scope.
7. Branch B teaching graphs (restoration / colourisation / img2vid) — governed by the ethics module; never in a published reel without a disclosed intervention statement.
8. **Publish `comfyui-memoacts` to the ComfyUI Registry** (P3) — open-source commitment + the only route toward eventual Comfy Cloud support; after the pack stabilises, not before September.

*(Deferred portability/offline items — explicit local model path for `nodes_align.py`, USB model install for 16 participants on museum Wi-Fi, base-vs-small model question, Armenian narration alignment, local-vs-Cloud behaviour diffs — live in `HARDENING.md`, not here.)*

---

## 10. Open items

- [x] Subtitle error taxonomy — **answered:** names, titles, dates («1е», «семьдесят четвертый» instead of 1974); overall recognition good. Consequence: known-text alignment eliminates the class entirely; keep a glossary only for Branch B ASR showcases.
- [x] Aligner selection — **resolved 2026-07-24:** stable-ts primary behind `Aligner` interface; bake-off vs whisperx (RU+EN) runs in parallel with implementation (§5.1, `ALIGNERS.md`).
- [x] Acceptance §6.8 "no model downloads" — **resolved:** amended to "no GPU-class/diffusion checkpoints"; aligner speech model permitted, no size ceiling (§6.2.8).
- [x] NC licences — **resolved:** tolerable for demos and fallbacks, never on a production critical path (§2.5).
- [x] PoC target — **resolved:** option (b), Comfy Cloud stock-node graph; sequencing per §0.
- [x] Comfy Cloud custom-node feasibility — resolved 2026-07-24: curated list only, arbitrary packs not installable. Deployment split per §3. Cloud-coverage survey per function: `SURVEY.md` (gating deliverable for P1 scope, §3).
- [ ] SFX — resolved as dual-path (§5.6); procurement/generation evaluation before the intensive.
- [ ] Safe-zone values — verify current Reels/TikTok/Shorts UI overlay guidance before fixing defaults. *(Context: platform UIs draw buttons/captions over the bottom and right edges of the video; subtitles must sit inside the uncovered region.)*
- [x] RU text normalisation (inflected number expansion) — **closed in v3.1 as not-applicable.** English only; `num2words` suffices, with year-pair reading ("nineteen seventy-four") as the one explicit case (§5.1).
- [ ] KAPFILM footage — in scope via mixed workflow (§2.3, §5.2), P2; no separate pipeline decision needed.
- [x] **Who is P2 for?** — **resolved 2026-07-28.** The curriculum has two parts (§0): August online (30 students, Cloud, overview) and September offline (16 students, local on two rented machines, practical). The pack reaches students in Part 2, so it is **not** production-only and no third "grow capability within stock Cloud nodes" track is needed. `GAPS.md` remains the P2 backlog for the pack; the Cloud ceiling binds Part 1 only, where an overview-level feature set is appropriate.
- [x] **Does the September offline workshop still exist?** — **resolved 2026-07-28: yes**, and the provisioning problem is far smaller than assumed. Not sixteen unknown personal machines but **two rented, project-controlled machines**. `HARDENING.md` rewritten accordingly; the USB-distribution and unknown-hardware-audit items are retired as solving a non-problem, replaced by a two-machine provisioning checklist.
- [ ] English narration + script for the retargeted test project (§6.2) — awaited from the project owner; P2 acceptance cannot be evaluated until it exists.
- [ ] **Does the September workshop use the pack, or stock local ComfyUI?** Newly relevant: "16 students try local ComfyUI" could mean either. It sets P2's deadline. If the workshop teaches the pack, P2 must be workshop-ready by September — roughly six weeks, with P1 not yet finished — and gains an acceptance criterion it does not currently have (usable by a workshop participant, not just by the production operator, §6.2.9 covers only the latter). If it teaches stock local ComfyUI (local-vs-Cloud contrast, no custom nodes), P2 keeps its natural October–November timeline alongside the video series. **Decide before committing P2 scope.**
- [ ] **Rented-machine specification** — a September deliverable with a hard lead time (the machines must be chosen and booked). Input exists: `GAPS.md` #2's ~11.5 GiB per 240-frame shot at source resolution, which scales with *source* image resolution rather than output. Derive RAM/CPU/disk from the intended workshop project size before booking, and note that per §6.2.8 no GPU is required by construction — a GPU is opportunistic, not a rental requirement.
