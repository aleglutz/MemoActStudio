# CLAUDE.md — MemoActStudio

Persistent context for Claude Code. Read this first, every session.

## What this project is

A ComfyUI-based production workflow replicating the subset of CapCut functionality used in historical vertical video production, for the MemoActs 2026 project (video series "How do wars end?" + online intensive curriculum).

**Authoritative spec: `SPEC.md`.** Read it before any task. If a patch or addendum file exists in the repo root that has not yet been merged into `SPEC.md`, say so and offer to merge rather than working from two sources.

## Current phase

**P1 — Cloud PoC.** Assemble a working reel graph on Comfy Cloud from stock / Cloud-supported nodes only. Reduced functionality is expected and acceptable. Deadline: demonstrable at seminar 4–5 of the running online intensive.

Not P1: the custom node pack, six effect families, video fragments, per-shot GUI editing. Those are P2, scoped by `GAPS.md`.

**Scope corrections, SPEC v3.1 (2026-07-28) — read §changelog before planning:**
- **English only.** Translation (RU/DE/HY) is out of project scope — handled separately with local DeepL + whisperX. No multilingual burn-in, no Armenian, no RU normalisation.
- **`projects/sidur` is not a dev fixture.** A new English script + narration is awaited from the project owner; until then `projects/demo_en` is the only working fixture.
- **Two audiences, two environments** (SPEC §0): August online intensive — 30 students, 8 lessons, **Comfy Cloud**, overview-level; September offline workshop — 16 of those students, **local ComfyUI on two rented machines**, practical/production.
- **The September workshop teaches `comfyui-memoacts` itself.** So **P2 has a hard September deadline** — P1 and P2 both have weeks, not months. P1 must be *finished, not polished*: there is no longer slack in P2 to absorb P1 overrun. Module priority for the September cut is in SPEC §0; `nodes_layers.py` (six effect families) is the designated first cut.
- Stretch goal — teaching students to build their own tools from the pack as a worked example — is a **golden achievement, never a requirement**. Its only actionable consequence now: write the pack legibly from the first commit, since that is cheap early and expensive to retrofit. No separate teaching version, no tutorial content in scope.

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
| `HARDENING.md` | Deferred portability items (much reduced — students are on Cloud, not local) |
| `README.md` | The CLI path, cold start to rendered reel. Start here to *run* something |
| `HANDOFF.md` | Where the last session stopped and what the next one does first. Rewritten, not appended to; superseded versions go to `archive/handoffs/` |
| `docs/` | Working documents: `PLAN.md` (current task list), `P1_GRAPH.md` + `PARTICIPANT_GRAPH_RECIPE.md` (August intensive), `WORKSHOP_MACHINE_SETUP.md` (September), `SHOTS_SCHEMA.md`, `THREEBAND_TOOL.md`, `UPSCALE.md`, `EDITING.md` |
| `archive/` | Superseded documents, kept for their reasoning. Not authoritative, not maintained — see `archive/README.md` |
| `projects/legends_of_surrender/` | **The live project** — English reel "Signed After Midnight" for Museum Berlin-Karlshorst. Media is unversioned; `REBUILD.md` regenerates it |
| `projects/demo_en/` | Working fixture (4 shots, 13.8 s) — pipeline mechanics only. Its stills are unversioned but are on disk, in `sources/images/` |

## Project layout

Every project is four folders and three files, and the boundary is drawn by
*what the edit can point at*, not by who made the file:

```
projects/<name>/
  script.md     the text — ground truth
  shots.csv     the edit decision
  REBUILD.md    how every generated file is remade
  sources/      everything shots.csv may name: SOURCES.md, narration.wav,
                images/ videos/ composites/ maps/ — a plate the tool drew and
                a scan a person found are the same kind of thing to a shot
  generated/    the compiler's own output, shots.json + report.txt. Deletable
  out/          the finished reel
  archive/      superseded, kept for its reasoning. Nothing is deleted from it
```

`memoacts_core.project.MEDIA_DIRS` is the only place that names the search
order. Prose inside `sources/` and `archive/` stays in git; the media beside it
does not — see `.gitignore`, which ignores their *contents* rather than the
folders precisely so the `.md` files survive.

## Non-negotiables

- **Open source end to end** on anything production-critical — the grant (Auswärtiges Amt, Zuwendungsbescheid) commits the project to open-source AI tools. Non-commercial-licensed components are tolerable for demos and fallbacks only, and every adopted component's licence goes in `SURVEY.md`.
- **Subtitles are never transcribed.** The script is ground truth; alignment computes timings only. Verbatim script text reaches the screen. (This survives v3.1 unchanged — it is *why* the workflow beats CapCut's auto-subtitles, independent of language count.)
- **Never silently upscale** an image beyond its native resolution.
- **Narration audio passes through untouched** — never re-encoded avoidably, never time-stretched.
- Cloud runs cost credits per GPU-second. Iterate locally, validate on Cloud.
