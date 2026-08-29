# sources/sfx — what is heard under the voice

One `.wav` per row of `../../sfx.csv`. The recordings themselves are not
versioned, like everything else under `sources/`; this file is here so the
folder is, and so the next person knows what belongs in it.

Two ways a file arrives, and by the time the mixer runs it cannot tell them
apart:

- **Generated.** `MemoActs — SFX Prompt` hands one row to a text-to-audio graph
  and `MemoActs — Save SFX` writes the take here under the name the row asked
  for, stamping that name and the seed back into `sfx.csv` so the take can be
  found again after a restart and made again after a year.
- **Found.** A CC0 recording dropped in by hand, named in the row's `file`
  column. Nothing else changes.

`MemoActs — SFX Bed` mixes whatever is here into one track the length of the
reel — placed, faded, and stepped back under the narration — and leaves it in
`generated/sfx_bed.wav`. The narration is only ever *read* by that step.

Full format and column reference: `docs/SOUND_DESIGN.md`.

## Status

Empty as of 2026-08-29. This project has no `sfx.csv` yet: run the Sound Design
node once and it writes a starter table, one commented row per shot, carrying
what that shot says.
