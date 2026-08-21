# The workshop — you cut a reel to your own voice

By the end of the day you have a vertical video: your words, read in your voice,
with your pictures, captioned in the exact text you wrote. You also know what
each of the five steps did to it, which matters more, because the first one you
can do again on your own.

The tool is five nodes in ComfyUI. There is no command to type.

## Before you start

Bring three things:

| | What it has to be |
|---|---|
| **A script** | 40–60 seconds of speech, in English. Six or eight sentences. Write it as you would say it |
| **A recording** | you reading it, one take, `.wav`. We record it in the room |
| **Pictures** | six or so. Bigger is better and you will see exactly why |

Everything else is on the machine.

> **Your reel is a folder.** Four folders and three files under `projects/`, and
> your name on it. Nothing you do reaches anyone else's; nothing anyone else
> does reaches you.

---

# The five steps

Open the workflow: **Workflows → memoacts_reel_stills**. Six boxes appear, wired
left to right. Five of them are the reel; the sixth is a shortcut you will be
grateful for.

## 1 · Project — "this is my material"

Pick your folder in the **project** dropdown. Press **Run**.

It reads the folder and tells you what it found: which recording, how long, how
many pictures, how many shots your script has, and which picture each shot
ended up with.

**Read this before anything else.** Every way a day goes wrong starts here — a
recording in the wrong folder, a picture that is not where the shot says it is.
Two seconds of reading against twenty minutes of confusion.

## 2 · Align — "my words become timings"

Press **Run** again. This one takes a minute or two, and it is the only slow
step in the day.

It listens to your recording with your script in hand and works out when each
word lands. **It is not transcribing.** It never decides *what* you said — only
*when*. That is the whole reason the captions later say exactly what you wrote,
including the dates, which an automatic subtitle button gets wrong more often
than not.

It runs once. Everything you do afterwards is free, until you re-record or
rewrite.

## 3 · Shot Table — "I decide what is seen"

This is where you work, and it is a table because that is what the decisions
are: one row per sentence, and one decision per column.

| Column | What it decides |
|---|---|
| **media** | which picture this sentence is over |
| **motion** | how it moves — `zoom_in`, `pan_lr`, `static`, and the rest |
| **rate** | how fast, as a fraction. 0.04–0.08 reads as a slow drift |
| **focus** | what the shot is *about* — see below |
| **label** | a tag in the corner: a place, a person |
| **credit** | where the picture came from, held for the shot |
| **effects** | the look, and what it costs you in render time |
| **notes** | for you. The tool never reads it |

Two things on this panel are worth more than the rest of the day:

**The number next to every picture.** `Karlshorst-Prepared.jpg — 0.96×`. That is
how much picture there is compared with the frame. **Below 1.00 means the
picture is smaller than the video and has to be blown up to fit** — it will look
soft, and no setting fixes it. Above 1.00 is room to move.

**Drag on the thumbnail.** The rectangle you draw is what the shot pushes in to
— the face, the signature, the town on the map. Click, and it moves without
resizing. The panel answers you as you draw: *"focus 0.375 · 2.67× push-in"*,
or in orange, *"as narrow as this source allows; anything tighter is
enlargement"*. It refuses to let you draw a window it would have to widen
behind your back.

Press **Save** when the table reads the way you want. **Run** rebuilds the shot
list and prints the report.

## 4 · Subtitles — "the words become captions"

Set the size and the plate — the box behind the text, which is there because
archival pictures run from near-black to bare paper and no single text colour
survives both.

It shows you every caption and when it appears, instantly, without rendering
anything. If a caption is too wide for one line it says so in red: a wrapped
caption stacks two plates and puts a dark bar through its own text.

## 5 · Render Reel — "the reel is made"

**Run.** Frames appear in the node as they are made, and the finished video
plays there when it is done. Minutes, not seconds.

Which is why the sixth box exists.

## One shot, in seconds

**Preview Shot** renders a single shot — type its number, run, watch. Seconds
instead of minutes. This is how you decide whether a move works. Use it about
twenty times before you render the reel once.

It has no sound and no captions, deliberately: both are timed from the start of
the reel and would be wrong against a piece of it.

---

# What you get, and what you don't

**You get** a 1080×1920 MP4 at 30 fps, your narration passed through without
being re-encoded, captions burnt in, and the `.srt` beside it.

**You don't get:**

- **A timeline.** You cannot drag a shot to make it a second longer. The
  narration decides how long each shot is, because the narration is what the
  audience is following. To change a duration, change the sentence.
- **Anything invented.** No picture is generated, no line is written for you, no
  gap is filled. The tool arranges what you brought.
- **An undo button on the file.** `shots.csv` is a text file your edits are
  saved into. It is also the only place your decisions live, which is why it is
  the one thing worth copying somewhere before you experiment.
- **Silent upscaling.** If a picture is too small the tool tells you, twice, and
  then does the best it can. It will never quietly pretend the pixels are there.

That last one is the difference worth taking home. Every step here reports what
it did and what it could not do. The workflow you are used to — the one with the
auto-subtitle button — does neither, which is why its mistakes reach the screen.

---

# When it goes wrong

| What you see | What it means |
|---|---|
| `no narration.* in …` | the recording is not in `sources/`, or is not named `narration` |
| every caption is in the wrong place | the read and the script diverged. Re-read the block, do not edit timings |
| `confidence 0.00` everywhere | alignment fell back to spreading the shots evenly. Step 2 failed; the log says why |
| a shot shows a picture you did not choose | that shot names nothing, so it took the next picture in the folder |
| `WRAPS` in the subtitle panel | a caption is too long for one line. Shorten the sentence |
| the table says `0.42×` and looks alarmed | your picture is less than half the width of the frame. Find a bigger one |
| the render is taking forever | look at the effects column. `newsreel` costs four times a plain render |

If something is not on this list, the message on screen is written to be read.
Read it before asking — it usually names the file.
