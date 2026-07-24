# CLAUDE.md — MemoActStudio

Persistent context for Claude Code. Read this first, every session.

## What this project is

A ComfyUI-based production workflow replicating the subset of CapCut functionality used in historical vertical video production, for the MemoActs 2026 project (video series "How do wars end?" + online intensive curriculum).

**Authoritative spec: `SPEC.md`.** Read it before any task. If a patch or addendum file exists in the repo root that has not yet been merged into `SPEC.md`, say so and offer to merge rather than working from two sources.

## Current phase

**P1 — Cloud PoC.** Assemble a working reel graph on Comfy Cloud from stock / Cloud-supported nodes only. Reduced functionality is expected and acceptable. Deadline: demonstrable at seminar 4–5 of the running online intensive.

Not P1: the custom node pack, six effect families, multilingual burn-in, video fragments, per-shot GUI editing. Those are P2, scoped by `GAPS.md`.

## Priority principle

**A working end-to-end PoC beats portability.** Install weight, model size and offline-install concerns never block an implementation decision now — note them in `HARDENING.md` and move on. Offline deployment is a September task.

## Environment

- ComfyUI (Easy-Install), Windows.
- **Python is embedded.** Install packages into it, never into a system Python:
  `C:\Users\Aleg\beehAIve\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe -m pip install <pkg>`
- This repo lives under `ComfyUI\custom_nodes\MemoActStudio` so ComfyUI loads it directly.
- Comfy Cloud: curated custom-node list only — **our own pack cannot be installed there.** That is why P1 uses stock nodes.
- MCP: local ComfyUI MCP for the dev loop; official Comfy Cloud MCP (`cloud.comfy.org/mcp`, OAuth) for cloud graphs.
- Claude Code skills: `jtydhr88/comfyui-custom-node-skills` plugin installed. Use it for any node work; write against the **V3 API** (`io.ComfyNode`, `io.Schema`, `io.NodeOutput`), never V1.

## Working method

- **The spec is not authoritative on verifiable facts.** Anything marked "verify" or "evaluate" is a hypothesis to test. Surfacing a contradiction is a deliverable, not a delay — v1 of the spec recommended `aeneas`, which the survey correctly killed.
- Present findings and decision points for review **before** writing implementation code on anything architectural.
- Use plan mode for multi-step work. Commit at each working checkpoint.
- One clarifying question at a time.

## File map

| File | Role |
|---|---|
| `SPEC.md` | Authoritative specification |
| `SURVEY.md` | Existing-node survey + Comfy Cloud coverage, adopt/wrap/build decisions |
| `ALIGNERS.md` | Aligner evaluation. Decided: stable-ts primary, behind an `Aligner` interface |
| `GAPS.md` | Every compromise forced by stock nodes in P1 — this is the P2 backlog |
| `HARDENING.md` | Deferred portability/offline items for September |
| `projects/sidur/` | Reference test project (RU narration, ~18 shots, archival stills) |

## Non-negotiables

- **Open source end to end** on anything production-critical — the grant (Auswärtiges Amt, Zuwendungsbescheid) commits the project to open-source AI tools. Non-commercial-licensed components are tolerable for demos and fallbacks only, and every adopted component's licence goes in `SURVEY.md`.
- **Subtitles are never transcribed.** The script is ground truth; alignment computes timings only. Verbatim script text reaches the screen.
- **Never silently upscale** an image beyond its native resolution.
- **Narration audio passes through untouched** — never re-encoded avoidably, never time-stretched.
- Cloud runs cost credits per GPU-second. Iterate locally, validate on Cloud.
