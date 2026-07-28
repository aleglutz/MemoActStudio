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

**Still open, and it sets P2's deadline:** does September teach **the pack**, or
**stock local ComfyUI**? If the pack, P2 must be workshop-ready in ~6 weeks with
P1 unfinished, and needs an acceptance criterion it lacks today (usable by a
workshop participant, not just the production operator). If stock, P2 keeps its
October–November timeline. Asked, not yet answered — SPEC §10.

**Earliest hard deadline in the project:** the rented machines must be *specified
and booked* before they can be provisioned. `GAPS.md` #2 (~11.5 GiB per 240-frame
shot, scaling with source resolution) is the sizing input; no GPU is required by
construction (SPEC §6.2.8).

## Next task

**Full 9-chunk `demo_en` Cloud run** (P1_GRAPH verification step 5) — the credit
measurement that feeds SPEC §6.1.4.

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
