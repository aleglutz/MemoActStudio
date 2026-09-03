# Assembling a reel, end to end

**Draft, 2026-08-29.** Written to be walked, not read. Every step says what you
should see when it worked, because a step that half-worked is the expensive
kind.

This is the long form. `docs/WORKSHOP_HANDOUT.md` is the short one a student is
handed on the day; when the two disagree, this one is being tested and that one
is being taught.

> **This draft is a crash test.** It has never been walked by anyone. Where it
> is wrong, it is wrong in a specific place — write the place down (§6) rather
> than working around it, because working around it is how a document stays
> wrong for a month.

---

## What you bring

| | |
|---|---|
| **A script** | Written scene by scene. Each scene is a heading, `## S01`, `## S02`, … and under it what you say in that scene. No timecodes |
| **A recording** | You reading it, one take. Any format ComfyUI can load |
| **Images** | One per scene, roughly. Larger is better — see step 2.3 |

The script format matters more than it looks:

```markdown
## S01
The 8th of May. And the 9th.

## S02
One long day here opened a fork that still runs across Europe.

## S03
```

- **The `##` is not decoration.** A bare line `s01` is not a heading. The tool
  will not see a new scene, will glue the text onto the scene before it, and the
  words will end up spoken by nobody and burnt into somebody else's subtitle.
- **And watch for `\## S01`.** Some editors add a backslash before a `#` when
  text is pasted into them. In markdown that means "a literal hash, not a
  heading", so the tool obeys it and none of your scenes exist: a 34-scene
  script arrives as 69 blocks and the heading lines get spoken. It has happened
  once already. The Project node now says so in plain words — but the fix is
  yours, and it is to delete the backslashes.
- **A heading with nothing under it is legal** — `## S03` above. That is a
  silent scene: it holds screen time and the alignment fills it from the pause.
- **Numbers and dates are written as you say them.** They are never transcribed,
  so what you type is what appears on screen.

Save it as `script.md` in your project folder.

## Your project folder

```
projects/<your name>/
  script.md          your text
  shots.csv          your edit decisions — the tool writes it, you edit it
  sources/
    narration.wav    what step 1 produces
    images/          your pictures
    sfx/             sounds, if you get that far
  generated/         the tool's own working files
  out/               the finished reel
```

Projects are separate. Nothing you do reaches anyone else's.

---

## The three workflows

Three graphs, opened in this order, each finished before the next is opened.

| | | leaves behind |
|---|---|---|
| **1 · Voice** | "This is my voice, as I want it heard" | `sources/narration.wav` |
| **2 · Reel** | "This is the film" | `out/reel.mp4` |
| **3 · Generation** | "This is a thing that did not exist" | new material in `sources/` |

They are separate for a reason you will feel rather than read: workflow 2's
second step listens to your recording and takes about ninety seconds. It only
does that again if the recording or the script changed. Keeping the voice on its
own canvas is what stops an EQ tweak from costing you ninety seconds.

---

## 1 · Voice

**Open:** `example_workflows/voice.json`, from this pack.

The chain is already built and already numbered:

| | Node | What it is for |
|---|---|---|
| 1 | **Load narration** | your take |
| 2 | **Speech Denoise** | room noise. On at `0.5` — turn it off (ctrl+B) if the source is clean; any denoiser costs a little detail |
| 3 | **Pitch / Time** | tempo, and pitch separately. The default is 1.15× with pitch left alone |
| 4 | **EQ** | cut rumble, lift presence. ComfyUI's own 3-band, the one node here that is not ours |
| 5 | **De-esser** | the `s` sounds |
| 6 | **Vocal Compressor** | evens out loud and quiet |
| 7 | **Normalize (peak)** | brings the peak to −1 dBFS |
| 8 | **Loudness Meter** | what you actually made, in LUFS. Aim near −14 |
| 9 | **Set Narration** | writes it into a project — see 1.1 |

They are in the node menu under **`memoacts/audio`**, and every one of them
takes audio and returns audio, so you can cut the chain anywhere or bypass a
node you do not want.

Work top to bottom. Listen after each change — the nodes preview audio, so you
do not have to render anything to hear what you just did. Node 8 is worth
running early: it tells you whether the problem is level or tone before you
start turning knobs.

**On speed.** Changing tempo here is fine and it is the only place it is fine.
Everything after this listens to the *result*: the timings of every subtitle and
every cut are measured against the recording as it comes out of this graph. If
you speed the voice up later, all of them are wrong. So: decide the pace here,
then leave it.

### 1.1 Set Narration — where your project begins

Node 9 is already at the end of the chain. There is no save node in front of
it and there should not be: the file it writes is the one the reel reads.

Type a name into **project**. If nothing under `projects/` has that name yet, it
is made now — folders, an empty `script.md`, and a `shots.csv` with a header and
no rows. If it exists, it is used as it stands.

Press **Run**.

**You should see** a report naming the folder, saying whether it was created,
and giving the recording's length, channels and sample rate. Then a short list
of what is still missing — your scenes, your pictures — because at this moment
the project is empty and this is the only node that knows it.

Three things it is doing quietly, each worth knowing:

- **It writes WAV and only WAV.** The reel looks for `narration.<anything>` and
  takes the first alphabetically, so a stray `narration.mp3` would beat your
  `narration.wav` silently and for as long as both existed. Any other
  `narration.*` is **moved into `archive/`** — moved, never deleted — and named
  in the report.
- **It leaves the file alone if you Run again with the same audio.** Alignment
  is remembered against this file; rewriting identical samples would throw that
  away and cost you ninety seconds for nothing.
- **It does not touch your voice.** The rate and channel count you recorded at
  are the ones written, as 24-bit PCM. Nothing is resampled, nothing is
  compressed. The one compression in the whole pipeline happens at the very end,
  when the MP4 is made.

**You should now have:** `projects/<your name>/sources/narration.wav`, and a
folder tree ready for the rest.

---

## 2 · Reel

**Open:** `example_workflows/reel_stills.json`, from this pack. Six nodes,
left to right. Five make the reel;
the sixth renders one scene for checking.

### 2.1 Project — "this is my material"

Pick your folder in the **project** dropdown. Press **Run**.

**You should see** a report: the recording it found and how long it is, how many
images, how many scenes your script has, and which image each scene got.

**Read it before going on.** Nearly everything that costs time later is visible
here:

- *Fewer scenes than you wrote* → a heading lost its `##`.
- *Wrong recording length* → the old take is still in `sources/`.
- *An image on the wrong scene* → that is what step 2.3 is for; not an error.

### 2.2 Align — "my words become timings"

Press **Run**. **Ninety seconds or so, and it is the slow one.** The first time
ever on a machine it may also download a model.

It compares the recording with the script and works out when each word is
spoken. It never decides *what* was said — only *when*. That is why your
subtitles come out as you wrote them, dates and names included.

**You should see** it finish without warnings. The result is remembered: it runs
again only if you change the script or the recording, so everything below is
free.

### 2.3 Storyline — "I decide what is seen"

This one is not on the canvas. Open the **Storyline** tab in ComfyUI's left
sidebar (the pictures icon) and choose your project at the top — it opens on
whatever the graph is about.

The panel is your scenes, stacked in the order they are spoken, and a shelf of
your pictures above them.

**To give a scene its picture: click the scene, then click the picture.** That
is the whole gesture. It writes the `media` column of `shots.csv`, the same file
you could edit in a spreadsheet, and neither loses the other's work.

What each scene shows you:

- **A bar for how long it lasts**, next to the seconds. Full width is the
  longest scene in the reel. This is the rhythm of the film — three short bars
  in a row will flash by, one long bar is a picture that has to hold. The bars
  appear once Shot Table has run; before that the panel says so.
- **auto** — nobody chose this picture. It is the cycled default, and it is how
  a scene reaches the render never having been looked at.
- **same as previous** — two scenes in a row on one picture. The renderer gives
  every scene its own move, and the default preset changes with the scene
  number, so the picture does not merely restart: it changes direction. Either
  give one of them a different picture, or **merge them** — see below.
- **missing** — the file named in the row is not in `sources/`.

Selecting a scene fills the panel below it: the picture large, with the **focus
rectangle** — drag on it to say what the shot is about, click to move the window
without resizing it — and the rest of the decisions.

**Where a scene begins and ends** is under the picture, and it is the one
control here that changes your script rather than your edit:

- **merge into S…** joins this scene to the one before it. Use it when the two
  are one picture and one move — "hold, then push in" is one scene, not two.
  The merged scene keeps the first row's picture and takes anything the first
  left blank from the second, so a focus set on the second half survives.
- **split before "…"** cuts a scene at a sentence. Both halves start on the same
  picture, which is how you *make* a hold-then-push-in: split, then set a focus
  on the second half.

Both rewrite `script.md` and renumber `shots.csv` with it, so your pictures stay
on the scenes you put them on. Both mean **Align runs again** — your words have
not changed, but which shot they belong to has. Save your edits first; the panel
will refuse if you have not.

| | Decides |
|---|---|
| **motion** | how it moves: `zoom_in`, `zoom_out`, `pan_lr`, `pan_rl`, `static`, … |
| **rate** | how fast, as a fraction of the frame. 0.04–0.08 reads as a slow drift |
| **corner tag** | a place or a person, in the corner |
| **credit** | where the picture came from |
| **look** | an effect preset, with what it costs in render time |
| **in-point / speed** | footage only |
| **notes** | yours |

Two more things worth knowing:

- **Hover a picture on the shelf** and it tells you its size and how far it can
  be pushed before it is being enlarged past its own resolution. An orange
  caption means it is already too small for the frame. That is a choice you make
  now rather than a warning you get after a render.
- **Expand** puts the same panel full screen, which is the way to lay out a
  whole reel's pictures at once. Escape closes it. Nothing is lost either way,
  saved or not.

Press **Save** in the panel, then **Run** on the Shot Table node — the panel
writes the decisions, the node compiles them.

**You should see** the node's report: every scene, when it starts and ends, how
confident the alignment was, and which picture it will use. Run it once and the
duration bars appear in the panel.

### 2.4 Subtitles — "the words become captions"

Press **Run**. Nothing is rendered; this is instant.

**You should see** the actual captions, cut from your own words at the timings
just measured, with their start and end times — and, if any caption is too wide
for one line, a list of them under **WRAPS**.

**Fix the wraps.** A wrapped caption stacks two backing plates and puts a dark
bar through its own text. Either shorten the sentence in `script.md` — which
means re-recording — or drop the caption size a little.

### 2.5 Preview Shot — before you commit to minutes

Set **shot_id** to a scene you are unsure about and press **Run**. Seconds, not
minutes, and one scene is what you actually look at when deciding whether a move
works. No captions and no voice: both are timed from the head of the reel and
would be wrong against a fragment.

Do this two or three times before 2.6. It is the difference between one render
and five.

### 2.6 Render Reel

Press **Run**. **Minutes** — roughly four to five for a two-and-a-half-minute
reel, longer if you chose a look in the effects column.

You will see frames appearing as they are made. That is the render, not a
preview: if you stop liking it, cancel.

**You should see**, when it finishes, a line reporting the video's length
against the narration's, and the drift between them — **a few milliseconds is
right**. The video plays in the node.

Each render is a new numbered file. The previous one is not overwritten, so you
can compare.

---

## 3 · Generation — only when a scene needs something that does not exist

Skip this entirely unless a scene has nothing to show. It is where the sheet of
paper in the opening of "89" comes from, where sound effects come from, and
where whatever gets built next will go.

The rule that keeps it simple: **workflow 3 does not touch the reel.** It makes
a file, puts it in `sources/`, and then that file is an ordinary picture or an
ordinary sound to workflow 2. Nothing downstream can tell it was generated.

- **A page, a plate, a composite** → lands in `sources/composites/`, and you
  choose it in the media column like any photograph.
- **Sound** → `Sound Design` writes a table of what each scene should sound
  like, `SFX Prompt` and `Save SFX` walk it one row at a time through whatever
  makes the audio, and `SFX Bed` mixes the lot into one track that plugs into
  Render Reel's **sfx** input. Details in `docs/SOUND_DESIGN.md`.

---

## 4 · "89", from nothing

The specific crash test, and it is built from an empty folder on purpose: every
hole this document has is a hole a student falls into, and reusing a project
that already works would paper over exactly the steps that have never been
walked.

**Where the material stands on 2026-08-29:**

- `script.md` was rewritten on the 26th: **20 blocks became 28 scenes**, and the
  opening hook — *"Six-seven is dead" / "Let's talk eight-nine"* — moved from a
  separate clip into the reel as scenes 1 and 2.
- **The new recording does not exist yet.** The newest audio in the project is
  from the 20th. Workflow 1 is therefore step one in the literal sense.
- `shots.csv` is from the 22nd and still addresses its rows by timecode. Against
  the new script that is not a small mismatch: 9 scenes have no row, one row
  matches nothing, and four rows match a timecode while landing on a different
  line than the one they were written for.

**The crash test does not reuse `legends_of_surrender`.** The point is to walk
the pipeline from nothing, which is what a student does and what an existing
folder full of working media would hide. The new project is **`89-in-comfy`**,
and it starts empty.

**So the order is:**

1. Record the new read, shape it in workflow 1, and end on **Set Narration**
   with `89-in-comfy` in the project box. That call makes the folder.
2. Write `script.md` with `## S01` headings — the 28 scenes, no timecodes.
3. Put the pictures in `sources/images/`. They can be copied from
   `legends_of_surrender`: the material is the same film, and this test is about
   the pipeline, not about finding photographs twice.
4. Run Project and Align, and read the report. This is where the 28 scenes
   become real.
5. Fill in `shots.csv` by scene number, in the table widget. The old project's
   rows are the reference for which picture goes where; they are not importable,
   because they address rows by timecode and the timecodes are gone.
6. Scenes 1 and 2 need media: either the existing hook clip cut in two, or the
   newly generated sheet.
7. Render.

`assemble_reel` is no longer part of this. The hook is inside the reel now, and
`out/reel.mp4` is the finished film.

When it works, `legends_of_surrender` can be retired or rebuilt from what this
one proved. Until then it stays exactly as it is — a finished reel and a
reference for the edit.

---

## 5 · What to do when something is wrong

| What you see | What it usually is |
|---|---|
| Fewer scenes than you wrote | a heading without its `##` |
| About twice as many scenes as you wrote | every heading escaped as `\## S01` |
| A scene's words in the previous scene's subtitle | same thing |
| The old recording's length in the Project report | an old `narration.*` outside `sources/` — Set Narration reports any it moved aside |
| Alignment runs every single time | something is rewriting the recording between runs |
| A caption with a dark bar through it | a wrap — see 2.4 |
| A picture visibly soft | it is being enlarged past its resolution; the media dropdown said so |
| A rendered frame that is pure black | not your prompt. `docs/WORKSHOP_MACHINE_SETUP.md` §3.5 |

---

## 6 · Crash-test log

Fill this in while walking, not afterwards.

| Step | What happened | What the document should have said |
|---|---|---|
| 1 · Voice | | |
| 1.1 Set Narration | | |
| 2.1 Project | | |
| 2.2 Align | | |
| 2.3 Storyline panel | | |
| 2.4 Subtitles | | |
| 2.5 Preview Shot | | |
| 2.6 Render | | |
| 3 · Generation | | |
| 4 · "89" | | |

Three questions worth answering at the end, because they are what the September
day turns on:

1. **How long did the whole thing take**, ignoring the recording?
2. **Which step needed someone to explain it**, rather than the document?
3. **Could you name the five steps of workflow 2 afterwards, without looking?**
   If not, the handout is not finished.
