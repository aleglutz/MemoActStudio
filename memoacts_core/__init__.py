"""memoacts_core — GUI-independent logic for the MemoActs reel workflow.

P1 role: the schedule generator (prepared-inputs model, SPEC §4).
P2 role: the library behind the comfyui-memoacts node pack.
"""

#: 1.1 adds the optional per-shot `words` array (word-level timings). Readers
#: written against 1.0 are unaffected; writers before 1.1 simply omit it.
SCHEMA_VERSION = "1.3"
