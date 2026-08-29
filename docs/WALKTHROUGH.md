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

**Open:** `MemoActs_VO_Speed_Normalize`.

The chain is already built and already numbered:

| | Node | What it is for |
|---|---|---|
| 1 | **Load narration** | your take |
| 2 | **Denoise** | room noise. **Bypassed by default** — turn it on only if you need it; it costs quality |
| 3 | **Speed up** | tempo, and pitch separately. The default is 1.15× with pitch left alone |
| 4 | **EQ** | cut rumble, lift presence |
| 5 | **De-esser** | the `s` sounds |
| 6 | **Compressor** | evens out loud and quiet |
| 7 | **Normalize** | brings the peak to −1 dBFS |
| 9 | **Save** | writes the file |

Work top to bottom. Listen after each change — the nodes preview audio, so you
do not have to render anything to hear what you just did. When it sounds right,
go on to 1.1, which is the node that puts it into a project.

**On speed.** Changing tempo here is fine and it is the only place it is fine.
Everything after this listens to the *result*: the timings of every subtitle and
every cut are measured against the recording as it comes out of this graph. If
you speed the voice up later, all of them are wrong. So: decide the pace here,
then leave it.

### 1.1 Set Narration — where your project begins

Add **MemoActs — Set Narration** at the end of the chain and wire the last
audio node into it. You can delete the Save node, or leave it: what reaches the
project is this one.

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

**Open:** `memoacts_reel_stills`. Six nodes, left to right. Five make the reel;
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

### 2.3 Shot Table — "I decide what is seen"

The node draws a table: one row per scene.

| Column | Decides |
|---|---|
| **media** | which picture this scene appears over |
| **motion** | how it moves: `zoom_in`, `zoom_out`, `pan_lr`, `pan_rl`, `static`, … |
| **rate** | how fast, as a fraction of the frame. 0.04–0.08 reads as a slow drift |
| **focus** | what the move heads towards — drag a rectangle on the thumbnail |
| **label** | a tag in the corner: a place or a person |
| **credit** | where the picture came from |
| **effects** | a look, with what it costs |
| **notes** | yours |

Two things worth knowing while you are in here:

- **The media dropdown tells you how far each picture can be pushed** before it
  is being enlarged past its own resolution. That number is a choice you make
  now, not a warning you get after a render.
- **You are editing a file.** The table is `shots.csv` in your project. You can
  edit it here or in any spreadsheet, and neither loses the other's work.

Press **Run**. **You should see** the shot report: every scene, when it starts
and ends, how confident the alignment was, and which picture it will use.

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
| 2.3 Shot Table | | |
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
