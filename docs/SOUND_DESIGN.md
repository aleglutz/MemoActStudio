# Sound design — the last stage of the reel

**Written 2026-08-24.** Answers SPEC §5.6, which asked for an SFX layer and left
its sourcing open between a curated CC0 library and generation with an
open-weight model. This takes the second path *and* the first: by the time the
mixer runs there is only a wav on disk, and it never learns which it was.

Open `example_workflows/sound_design.json`. It is the five-node reel graph with
four more nodes on the end.

    Shot Table ─→ Sound Design ─→ SFX Prompt ─→ [ a text-to-audio graph ]
                       │                                   │
                       │                            Save SFX ─→ sources/sfx/
                       ↓
                    SFX Bed ─→ (audio) ─→ Render Reel

## The four nodes, one sentence each

| Node | The sentence |
|---|---|
| **Sound Design** | "This scene needs a sound." The table: one row per sound. |
| **SFX Prompt** | "One row, handed to the model." Prompt, seconds, seed. |
| **Save SFX** | "The take goes into the project, under the name its row asked for." |
| **SFX Bed** | "Every sound, placed and mixed under the voice." |

Only the first and the last are about the reel. The two in the middle exist to
walk one row at a time through whatever generates the audio — which is why the
generator sits between them rather than inside either: **swap the model and
nothing else in the graph moves.**

## `sfx.csv` — the third decision

The project already keeps *what is said* (`script.md`, ground truth) apart from
*what is seen* (`shots.csv`, the edit). Sound is the third, and it changes on
its own schedule, long after the words are fixed:

```csv
shot,at,dur,gain,fade,duck,loop,file,seed,prompt,notes
1,0,3,-16,0.1 0.8,8,,,,the pages of a large old book turning slowly,
0:41,-0.2,1.6,-9,0.01 0.9,10,,,,a heavy wooden door slams shut in a stone hallway,
3,0,2.5,-13,,9,,,,unhurried footsteps on a parquet floor in an empty hall,
,0:00,,-30,3 3,5,yes,room_tone.wav,,,ambience under the whole reel
```

| column | meaning |
|---|---|
| `shot` | which shot the sound belongs to — by **number**, or by the **cue timecode** written in the script. Cues survive a shot being inserted; numbers do not. Blank makes `at` an absolute position in the reel, which is what an ambience bed wants |
| `at` | where it starts relative to the shot, in seconds. **May be negative** — a door slam usually lands a beat *before* the cut it motivates |
| `dur` | how long it is: what gets generated, and what gets played. Blank = the shot's own length, capped at 47 s. A sound may outlast its shot; tails are not a mistake |
| `gain` | dB, and negative, because this layer sits under a voice. Default −14 |
| `fade` | `in out` in seconds; one number sets both. Default `0.02 0.25` |
| `duck` | how far this sound steps back **while the narrator is speaking**, in dB. Default 8. `0` turns it off for that row |
| `loop` | repeat a short file to fill `dur` — twelve seconds of room tone out of a three-second recording |
| `file` | the recording in `sources/sfx/`. Blank = derived from the row, and **Save SFX writes the name back here** |
| `seed` | written back too, so a take you liked can be made again |
| `prompt` | what the sound is, in words. The one column that is never optional |
| `notes` | yours |

A row starting with `#` is a comment. A project with no `sfx.csv` gets a starter
table on the first run — one commented row per shot, carrying what that shot
says — because a blank text box is not a format.

**Where the table lives.** In the file, and in the box on the Sound Design node,
with one rule: *the box wins when it holds anything*, and an empty box means
"read the file". The two buttons on the node move between them — **Load
sfx.csv** fills the box, **Clear** empties it and hands authority back to the
file.

## Generating the sounds

Set the **batch count** to the number of rows and queue once. `index` on SFX
Prompt is on `increment`, so one queued batch walks the whole table; `seed` is
on `randomize`, so a re-run is a fresh take rather than the same one again.

The model in the example workflow is **Stable Audio Open 1.0** with the
`t5_base` text encoder — 50 steps, cfg 5.0, `dpmpp_3m_sde_gpu` / `exponential`,
44.1 kHz stereo, up to 47 s. It was trained on sound libraries, which is exactly
the material a cue asks for and exactly why the default `style` says *single
sound effect, field recording, close mono source, dry, clean, no music, no
speech*: without those words the model reaches for music.

⚠ **Its licence is not OSI** (Stability AI Community License) — see the ledger in
`SURVEY.md`. Nothing in the pack depends on it: the checkpoint is named in a
stock loader node, and a row whose `file` names a CC0 recording plays exactly
like a generated one.

**Two things Save SFX does that matter more than they look.**

*It finds where the take actually starts.* A generated sound routinely opens with
a second of *almost* nothing — not digital silence, so an absolute threshold
never finds it, but the room the model imagined before the event. Measured
against the take's own peak instead (`head_db_below_peak`, default 20 dB), the
onset is where it sounds like it is. Measured on this machine: a page turn
generated at 3 s came back with the pages at **1.89 s**. Left alone it would have
landed most of two seconds after the cut it was written for.

*It normalises the peak* (`peak_dbfs`, default −1 dBFS), so `gain` in the table
means the same thing for every row and the numbers are comparable between
sounds.

## The mix, and the one thing it may not touch

**The narration passes through untouched.** That is a project non-negotiable
(SPEC §5.6) and here it is structural rather than careful: the bed is a separate
track, and the two are summed by ffmpeg at the mux —

```
[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]
```

`normalize=0` is the load-bearing part. `amix` divides every input by the number
of inputs by default, which would quietly drop the voice 6 dB the moment a sound
design existed. `duration=first` keeps the output as long as the narration, so a
tail running past the last word cannot lengthen the file.

Verified on `demo_en`, rendering the same reel twice, with and without the bed:
the difference between the two audio tracks equals the bed to within **−48
dBFS** — the AAC error floor, 25 dB below the bed itself — and the narration's
own level moved by 0.09 dB, which is the bed's energy adding to it. The voice
that reaches the mux is the recording.

**Ducking** is the only automatic move, and it only ever attenuates the sound
effects. The narration is opened read-only to answer one question — *is the
narrator speaking* — as a gate with a 30 ms attack and a 300 ms release rather
than a level follower, because a follower makes the sound effects breathe with
every syllable. Turn it off with `duck_under_voice` to hear the table's gains on
their own, which is how you judge them.

## The author's path

The terminal is not the teaching surface, but it is still the reference
implementation, and both doors call the same two functions
(`pipeline.read_sound_design`, `pipeline.build_sfx_bed`):

```bash
python tools/render_reel.py --project projects/<name> --sfx
python tools/render_reel.py --project projects/<name> --sfx --sfx-gain -3 --no-duck
```

`--sfx` builds `generated/sfx_bed.wav` from `sfx.csv` and mixes it in. Generating
the sounds has no CLI: that half is a graph, and it is the half the workshop
teaches.

## What is deliberately not here

- **No music.** A different problem with a different model (ACE-Step) and a
  different licence question. Sound effects sit under a voice; music competes
  with one.
- **No per-sound EQ, reverb or pitch.** `gain`, `fade`, `duck` and `loop` are
  what a reel of this length actually needs. Anything more is a DAW.
- **No automatic sound design.** Nothing looks at a shot and decides it should
  have footsteps. The prompt is the author's sentence about their own material,
  which is the same claim `script.md` makes about the words.
