# Archive

Superseded documents, kept because they record *why* a decision was made rather
than what the current state is. Nothing here is authoritative and nothing here
is maintained. For the current state read `SPEC.md`, then `CLAUDE.md`.

**Paths inside these files are as they were on the day of archival.** They are
not rewritten when the repository moves things, because a historical record that
gets edited to stay tidy stops being a record. Read a broken link as "this was
here then".

## `spec/` — superseded specification layers

| File | Superseded by |
|---|---|
| `20260724_SPEC_v2.1_Patch.md` | merged into `SPEC.md` v3 |
| `20260724_SPEC_v2.1_Addendum_PoC_Target.md` | merged into `SPEC.md` v3 (§0, §3) |

`SPEC.md` is v3.1 and its header points here for the originals.

## `handoffs/` — session-state notes, expired by construction

A handoff describes where one session stopped. It is stale the moment the next
session starts; these are kept for the reasoning they carry, not the next steps.

| File | Superseded by |
|---|---|
| `20260728_HANDOFF.md` | `docs/PLAN.md`, which says so in its own header; scope decisions merged into `SPEC.md` v3.1 |
| `20260805_HANDOFF_comfy_threeband.md` | `docs/THREEBAND_TOOL.md`, which answers it. Still cited live by `SURVEY.md` for its §7 fallback (writing our own crop node, should the Olm-DragCrop licence block redistribution) |

## Superseded plans

| File | Superseded by |
|---|---|
| `20260810_PLAN.md` | `docs/PLAN.md` (2026-08-21). Finished rather than abandoned — subtitles, `shots.csv`, animated maps and moving bands all landed; the project owner confirmed it complete on 2026-08-20. Kept for the reasoning in its A2 section, which records *why* one caption is one line, and for the deferred-timeline argument in B |

## Loose reference

| File | What it is |
|---|---|
| `script-framework.pdf` | Storyboard-format reference, added 2026-08-05 alongside the script parser that learned to read it. **On disk, not in the repository:** nobody wrote down who made it, and an unattributed document does not go into a public repo. Restore it to git the day its provenance is known |

## Where the other archives are

Project-scoped history stays with its project rather than here —
`projects/legends_of_surrender/archive/` holds earlier cuts of that reel's
script. This directory is for repository-wide documents.
