# Module 03 — four ways to work an archival film

Teaching material for the August online intensive. One thirty-second piece of
archival footage, put through four workflows that intervene in it by rising
degrees: quote it, sound it, sharpen it, colour it.

The order is the argument. Level 1 adds nothing to the image and takes its words
from a document. Level 2 manufactures something the film never carried. Level 3
invents texture inside the image. Level 4 invents the image. By the fourth,
students should be able to say where they would have stopped — and notice that
the tools give no indication of where the line was crossed.

## The footage

`projects/legends_of_surrender/video/MBK_KAPFILM_FINAL.mp4`, Museum
Berlin-Karlshorst, 7:36 — the German delegation arriving at Tempelhof, the
signing of the Act of Military Surrender at Karlshorst, and the banquet after.

Three facts about it decide everything downstream:

- **It is pillarboxed.** The transfer is 1280×800; the picture inside it is
  1068×800 at x=106. `cropdetect` agrees across the whole file. Working from the
  padded frame means cropping and scaling black bars all the way to the output.
- **It is silent.** Not quiet — the AAC track measures −91 dB mean *and* max end
  to end, with every one of its 43,776,000 samples in a single histogram bin.
  There is nothing to preserve, and nothing to duck under.
- **It carries the museum's own burned-in captions** — a trilingual DE/RU/EN
  plate, around 3:20 among other places. Our captions would argue with it.

## The working cut — 04:14–04:44

`sources/master_30s.mp4`, 1068×800, 901 frames, de-pillarboxed, audio dropped.

Keitel reads the act and raises a page; Zhukov presides; the delegation signs
while the press crowds the table. Chosen because the faces are large enough for
levels 3 and 4 to have something to argue about, the sound cues are varied
enough for level 2 to have something to make, and the museum's caption plate is
absent from this stretch.

One segment carries all four levels, so a screening shows one piece of film
under rising intervention rather than four unrelated clips.

## The four levels

| | Level | Runs on | What it adds |
|---|---|---|---|
| 1 | Quotes in frame | CPU | Nothing to the image; words from a document |
| 2 | Sound for silent film | 6 s GPU per layer | A soundtrack that never existed |
| 3 | Upscale / restoration | ~15 min GPU per 10 s | Twice the pixels, and texture no camera recorded |
| 4 | Colourisation | ~20 s GPU per frame | Colour, and — unguarded — the whole image |

`workflows/README.md` is the technical companion: what each graph is made of,
what it cost, and where each one broke.

## What each level actually established

**Level 1.** The quoted lines come off the signed English copy of the act held
in this repository, not off the footage and not out of a paraphrase. The same
three quotes render twice: through `DrawText+`, which is what Comfy Cloud can
do, and through libass, which is what the reel does. The stock version works and
is visibly poorer — one node holds one string over one frame range, and there is
no real caption plate. That is `GAPS.md` #3 made watchable.

**Level 2.** Sound is the cheapest level and the least-flagged fabrication.
Nobody captions a room tone; a generated hall murmur will be received as
atmosphere rather than as content, which is exactly what makes it worth showing
early. Judging the takes needs ears — one generated "press camera" layer came
back a tonal hum and had to be re-rolled.

**Level 3.** This doubles the film, 1068×800 to 2136×1600, and keeps the
enlargement — an upscaler that hands its pixels back has done nothing but leave
side effects. Two things change in the picture, and only one is the one people
expect. Edges get sharper: buttons, braid, the line of a cap. And the grain
disappears, because to the model grain looks like noise. The grain is the film.
Replacing it with smooth cloth is a decision about how the record should look,
not a repair. Which model you pick decides how much gets invented — `UPSCALE.md`
measured five of them and chose Remacri, and Comfy Cloud does not carry Remacri.
It carries two of the ones that document rejects.

**Level 4.** Asked to colourise, Qwen-Image-Edit did not colourise. It redrew:
a different face, re-invented medals, no film grain, the room re-lit — a
plausible modern photograph standing where a document had been. The fix is to
demote the model: keep the archival frame's luminance untouched and take only
its chroma, so no edge and no face can move. Both results are kept. The first is
the warning; the second is the method.

## Handing it to students

The August intensive runs on Comfy Cloud, where a job is killed somewhere past
half a minute of execution and our own node pack cannot be installed at all.
That sets a hard ceiling per level:

| Level | Handoff | Why |
|---|---|---|
| 2 — sound | **Yes** | One job per layer, six seconds of GPU, no frames at all |
| 1 — quotes | **Yes, chunked** | No model, but 900 frames of `DrawText+` needs splitting — or 12 fps, which suits the film anyway |
| 3 — restoration | Frames only | 4× of 1068×800 is 4272×3200 per frame; thirty seconds is not a Cloud job |
| 4 — colourisation | Stills only | A diffusion pass per frame, and no colouriser exists on Cloud in the first place |

So two of the four are genuinely hands-on, and they are the first two. Levels 3
and 4 are screened, with a single frame handed over so the students still touch
the thing they are being shown.

## What to put on screen

| File | | |
|---|---|---|
| `out/L1_quotes.mp4` | 30 s | Three quotes from the document, over the footage |
| `out/L2_sound.mp4` | 30 s | The same footage with a soundtrack that was made up |
| `out/L3_ab_zoom.mp4` | 10 s | **Screen this one.** Same patch of frame, plain enlargement on the left, Remacri on the right |
| `out/L3_split.mp4` | 10 s | One frame cut down the middle: left plain, right restored |
| `out/L3_restored.mp4` | 10 s | The restored clip on its own, 2136×1600 |
| `stills/L3_models_close_00014.png` | — | Plain ‖ Remacri ‖ NMKD-Siax on one face — where the model choice shows |
| `out/L4_ab.mp4` | 6 s | Three panels: the film, the model's redraw, the restrained version |
| `stills/L4_ab_*.png` | — | The same three panels at full size, on three frames |

Two things to say out loud, because the clips cannot say them:

- **Levels 3 and 4 are slowed down.** Level 3 is ten seconds of real time. Level
  4 is twenty frames played at ten a second — two thirds of a second stretched
  to two. Slow motion nobody announces is its own small fake, and this is the
  wrong module to commit one in.
- **Level 3 is twice the size of the others.** That is the point of it, but it
  means it will not sit in a row with levels 1, 2 and 4 without being scaled for
  the screen.

## Rebuilding

None of the media is in git. `REBUILD.md` regenerates all of it from the one
archival file.
