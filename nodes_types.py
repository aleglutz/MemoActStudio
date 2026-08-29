"""Shared custom socket types for the memoacts nodes.

Defined once here rather than per module so every node wires against the same
`io_type` string — two independently-created Custom types with the same name do
match, but a typo in one of them would only surface as a socket that silently
refuses to connect.

The five that carry the workflow read left to right, and each is one sentence
of it: a project, its timings, its shot table, how the captions look, and the
reel. Effects hang off the table.
"""
from __future__ import annotations

from comfy_api.latest import io

#: The project folder. Payload: {"project_dir": str}.
#:
#: Only the path travels, never the contents. Every step re-reads the folder,
#: which `memoacts_core.pipeline.read_project` does in milliseconds — so an
#: image dropped into `sources/images/` or a row changed in `shots.csv` is
#: picked up by the next run instead of hiding behind a cached payload.
Project = io.Custom("MEMOACTS_PROJECT")

#: Timings for the narration. Payload:
#:   {"alignment": memoacts_core.pipeline.Alignment, "project_dir": str}
#:
#: The one expensive thing in the workflow, and the reason it is its own socket:
#: it depends on the script and the recording and on nothing else, so editing
#: the shot table must not cost another pass over the audio.
Alignment = io.Custom("MEMOACTS_ALIGNMENT")

#: The shot table plus the project it came from. Payload:
#:   {"doc": <shots.json content, docs/SHOTS_SCHEMA.md>, "project_dir": str}
#: The project directory travels with the table because every downstream node
#: needs to resolve `sources/` relative to it.
Shots = io.Custom("MEMOACTS_SHOTS")

#: How the captions look — settings, not files. Payload is the caption fields
#: of `memoacts_core.pipeline.RenderOptions`.
#:
#: The track itself is written by the render, because the burn-in and the file
#: on disk must be the same pass; a node that wrote its own would be a second
#: writer, which is exactly how the pack drifted from the CLI before.
Subs = io.Custom("MEMOACTS_SUBS")

#: The sound design. Payload:
#:   {"project_dir": str, "doc": <shots.json>, "csv": str,
#:    "cues": [memoacts_core.sfx.Cue], "placed": [memoacts_core.sfx.Placed]}
#:
#: Both lists travel because they answer different questions: `cues` is what the
#: table *says*, in file order, which is what the generator walks; `placed` is
#: what it *means* against this shot table — when each sound starts, how long it
#: runs, and whether the recording exists yet — which is what the mixer needs.
SfxCues = io.Custom("MEMOACTS_SFX")

#: One row of it, on its way through a text-to-audio graph. Payload is `SfxCues`
#: plus {"cue": Cue, "seed": int, "seconds": float}.
#:
#: It exists so the generated audio comes back to the node that knows which row
#: asked for it. Without it the save step would need its own copy of the index,
#: and an index that is set in two places is an index that disagrees with itself.
SfxCue = io.Custom("MEMOACTS_SFX_CUE")

#: A `memoacts_core.effects.EffectStack`. Kept out of the shot table's `doc`
#: because `doc` stays plain JSON (docs/SHOTS_SCHEMA.md) — effect stacks travel
#: alongside it, in the payload's `effects` map keyed by shot id.
Effects = io.Custom("MEMOACTS_EFFECTS")
