# Rebuilding this project's generated media

Media is never versioned, and everything below is an *output*: it is rebuilt
from `sources/` plus `assets/geo/`, not copied between machines. A copied output
can silently disagree with the inputs it claims to come from, which is why the
commands live here rather than the files living in git.

Run from the repository root with the environment active (`README.md` §0).
Nothing here needs ComfyUI, torch or a GPU — only Pillow, numpy and ffmpeg.

## Map plates — palette `pencil` (SOURCES: sampled from the act scans)

Two moves on 2026-08-22. `ink` (signature blue-black sea) went to `sepia`, to
take the blue out of everything but the flag wash; `sepia`'s tea-stained water
then read badly against the land, so the water was resampled from the
archivist's **blue pencil "10"** in the corner of page 1 of the act — hue 200°,
carried down the pencil's own shade ramp to water depth. Land, coast, border
and flag wash are `sepia`'s, unchanged: that half already worked. The full
measurement is in the `pencil` entry in `tools/render_map.py`.

All three plates move together — a single plate left on an older palette is
visible against the other two.

`render_map.py` corrects Crimea and Sevastopol to Ukraine before drawing, and
refuses to render if the correction fails. It prints the check; the plates
committed here were rendered with `moved Russia part #100 -> Ukraine`.

    python tools/render_map.py --out projects/legends_of_surrender/sources/maps \
        --name map_baltics --frames 360 --palette pencil \
        --highlight Latvia Estonia Lithuania

    python tools/render_map.py --out projects/legends_of_surrender/sources/maps \
        --name map_poland_ukraine --frames 360 --palette pencil \
        --highlight Poland Ukraine --already Latvia Estonia Lithuania

    python tools/render_map.py --out projects/legends_of_surrender/sources/maps \
        --name map_france_reims --highlight France --context 1.5 --scale 2 \
        --palette pencil --marker "4.0317,49.2583,Reims"

`--scale 2` is what lets the 0:23 shot push in 2.5x without enlarging anything;
the tool prints the `focus` triple that `shots.csv` uses, so it is never
measured off the finished image by eye.

## Stacked frames

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S01-02_two-band --still \
        --band Reims-Signing.jpg:0.5 --band Karlshorst_Signing.jpg:0.5

    python tools/render_bands.py --project projects/legends_of_surrender \
        --name S18_three-cities_bw --still --mono \
        --band London.jpg:0.5 --band Berlin.jpg:0.5 --band Moscow.jpg:0.5

`S14_three-band.mp4` is **retired**: 1:32 now belongs to the page move below.
The command is kept in git history if the shot ever comes back.

## The act, read — 1:26 to 1:38

One clip, two shots: 1:26 reads it from 0, 1:32 from 5.420 s, the measured
length of the first shot.

### What the reference actually does

Measured off the reel frame by frame (phase correlation at 10 fps, cut
detection on correlation and frame difference), not described from memory:

| | |
|---|---|
| segments between cuts | 28 in 40 s — median **1.05 s** |
| of those | 24 moves, 4 holds; a hold is **0.8 s** median |
| speed while moving | median **374 px/s** at 720 wide, range 75–1241 |
| direction | horizontal dominates: 11 right, 6 left, 5 diagonal, 1 vertical |
| speed within a segment | *not* constant — it accelerates and settles |
| closeness | **27 text lines** fill the height in the wide beats, **10–11** in the close ones |

Two things follow that the earlier passes got wrong. The framing is a *reading*
framing — 27 lines, not a whole page — and it goes twice closer than that at
the close beats. And the movement eases: `--ease linear` was wrong, the sheet
arrives and settles rather than stopping dead.

### The path

Page 2 is not in the reel: one turn, page 1 to page 3. The scans differ (1024x1410
and 1860x2560), so `s` differs to hold one reading size — 2.60 and 1.43 both give
a sheet about 2660 px wide, 27 text lines in frame, the reference's own framing.
**Page 3 is at one scale for its whole section**, which is what removes the seam:
the camera reaches Keitel by travelling, never by getting closer.

Magnification is real — 2.6x on the klein scan — and deliberate: `UPSCALE.md`
forbids silent enlargement, not enlargement, and the factor is printed every run.
It is plain Lanczos, which invents nothing. When the scans are upscaled, divide
every `s` by the upscale factor; the framing does not move.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image GIoS_Wehrmacht_Signed_Ru_p1.jpg \
        --image GIoS_Wehrmacht_Signed_Ru.jpg \
        --name S12_ru_page_move --frames 377 --ease cosine \
        --key 0.000:0.500,0.950,2.60,1 --key 0.035:0.500,0.950,2.60 \
        --key 0.122:-0.231,0.950,2.60 --key 0.166:-0.231,0.950,2.60 \
        --key 0.279:1.231,0.863,2.60  --key 0.314:1.231,0.863,2.60 \
        --key 0.528:-0.066,0.204,1.43 --key 0.567:-0.066,0.204,1.43 \
        --key 0.672:0.796,0.309,1.43  --key 0.715:0.796,0.309,1.43 \
        --key 0.942:0.328,0.929,1.43  --key 1.000:0.328,0.929,1.43 \
        --turn 0.384,0.414,2

| time | | speed |
|---|---|---|
| 0.0–0.44 s | held on the head of page 1 | |
| 0.44–1.53 s | the sheet goes left | 725 px/s |
| 1.53–2.09 s | **held on the "10" in blue pencil**, top right | |
| 2.09–3.51 s | back right and down, a whip | 1 120 px/s |
| 3.51–3.95 s | **held on the tape and punch holes** at the left margin | |
| **3.95–6.64 s** | one long move down to de Lattre de Tassigny, bottom right — **the sheet turns over on the way**, at 4.83–5.20 s | 700 px/s |
| 6.64–7.13 s | held | |
| 7.13–8.45 s | left to Spaatz, bottom left | 720 px/s |
| 8.45–8.99 s | held | |
| 8.99–11.84 s | the long rise to Keitel's autograph | 455 px/s |
| 11.84–12.57 s | held on it | |

**The turn has no keys of its own, and that is the point.** It used to need a
pair — one to end page 1's scale, one to start page 3's — and under
`--ease cosine` a key is a full stop. So the sheet arrived at mid-page, where
there is nothing to look at, settled, turned, and started again from rest: two
placements around one page, which is not what a hand does. `render_move` takes
each sheet's scale from that sheet's own keys now (`scale_at`), so a page change
is a cut in scale and needs no key to pin it. The turn happens inside a single
move, and the sheet never stops between the tape and the signature. Measured on
the render, frame to frame: 0 px through the twelve frames of the old turn,
31–37 px through the new one.

The two detail beats are the reason the sequence reads as someone handling a
document rather than a camera executing a move: a pencilled "10" that some
archivist wrote, and the tape somebody used to reinforce the punch holes. The
signatures are what the shot is about; those two say the thing is an object that
has been filed, lent and repaired.

Coordinates on the page, if a beat ever needs re-aiming: the "10" sits at
(0.95, 0.035), the tape at (0.035, 0.31); on page 3, de Lattre (0.73, 0.655),
Spaatz (0.38, 0.60), Keitel (0.57, 0.275). A key that centres page point
(px, py) is `cx = 0.5 + (0.5 - px) * pw / 1080`, `cy = 0.5 + (0.5 - py) * ph / 1920`,
clamped so the sheet still covers the frame.

### The turn

`--turn t0,t1,page` folds the sheet over instead of swapping the image. A cut
between two scans says "another page"; it does not say a hand. What says a hand
is the crease: a seam crossing the frame, the lifted part of the sheet mirrored
back over itself and foreshortened, its underside darkening as it leans, and a
shadow thrown on the page it uncovers. Each sheet keeps its own scale — through
the turn and on both sides of it. They differ only because the scans do, 1024 px
against 1860 px for the same sheet of paper, so a ramp between the two `s`
values would swell or shrink the page while it is being handled, which is the
one thing paper does not do.

The clip is 377 frames against the 371 the two shots consume, so the settle
lands at the end of the second shot rather than after it. **If the narration is
re-recorded**, read the new shot lengths from `generated/report.txt`, set
`--frames` to their sum plus six, and set `in` on the 1:32 row of `shots.csv`
from the 1:26 shot's **frame count**, not its seconds: 186 frames at 30 fps is
`in = 6.200`. The report's 6.22 s would put the seek 0.6 of a frame past the
boundary, and the seam would repeat or drop one.

**Then re-run `tools/generate_shots.py`.** `render_reel` reads
`generated/shots.json`, never `shots.csv` — the CSV is the edit decision and the
JSON is what was compiled from it, which is the whole reason they are separate
(SPEC §4). Editing the CSV and rendering without recompiling leaves the old
in-point in force, and the two shots then read overlapping stretches of one
clip: with `in` still at 5.420 against a 186-frame first shot, the reel replayed
23 frames — 0.77 s of the sheet travelling — starting seven frames after the
turn, and the page appeared to be laid into the frame twice. The alignment is
deterministic: recompiling costs about a minute and moves no cue.

## The cold open — S00, 4.80 s

Not in `shots.csv`, and deliberately so: the reel is cut to a recorded
narration and every cue in it is measured from that recording, so a shot
inserted at the head would move all twenty of them. The hook is built as its
own clip and joined ahead of the reel at assembly.

The sheet first. It is a markdown file — `hook_page.md`, in git — typed in
Special Elite onto paper fitted to the act itself. Not sampled by eye: the
blank margins of `S12_ru_page_move.mp4` were measured by feature size, and the
sheet is generated to land inside the same three figures (2.3–2.6 levels of
grey coarser than 56 px, 1.8–2.4 between 12 and 56, 2.1–3.1 finer than that,
and the middle band 1.2–1.5 times steeper down the frame than across it, so it
lies in horizontal bands). Two things follow that guessing gets wrong every
time: archive paper photographs **smooth** — no fibre, no stipple — and its
type has **no clean edge**, carrying a halo and losing whole parts of a stroke
where the ribbon skipped.

    python tools/render_page.py \
        --page projects/legends_of_surrender/sources/hook_page.md \
        --out projects/legends_of_surrender/sources/composites/hook_page.png \
        --anchor "M E M O A C T S" --anchor "8,9" --anchor pencil

It prints the three `render_move.py` keys below rather than leaving them to be
measured off the image by eye, exactly as `render_map.py` prints its `focus`.
**If the sheet is edited, re-read the keys from that output** — a line added
above the wordmark moves every anchor under it.

    python tools/render_move.py --project projects/legends_of_surrender \
        --image hook_page.png --name S00_hook --frames 144 --ease cosine \
        --shutter 0.5 --subframes 384 \
        --caption-from projects/legends_of_surrender/script.md \
        --key 0.000:0.505,0.812,1.00 --key 0.112:0.505,0.812,1.00 \
        --key 0.231:-2.833,1.627,1.00 --key 0.545:-2.833,1.627,1.00 \
        --key 0.622:-0.412,0.172,1.00 --key 1.000:-0.412,0.172,1.00

**The holds are cut to the read, not to a feel.** The take was measured on its
own envelope — 50 ms buckets, not by ear — and the move was fitted to what came
back:

| time | | | spoken |
|---|---|---|---|
| 0.00–0.54 s | held on **M E M O A C T S**, typed among the working notes | | |
| 0.54–1.11 s | up and right across the header | 6 880 px/s | |
| 1.11–2.62 s | held on the pencilled **67** in the corner | | 1.20–2.60 |
| 2.62–2.99 s | back down and left | 10 350 px/s | |
| 2.99–4.80 s | held on **8,9** in the enumeration | | 2.95–4.45 |

Each line is on screen from just before its first syllable to just after its
last. **The 0.30 s the reader left between the two sentences is the whole
budget for the second whip**, which is why it is nearly three times the speed
of the first — the alternative was a caption arriving after the line it
captions, which was what the first cut of this did. Re-record the hook and this
move is re-timed with it; the two are not independent.

Five things about it are load-bearing:

- **`s = 1.00` throughout.** The sheet is generated, so it is generated at the
  size the closest beat needs: one page pixel per frame pixel, nothing
  resampled, no enlargement to declare, and the paper keeps the grain it was
  drawn with. It also makes the two whips cheap, since a frame is a paste.
- **The camera never zooms**, because the model is a sheet on a bed and paper
  does not swell — the same rule the act shot follows. That is what forces the
  enumeration into display type: one type size cannot both hold the wordmark in
  a 1080 px frame and fill it with two numerals. Both sizes were reset on
  **2026-08-22**. The wordmark is `display 1.12` — fifteen cells, 1065 px of the
  1080, the widest it can be and still be whole; it was `center` (1.00, 960 px)
  and simply read small on the opening hold. The enumeration is typed
  `1,2,3,…` **without spaces**: with `, ` between them the anchor was four cells
  and 998 px, so the **8** and the **9** sat pinned against opposite edges of a
  1080 px frame with a comma marooned between them. Closed up they are three
  cells and 749 px, and read as one pair. `display` stays at **3.9** — the
  numerals did not change size, only their spacing.
  The second whip travels further for it (10 350 px/s, was 9 250), so the
  subframe ceiling was re-checked rather than assumed: rendering the same move
  at `--subframes 768` gives a frame-for-frame identical clip, so 384 is not
  binding and the smear is still sampled by distance.

- **`--shutter 0.5`** is what makes the whips read as speed rather than as a
  stutter: at 9 250 px/s the sheet crosses nearly a third of the frame between
  frames, and the second whip is only eleven frames long. It is off by default,
  so `S12_ru_page_move` above still renders identically. `--subframes 384` goes
  with it — the samples are spaced one per pixel and a half, so the cosine peak
  of that whip asks for about 325 of them, and the default ceiling of 48 would
  leave the smear as a row of ghosts, which is the artefact the shutter exists
  to remove. It is a ceiling, not a count: the holds still cost two samples
  each.
- **The two lines come out of `script.md`**, from a `> **HOOK**` blockquote that
  the script parser drops — the hook is not in `narration.wav`, so it cannot
  be a shot without shifting every cue after it, but screen text is verbatim script
  text and never a string typed into a command line. `--caption-from` puts one
  line on each hold, filling from the last hold backwards, and takes the timing
  from the move itself; re-time the move and the lines follow — as they did
  when the cold open was cut to the recorded read. They carry no styling of
  their own: the reel's caption sits below the middle of the frame
  (`subs.SubStyle`) precisely so it clears the beat a page move aims at, and a
  cold open captioned differently would read as another film.
- **The 67 is what sets the caption height for the whole reel.** It is the one
  beat whose subject is drawn rather than photographed, so its extent can be
  measured: ink to y = 1259 of 1920. `margin_v` 670 put the plate's top edge at
  1184 — through the tail of the 7. 530 puts it at 1324, clear by ~98 px on the
  rendered frame. Every other shot is a photograph, and a photograph has no
  edge to clear; this one does, so it decides.

The clip itself is mute; the read arrives at assembly, off the head of
`voiceover.wav`.

## The recording — one take, two files

The hook and the reel are read in one pass, and the take is exported whole:
`voiceover.wav`, 168.968 s. Everything downstream of alignment means the *reel's*
narration by `narration.wav`, and a file that opens with two lines the reel does
not contain would push every cue in it out by the length of the hook. So the
take is cut once, at the length of the hook clip:

    ffmpeg -ss 4.8 -i sources/voiceover.wav -c copy sources/narration.wav

`-c copy` on PCM is a sample-exact cut, not a re-encode — same MD5 as
`-af atrim=start=4.8`, checked both ways. 4.800 s falls inside the 1.31 s of
silence between the last hook word (4.070 s) and the first reel word (5.380 s),
so neither side loses a syllable and the reel's read keeps a 0.58 s lead-in.

**`voiceover.wav` is the master and the only thing muxed.** `narration.wav`
exists for alignment, and for the working copy of the reel that `render_reel`
lays it under; the finished file takes its audio from the whole take, encoded
once.

## The whole reel — 20 shots behind the hook, 168.97 s

**`out/reel.mp4` is the finished film, hook included** — changed 2026-08-22.
It used to be the hookless body, with `out/reel_with_hook.mp4` as the joined
cut; now the body is an intermediate under `generated/` and the join lands on
`out/reel.mp4`. Two consequences worth knowing before running this:

- `out/reel_with_hook.mp4` **is no longer produced by this file.** The copy on
  disk is a frozen artefact, deliberately kept: it is the last cut rendered
  with Natural Earth's uncorrected border, where Crimea reads as Russia. Do not
  overwrite it — it is the evidence the correction was needed.
- The body cannot be written to `out/reel.mp4` any more, because the assemble
  step reads it. It goes to `generated/`, which is the compiler's own output
  and deletable by design.

    python tools/render_reel.py --project projects/legends_of_surrender \
        --out projects/legends_of_surrender/generated/reel_body.mp4

    python tools/assemble_reel.py \
        --clip projects/legends_of_surrender/sources/composites/S00_hook.mp4 \
        --clip projects/legends_of_surrender/generated/reel_body.mp4 \
        --narration projects/legends_of_surrender/sources/voiceover.wav \
        --narration-under 1 \
        --subs projects/legends_of_surrender/sources/composites/S00_hook.srt \
        --subs projects/legends_of_surrender/generated/reel_body.srt \
        --out projects/legends_of_surrender/out/reel.mp4

5 069 frames — 144 and 4 925, joined without re-encoding a single one, because
both clips come out of `memoacts_core.render.encode` and so already agree on
codec, size, pixel format and rate.

**The narration is neither delayed nor re-cut.** `--narration-under 1` says it
runs from the first clip, so the delay computes to zero, `adelay` is never
added, and the take is encoded to AAC exactly once, straight from the WAV
master. Nothing is padded and nothing is spliced — which is what keeps the
hook's read where the microphone put it relative to the reel's, the one
relationship a two-file mux would have had to reconstruct by hand.

The delay is not typed in either way. `--narration-at` defaults to the length of
the clips ahead of whichever clip the narration runs under, read off the files,
so it cannot disagree with what was actually joined.

`reel_with_hook.srt` is written beside the video: the hook's two lines, then
every reel cue moved on by 4.800 s. **That file is what the hook's line is
recorded against** — the timings on screen are already fixed by the move, so
the read fits the cut rather than the cut being re-fitted to the read.
