"""memoacts_core — GUI-independent logic for the MemoActs reel workflow.

P1 role: the schedule generator (prepared-inputs model, SPEC §4).
P2 role: the library behind the comfyui-memoacts node pack.
"""

#: 1.1 adds the optional per-shot `words` array (word-level timings). Readers
#: written against 1.0 are unaffected; writers before 1.1 simply omit it.
#: 1.5 adds per-shot `effects`, the name of a preset from `effects.PRESETS`.
#: Additive the same way: `null` on every shot a 1.4 file carries, which is
#: what a shot with no look of its own means.
SCHEMA_VERSION = "1.5"
