# HANDOFF — session state as of 2026-07-28 (evening; supersedes the morning version)

Read `CLAUDE.md` and `SPEC.md` first as always — **SPEC is now v3.1 and its
changelog is the most important thing in this file's vicinity.** This file is the
delta: where the last session stopped and what the next one does first.

## What changed today

**1. First Comfy Cloud validation run — PASSED** (commit `16634f7`).

`shot_01_c1`, 36 frames, prompt `1cd9ef5f-e7bd-422e-be3c-27450af063e7`. Both
hypothesised failure modes came back **negative**, so neither `P1_GRAPH` fallback
is needed:

- 36 frames out, not 1 → Cloud honours the **list domain**; the `GAPS.md` #3
  workaround transfers intact.
- All 36 frames unique (framemd5) with visible zoom → the **list-map broadcast**
  transfers; coarse-step motion not needed.
- Output 1080×1920 / 30 fps / 1.200 s / h264-yuv420p, EN burn-in correct.
- Cost: **20.724 s** execution window, 0.542 s/frame, 2.709 s queue wait.

Two Cloud-only gaps found and recorded — `GAPS.md` **#4** (uploads are
content-addressed: `/api/upload/image` ignores the filename and stores under the
SHA-256 digest, so exported graphs are **not submittable unchanged**) and **#5**
(Cloud zeroes resource telemetry — peak RAM is unmeasurable there; only
`GET /api/jobs/{prompt_id}` gives timing).

**2. Roadmap corrected by the project owner → SPEC v3.1.** Three decisions:

- **English only.** Translation (RU/DE/HY) leaves project scope entirely — done
  separately with local DeepL + whisperX. Knock-ons applied across the repo:
  `GAPS.md` #1 withdrawn (Latin-only font stops being a blocker and becomes the
  intended path); SPEC §2.4 "languages are passes" withdrawn; §5.5 multilingual
  out; RU number-inflection open item closed; `ALIGNERS.md` rescoped to EN
  (stable-ts now very likely sufficient, bake-off demoted to confirmation,
  MMS_FA dropped); `HARDENING.md` Armenian items dropped.
- **`projects/sidur` is not a dev fixture** — it was a planning example. A new
  **English** script + narration is awaited from the project owner; acceptance
  §6.2 retargets to it. `projects/demo_en` is the only working fixture meanwhile.
- **Students run on Comfy Cloud, permanently** — no dependence on personal
  hardware. This voided most of `HARDENING.md` (USB model distribution,
  participant install audit) and raised a live architectural question, below.

## Curriculum structure (clarified 2026-07-28) — closed two open questions

| | **Part 1 — August online** | **Part 2 — September offline** |
|---|---|---|
| Students | 30 | 16 (subset of the same 30) |
| Format | 8 lessons, overview | Hands-on, practical/production |
| Environment | **Comfy Cloud** | **Local ComfyUI, two rented machines** |

- **"Who is P2 for?" — resolved.** The pack reaches students in September on the
  rented machines, so it is not production-only and no "grow capability within
  stock Cloud nodes" track is needed. The Cloud ceiling binds Part 1 only, where
  an overview-level feature set is appropriate rather than a compromise.
- **"Does the September workshop exist?" — resolved: yes**, and much smaller than
  feared: two project-controlled machines, provisioned once and cloned, not
  sixteen unknown personal ones. `HARDENING.md` rewritten around that.

- **"Does September teach the pack?" — resolved 2026-07-28: YES.** P2 therefore
  has a **hard September deadline** (~6 weeks, P1 unfinished). SPEC §0's
  "P1 has weeks, P2 has months" was corrected — both have weeks. Practical
  consequence for the next sessions: **finish P1, do not polish it.** New
  acceptance criteria §6.2.10–12 (workshop installability, rotation-slot
  latency, legible failure). Stretch goal (students build their own tooling
  from the pack as an example) is a *golden achievement, never a requirement* —
  its only cost now is writing the pack legibly from the first commit.
- **Not as alarming as the dates look:** much of `memoacts_core` already exists
  in script form and was deliberately built as its seed —
  `tools/generate_shots.py` (alignment, normalisation, shot table, crop maths,
  resolution guard), `tools/run_p1_local.py` (shot-assembly chain),
  `tools/assemble_reel.py` (concat + mux). September is substantially *wrapping
  proven logic in V3 nodes*. And `GAPS.md` #2/#3 already dictate the two
  rewrites (frame-streaming motion engine, libass burn-in) — not open questions.

**Earliest hard deadline in the project:** the rented machines must be *specified
and booked* before they can be provisioned. `GAPS.md` #2 (~11.5 GiB per 240-frame
shot, scaling with source resolution) is the sizing input; no GPU is required by
construction (SPEC §6.2.8).

## P2 progress (started 2026-07-28)

The core library now covers every must-have module's logic; only the ComfyUI
node layer is missing.

| Module | State |
|---|---|
| `memoacts_core/align.py`, `normalize.py`, `project.py`, `schedule.py` | pre-existing (P1 generator) |
| `memoacts_core/render.py` | **new** — frame-streaming motion engine, GAPS #2 |
| `memoacts_core/subs.py` | **new** — `.ass`/`.srt`, GAPS #3 resolved |
| `tools/render_reel.py` | **new** — whole pipeline downstream of alignment, one pass |
| `assets/fonts/` | **new** — Share Tech Mono + OFL, no longer depends on essentials |
| `memoacts_core/effects.py` | **new** — six effect families, SPEC §5.4 |
| `__init__.py` + `nodes_*.py` | **new** — 14 V3 nodes, smoke-tested headlessly |

Measured on demo_en (415 frames, 13.833 s, drift +1 ms vs narration):

- **0.98 GiB peak RAM** (python + ffmpeg) vs P1's ~11.5 GiB per 240-frame shot.
  Chunking and the external concat step are both gone.
- **25 s render, 61 ms/frame.** CPU-bound — this, not RAM, is what sizes the
  rented machines.
- **Subtitles free**: 23.0 s with libass vs 23.1 s without, against P1's
  139 s vs 54 s (~2.6×). Cost is per cue now, not per frame.

Two defects found and fixed while building, both live in P1 output:
`normalize.py` read years as cardinals ("one thousand, nine hundred and
seventy-four" for 1974) against a narrator saying "nineteen seventy-four"; and
the resolution guard clamped the zoom *rate* but let a too-small source be
enlarged silently (demo_en's 800×1000 → 1.92×), violating a non-negotiable.
`render.py` now enforces `on_upscale = warn|error|allow`.

### Node layer

Six V3 nodes, written against the skill reference at
`~/.claude/plugins/marketplaces/comfyui-custom-node-skills/plugins/comfyui-custom-nodes/skills/`.
Read those files directly: enabling the plugin does **not** load its skills into
a session that was already running — same registry-at-startup behaviour as the
MCP tools.

    Align Shots ─→ Set Motion ─→ Subtitles ─→ Render Reel
                        └──────→ Shot Report

Verified headlessly against a `comfy_api` stub: all six register with unique ids
and correct socket types, the full graph runs on `demo_en`, a motion override
touches only the targeted shot, and the render matches the CLI path exactly
(415 frames / 13.833 s / +1 ms drift). Errors are legible `ValueError`s naming
the problem — acceptance criterion §6.2.12.

**✅ Verified in ComfyUI itself, 2026-07-28.** Branch merged to `main`
(fast-forward), server started, pack imported in 0.4 s with no error — the other
import failures in the log (`comfy_kitchen`, `comfy_angle`, `brushnet`,
transformers/diffusers) are pre-existing and belong to other packs.

- `/object_info`: **all 14 nodes registered**, correct categories
  (`memoacts`, `memoacts/effects`), correct socket types and optional inputs.
- A full graph executed through `/prompt` in **42 s**: align (real stable-ts,
  conf 0.75–0.97) → set motion → effect preset → grade override → apply to
  shot 1 only → subtitles → shot report → render.
- Output `servertest_00001.mp4`: 415 frames, 13.833 s, 1080×1920, AAC,
  4.75 Mbps. Shot 1 desaturated and grained, shot 2 untouched — per-shot
  "edit by exception" confirmed end to end on the real server.

The local ComfyUI server was left **running** on 127.0.0.1:8188.

## P1 is CLOSED (2026-07-28)

Closed by decision without completing the full Cloud reel. Status against the
five acceptance criteria — two met only in qualified form — is in SPEC §6.1.
Short version: the mechanism is proven on Cloud and the cost is measured, but a
**per-job execution time limit** was found (`GAPS.md`), the full-set run failed
6/8, and finishing it would re-confirm known behaviour while spending credits.
The local P2 renderer makes the same reel in 25 s for free.

Corrected on close so the artifacts are runnable: `--max-chunk` 60 → 30,
`demo_en` shot table + cloud graphs regenerated (16 chunks, worst case 16.3 s
estimated), facilitator recipe warned about both the time limit and the hashed
upload filenames.

**Carried forward, not dropped:** a seminar-scale concurrency test before any
Cloud teaching session, and a facilitator recovery procedure for the
unattributable `ServiceError`. Both are August-intensive blockers, not P2 work.

## Next task

1. **First run on the real English project** — script + narration awaited from
   the project owner (expected 2026-07-29). This is the first evaluation of
   SPEC §6.2 criteria 1–9, which `demo_en` cannot exercise: four synthetic
   stills and 13.8 s prove mechanics, not acceptance.
3. **Calibrate the effect presets** against the reference creator's actual
   reels. The shipped values are placeholders chosen on synthetic images, which
   exaggerate grain badly (SPEC §5.4).
4. **Decide the workshop's effect budget.** Effects triple to quadruple render
   time; a heavy preset puts a 2.5-min reel at ~17 min, which does not fit a
   rotation slot at ~8 students per machine (SPEC §6.2.11).

Also open, unchanged: the seminar-scale Cloud concurrency test and a facilitator
recovery procedure (both August blockers, see P1 above), and the English script
+ narration for the retargeted test project (§6.2).

- The 4 images are **already uploaded**; digests are in the run log of the
  2026-07-28 session (re-upload is cheap and idempotent with `overwrite=true`).
- **8 remaining graphs still need the #4 digest rewrite** before submission —
  `projects/demo_en/cloud_graphs/*.json` reference bare filenames and will fail.
  Worth teaching `run_p1_local.py --export-all` to emit a `cloud_name` field, or
  adding a small patch step to the submission path.
- Current projection, **unconfirmed**: ~225 s of graph execution for 415 frames
  plus ~9× per-chunk overhead ≈ 4–4.5 min billable. Extrapolated from one
  36-frame sample (the *smallest* chunk) — do not feed it into the cohort budget
  before the real run.
- `docs/PARTICIPANT_GRAPH_RECIPE.md` needs a fix for #4 — a facilitator uploading
  via the Cloud UI gets a hash they must paste into every `LoadImage`.

Then: the new English project, once its script + narration arrive.

## Local environment notes

- The local ComfyUI server is **down** (background process exited, code 58).
  Restart before any local runs, from
  `C:\Users\Aleg\beehAIve\ComfyUI-Easy-Install\ComfyUI-Easy-Install`:
  `.\python_embeded\python.exe -I ComfyUI\main.py --windows-standalone-build`
  → serves on 127.0.0.1:8188; check with GET /system_stats.
- Not needed for Cloud work: `--export-all` runs offline, and submission goes
  through the `comfy-cloud` MCP.
- Hand-added locally (not in a lockfile anywhere): `ComfyUI_essentials` cloned
  into custom_nodes (heavy requirements deliberately NOT installed);
  `stable-ts` + `num2words` in the **embedded** python.
- `comfy-cloud` MCP is authenticated and working. It is a CLI-added **local
  scope** server → appears in Claude Code's `/mcp` panel, never in claude.ai
  connector settings. The session that authenticates it has no
  `mcp__comfy-cloud__*` tools; the registry is fixed at startup, so a fresh
  session is required after authenticating.

## Deferred validations (documented, not tasks)

- ~~RU alignment quality on real Sidur narration~~ — dropped with v3.1.
- ~~Armenian rendering via the PNG-strip path~~ — dropped with v3.1.
- EN aligner confirmation run on the new narration, once it arrives
  (`ALIGNERS.md` bake-off protocol, now a confirmation rather than a selection).
