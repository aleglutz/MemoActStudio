# Work plan — reel dynamics and legibility

Written 2026-08-10 after the first full render of `legends_of_surrender`.
Supersedes the "next task" list in `HANDOFF.md`.

Five things came out of watching it: subtitles are unreadable and too long,
there is no way to add, drop or reorder a shot, the reel is static, the maps
should animate, and the stacked frames should move. Ordered below by what
unblocks the most for the least, not by the order they were raised.

Effort is in working days on this machine, and assumes nothing else is running.

---

## A. Subtitles — legibility (≈1 day total)

### A1. Semi-transparent plate — DONE

`BorderStyle: 3` (opaque box) instead of `1` (outline + shadow), filled with an
alpha-carrying colour. `SubStyle.plate_opacity` (default **0.55**),
`plate_colour`, `plate_pad`; exposed on `MemoActsSubtitles` and as
`render_reel.py --plate`. `plate_opacity=0` restores the old style exactly.

Three things worth remembering, all of which cost time to find:

- ASS alpha runs **backwards** — `00` is opaque, `FF` transparent. `_ass_colour`
  now takes an opacity in the human direction and inverts it.
- Under `BorderStyle: 3` the `Outline` field stops being a stroke width and
  becomes the **box's padding**; `plate_pad` feeds it.
- Renderers disagree about whether the box is filled from `OutlineColour` or
  `BackColour`, so both are set to the plate colour.

Calibrated against the reel's worst frame — shot 10, the signed instrument,
whose caption band averages **236/255**. At 0.55 the caption is legible there
and the plate stays unobtrusive over the dark shots (shot 6 averages 25).

One cosmetic artefact remains: the box is drawn **per line**, so a two-line
caption gets two boxes of different widths and reads as ragged. **A2 removes it**
by making a caption one line — which is why it is worth doing next rather than
chasing a full-width band here.

### A2. One line, larger — DONE

Font 44 → **56**, and each block is cut into captions that fit on one line at
the aligner's word timings. 18 blocks became 79 captions, median 1.9 s.

**One line is a correctness requirement, not a preference.** The plate is drawn
per line, so stacked lines stack their plates, and where two semi-transparent
plates overlap the alpha composites twice: measured L=60 against L=116 for a
single plate, a 20 px bar exactly `2 × plate_pad` tall, straight through the
text. So the fix for "no wall of text" and the fix for the dark bar are one fix.

Guaranteed rather than tuned: `memoacts_core.caption` measures with the same
font file libass burns in and packs to a pixel budget, so nothing wraps at any
size (checked at 50/56/62/68). `subs.check_wrap()` reports any caption that
would, and `render_reel.py` prints it as a defect.

Sentences are cut first, then over-long ones split evenly. Greedy packing alone
produced `May. Two dates for the end of` — one caption carrying two thoughts.

### ~~A2 as originally planned~~ — the reasoning, kept

The request is "no more than two lines, ideally one, bigger". That cannot be
done by setting a font size. The longest block in this script is **32 words /
175 characters**, which is about five lines at the current 44 px and more at any
larger size. One line per caption means **one caption is no longer one script
block** — the block has to be split into several short cues, timed within itself.

The timing for that already exists and is being thrown away. `StableTsAligner`
computes **word-level** start and end times and then collapses them to block
boundaries. Keeping them lets a block be cut into cues at real word times rather
than by guessing proportionally.

Work: retain word timings through `Span`, add a segmenter that packs words into
cues under a character budget (breaking at punctuation first, then at the last
space), emit those as the `.ass` events. Bigger font, `margin_v` retuned.

**This also feeds B**, which is why it comes before the editing work.

---

## B. Add, drop and reorder shots (≈1–2 days)

### The actual problem

Today one narration block is exactly one visual shot. A 14-second block gets one
still. That is the root of "not enough dynamics" — the cut cannot move faster
than the writing.

### What to build — not a timeline, yet

Let `shots.csv` carry **more than one row per block**, each with its own start
offset inside the block:

    shot,at,media,in,motion,rate,anchor,effects,notes
    1:35,0.0,Moscow.jpg,,pan_rl,0,,,
    1:35,4.5,map_russia.png,,zoom_in,0.04,,,flags appear
    1:35,9.0,S18_three-cities_bw.png,,static,,,,

`at` is seconds from the block's own start. Rows without it keep today's
behaviour, so nothing existing breaks. Dropping a shot is deleting a row;
reordering is moving one; adding is a new row. Word-level timings from A2 make
`at` snap to a word boundary rather than landing mid-syllable.

This gives the editing control immediately, in a file that diffs and reviews.

### The timeline strip — deferred, deliberately

A drag-and-drop timeline inside ComfyUI is a custom node with a JavaScript
frontend, canvas interaction, and its own state model — a week at least, and its
own maintenance. It is worth building **after** the data model above exists,
because the strip would be a view onto exactly that table. Building the view
first would mean designing the model through a GUI, which is the expensive
order.

Recorded as a P3 candidate, not September scope.

---

## C. Dynamics

### C1. Animated maps — flags arriving one by one (≈1 day)

`render_map.py` already composites a full frame per call, so animation is a loop
with a per-country alpha ramp: each flag fades in at its own offset, eased, over
a shot-length sequence. Output a frame sequence or an mp4 that `shots.csv`
references like any other clip.

Cheap because the hard part — geometry, relief, flag clipping — is done.

### C2. Stacked frames that move (≈0.5 day)

Two blockers, both known:

- A composite is built at exactly 1080×1920, so `max_zoom` is 1.00 and it cannot
  move at all. **Fix: build composites at 2160×3840** — change the target size in
  `threeband_9x16_api.json` and the band heights with it. Then the existing
  motion system works on them unchanged.
- More interesting than moving the whole frame: move the **bands
  independently**. The original storyboard asked for exactly this — *"the two
  halves slowly diverge upwards and downwards"*. That needs the renderer to
  composite bands per frame rather than consume a flat PNG, which is a real
  change to `render.py` and closer to 1.5 days.

Start with the oversized composite; decide on independent bands after seeing it.

### C3. Video fragments (≈1–1.5 days) — a scope decision, not just work

`nodes_video.py` is marked **"Won't"** for September in SPEC §0. The reel needs
it: `MBK_KAPFILM_FINAL.mp4` is the only moving footage, and at 1280×800 it fits
a 636 band at 0.84× with no enlargement — it is the one asset that is *better*
in the stacked layout than full-frame.

`shots.csv` already parses the `in` timecode and the renderer already refuses
footage with an explicit message. What is missing is a streaming frame source,
and the pattern exists — `effects.TextureSource` already streams and loops a
clip through an ffmpeg pipe.

Design decision from earlier, still open for confirmation: **the in-point is
editorial, the out-point is computed from the shot's duration.** Fragment length
then follows the edit automatically and cannot drift when the narration is
re-recorded.

---

## Recommended order

1. ~~**A1** — subtitle plate.~~ Done.
2. ~~**A2** — word-timed segmentation, bigger single-line captions.~~ Done.
3. **B** — multiple shots per block. Editing control, and dynamics for free.
4. **C2** — oversized composites so stacked frames can move.
5. **C1** — animated maps.
6. **C3** — video fragments, once the scope call is made.

A1 through B is roughly three days and addresses legibility, editing and most
of the pacing. C is another two to three.

## What this costs September

The September workshop teaches the pack, and the must-have set is already
complete and verified. Everything above is **beyond** that set. A2, B and C3 all
touch `memoacts_core`, which is what the workshop teaches — so they improve the
thing being taught rather than diverting from it, but they are still new code
that has to be legible and working by then.

The one genuinely new commitment is **C3**, which reverses a documented "Won't".
Worth making deliberately rather than by drift.

Unchanged and still outstanding: the seminar-scale Cloud concurrency test and a
facilitator recovery procedure (`GAPS.md`), the rented-machine specification
(`HARDENING.md`), and the Olm-DragCrop redistribution licence question
(`SURVEY.md §3`), which blocks imaging the workshop machines.
