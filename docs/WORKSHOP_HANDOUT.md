# Workshop handout — assembling a reel

By the end of the session you will have produced a vertical video from your own
script, your own recording and your own images, with subtitles carrying the
script text exactly as written.

The pack is six nodes in ComfyUI. No commands are typed.

## What to bring

| | Requirement |
|---|---|
| **Script** | 40–60 seconds of speech, in English. Six to eight sentences, written the way you would say them |
| **Recording** | You reading the script, one take, `.wav`. Recorded during the session |
| **Images** | About six. Larger is better; the reason is explained in step 3 |

Everything else is installed on the machine.

## Your project

A project is a directory under `projects/`, named after you. It contains:

```
script.md      your text
shots.csv      your edit decisions, written by the Shot Table node
sources/
  narration.wav
  images/
generated/     shots.json and report.txt, written by the pack
out/           the finished video
```

Projects are separate. Nothing you do affects anyone else's.

## Opening the workflow

**Workflows → memoacts_reel_stills.** Six nodes appear, connected left to
right. Five of them produce the reel; the sixth renders a single shot for
checking.

---

## 1 · Project — this is my material

Select your directory in the **project** dropdown and press **Run**.

The node reports what it found: which recording, its length, how many images,
how many shots the script contains, and which image each shot resolved to.

Read this output before continuing. Most problems that cost time later — a
recording in the wrong directory, an image filename that does not match — are
visible here.

## 2 · Align — my words become timings

Press **Run**. This step takes one to two minutes and is the slowest in the
workflow.

It compares the recording with the script and determines when each word is
spoken. It does not transcribe: it never decides *what* was said, only *when*.
This is why the subtitles later reproduce your script exactly, including
numbers and dates.

The result is cached. It is recomputed only when the script or the recording
changes, so later steps cost nothing.

## 3 · Shot Table — I decide what is seen

One row per sentence, one decision per column.

| Column | Decides |
|---|---|
| **media** | which image this sentence appears over |
| **motion** | how it moves: `zoom_in`, `zoom_out`, `pan_lr`, `pan_rl`, `static`, and others |
| **rate** | how fast, as a fraction of the frame. 0.04–0.08 reads as a slow drift |
| **focus** | the area the shot moves towards — see below |
| **label** | a caption in the top corner: a place or a person |
| **credit** | the image source, displayed for the length of the shot |
| **effects** | a look, with its render cost |
| **notes** | your own notes; not read by the pack |

### The number beside each image

The media dropdown shows each file with a figure, for example
`Karlshorst-Prepared.jpg — 0.96×`. This is the width of the largest 9:16 window
the image can supply, divided by the output width of 1080 pixels.

- **Below 1.00**: the image is smaller than the video frame and will be
  enlarged to fit. It will look soft, and no setting changes that.
- **Above 1.00**: there is spare resolution, which is what a zoom uses.

### Setting a focus

Drag a rectangle on the thumbnail to mark the area the shot moves towards: a
face, a signature, a place on a map. Click to move the rectangle without
resizing it.

The rectangle is always 9:16 and is adjusted to what the renderer will use. The
panel reports the result as you draw, for example `focus 0.375 · 2.67× push-in`.
If you draw a rectangle narrower than the image can supply, it is widened to the
smallest usable size and the panel says so.

Press **Save** to write `shots.csv`, then **Run** to rebuild the shot table and
print the report.

## 4 · Subtitles — the words become captions

Set the font size and the opacity of the plate behind the text. The plate
exists because archival images range from near-black to white paper, and no
single text colour is legible over both.

The node lists every caption with its timing, without rendering. Captions too
wide for one line are flagged: a wrapped caption draws two overlapping plates,
which produces a dark band across the text.

## 5 · Render Reel — the reel is made

Press **Run**. Frames appear in the node as they are rendered, and the finished
video plays there when the render completes. A full reel takes minutes.

## One shot, in seconds

**Preview Shot** renders a single shot. Enter its number and run; the result
appears in seconds rather than minutes. Use it to check framing and motion
before rendering the whole reel.

It has no audio and no subtitles, because both are timed from the start of the
reel and would not match a fragment of it.

---

## What the pack does not do

- **No timeline.** Shot duration comes from the narration and cannot be set
  directly. To lengthen a shot, lengthen the sentence.
- **No generation.** No image is created, no text is written, no gap is filled.
  The pack arranges the material you supply.
- **No undo history.** `shots.csv` holds your edit decisions and is overwritten
  when you save. Copy it before making large changes.
- **No silent upscaling.** An undersized image is reported when you select it,
  in the shot report, and again at render time, with the enlargement factor.

## Troubleshooting

| Message or symptom | Cause |
|---|---|
| `no narration.* in …` | The recording is not in `sources/`, or is not named `narration` |
| Captions appear at the wrong times | The reading diverged from the script. Re-record the affected block rather than editing timings |
| `confidence 0.00` on every shot | Alignment failed and fell back to spreading shots evenly. The log states the reason |
| A shot shows an image you did not choose | That shot names no media, so images are assigned from the directory in order |
| `WRAPS` in the Subtitles node | A caption is too long for one line. Shorten the sentence |
| `0.42×` beside an image | The image is less than half the width of the output frame. Use a larger one |
| The render is much slower than expected | Check the effects column. `newsreel` costs about four times a render with no effects |
