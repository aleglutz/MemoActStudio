"""Shared custom socket types for the memoacts nodes.

Defined once here rather than per module so every node wires against the same
`io_type` string — two independently-created Custom types with the same name do
match, but a typo in one of them would only surface as a socket that silently
refuses to connect.
"""
from __future__ import annotations

from comfy_api.latest import io

#: The shot table plus the project it came from. Payload:
#:   {"doc": <shots.json content, docs/SHOTS_SCHEMA.md>, "project_dir": str}
#: The project directory travels with the table because every downstream node
#: needs to resolve `images/` and `narration.*` relative to it.
Shots = io.Custom("MEMOACTS_SHOTS")

#: Generated subtitle track: {"ass": str, "srt": str, "cues": int}
Subs = io.Custom("MEMOACTS_SUBS")

#: A `memoacts_core.effects.EffectStack`. Kept out of the shot table's `doc`
#: because `doc` stays plain JSON (docs/SHOTS_SCHEMA.md) — effect stacks travel
#: alongside it, in the payload's `effects` map keyed by shot id.
Effects = io.Custom("MEMOACTS_EFFECTS")
