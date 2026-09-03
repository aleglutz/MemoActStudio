# Workshop machine setup — September offline workshop

Provisioning procedure for the **two rented machines** (SPEC §0). Build machine
A by following this exactly, verify with §6, then image it onto machine B. Do
not hand-install twice — divergence between the two machines is the failure mode
that costs workshop time on the day.

**This document absorbed `HARDENING.md` on 2026-08-29.** That file was a list of
deferred portability items, and once the audience became two project-controlled
machines rather than sixteen personal ones, every item still alive in it was a
step in *this* procedure. It is now `archive/20260829_HARDENING.md`; nothing was
dropped without a line saying so. `SPEC.md` still names it in prose — read those
mentions as pointing here.

**Status: written 2026-07-28 against the dev machine, NOT yet executed on a
clean box.** Every step below is what the dev environment actually contains,
recovered by inspection rather than from an install log — so treat the first
run on machine A as the real test of this document, and correct it as you go.
Steps marked ⚠ are the ones most likely to be wrong.

## 1. What the workshop needs

| Component | Why |
|---|---|
| ComfyUI (Easy-Install, Windows) | the environment students work in |
| `comfyui-memoacts` (this repo) | the pack being taught |
| ffmpeg **built with libass** | motion render + subtitle burn-in |
| `stable-ts` + Whisper model | alignment (facilitator step, §4) |
| `num2words` | digit/date expansion before alignment |

Deliberately **not** needed: a GPU (SPEC §6.2.8 — Branch A has no GPU or
diffusion dependency by construction), an internet connection during the
workshop, any system-wide font install (the pack ships its own, §3).

## 2. Sizing the machines

Derive from the intended workshop project before booking — the numbers are not
arbitrary:

- **RAM.** The streaming renderer holds one frame at a time, so reel length no
  longer drives memory (`GAPS.md` #2). Measured on demo_en: **0.98 GiB peak**
  for Python + ffmpeg combined, 415 frames. The old ~11.5 GiB figure applied to
  the P1 tensor-batch approach and no longer governs. Budget for the OS,
  ComfyUI, and a comfortable margin rather than for the render.
- **CPU.** This is the real constraint. Rendering is CPU-bound: ~61 ms/frame at
  1080×1920 on the dev machine, so demo_en's 13.8 s reel takes ~25 s. A 2.5-min
  reel is ~4500 frames → roughly **4–5 minutes per render**. See §5.
- **Disk.** ComfyUI + embedded Python + Whisper model (~150–500 MB) + student
  project media. Modest, but give students room for their own images.

## 3. Install procedure (machine A)

1. **ComfyUI Easy-Install**, default location. Note the embedded Python path —
   everything below installs into *that* interpreter, never a system Python:

   ```
   <install>\python_embeded\python.exe
   ```

2. **Clone this repo** into `ComfyUI\custom_nodes\` so ComfyUI loads it:

   ```
   ComfyUI\custom_nodes\MemoActStudio\
   ```

3. **Python dependencies** into the embedded interpreter:

   ```
   .\python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\MemoActStudio\requirements.txt
   ```

   Four packages: `stable-ts`, `num2words`, `pedalboard`, `pyloudnorm`. As of
   **2026-09-03 all four are declared in `requirements.txt`** — the voice
   nodes came into the pack that day and brought the last two with them, which
   until then were installed on the dev machine and nowhere written down.

   ⚠ `stable-ts` pulls `openai-whisper` and depends on torch, which ComfyUI
   already ships — so the increment should be small. Verify it does not
   reinstall or upgrade torch; if it tries, stop and pin instead, because a
   torch swap can break the ComfyUI install itself.

   ⚠ `pedalboard` is a **compiled wheel** (Rubber Band + JUCE DSP), needed by
   the voiceover nodes. If no wheel exists for the machine's Python, this is
   the step that fails, and it fails *here* rather than mid-workshop only if
   somebody runs it. `pyloudnorm` is pure Python; `scipy` ships with ComfyUI.

   **This list is the whole list.** It was previously true only of the dev
   machine, by hand, unrecorded — which is exactly how two machines diverge.
   `requirements.txt` in the pack is the authority; if it and this line
   disagree, the file wins and this line is stale.

   ⚠ **numba must be new enough for whatever numpy is installed, and nothing
   says so until an alignment is attempted.** `stable-ts` → `openai-whisper` →
   `whisper.timing` → `numba`, and numba pins numpy *from above*: 0.62 wants
   `numpy<2.4`, 0.66 `<2.5`, 0.67 `<2.6`. Broken here on 2026-09-01 with
   `ImportError: Numba needs NumPy 2.3 or less. Got NumPy 2.4` — numpy had gone
   to 2.4.6 on 24 August and took the aligner with it.

   Fix by moving **numba**, not numpy: `pip install --upgrade numba` took it to
   0.67.0 with llvmlite 0.49.0 and touched nothing else. Downgrading numpy in a
   ComfyUI install is the worse half of the trade — a dozen packages here pin it
   in both directions and several already disagree with each other.

   Verify it properly, because importing numba is not the test:

   ```
   .\python_embeded\python.exe -c "import stable_whisper, whisper.timing; from numba import njit; print(njit(lambda a,b: a+b)(2,3))"
   ```

   **And note how long it hid.** Alignment is cached on the script and the
   recording, so a week of editing passed without anyone running it. The one
   step that needs this dependency is also the one step that rarely runs — on a
   workshop machine, check it on the day you image, not on the day you use it.

4. ⚠ **`ComfyUI_essentials`** was hand-cloned into `custom_nodes` on the dev
   machine, with its heavy requirements deliberately *not* installed. Check
   whether anything still needs it before cloning it onto A — the subtitle font
   dependency that justified it is gone (step 7). If nothing needs it, do not
   install it.

5. ⚠ **Do not put `--use-sage-attention` in the launch command, and check it is
   absent from anything cloned off the dev box.**

   On the dev machine, ComfyUI started with that flag renders **pure black**
   from Qwen-Image-Edit — 2–4 KB PNGs, zero luminance variance — while the job
   reports `success`. Nine consecutive runs were void before the pattern was
   spotted; every void run carried the flag and every good one did not. There
   is no error, no warning and no clue in the log.

   The danger is not the black frame, which is obvious once looked at. It is
   that the flag is a **four-fold speedup** — 42 s a frame against 156 s — so a
   provisioning pass that benchmarks the machines will find it and keep it, and
   a student whose graph returns black will reasonably blame their own prompt.

   Scope is unverified beyond Qwen-Image-Edit on that GPU; ESRGAN upscaling and
   Stable Audio were unaffected in the same session. Either test every model the
   workshop uses under the flag, or leave it off and accept the slower figure.
   §6 step 5 is the check that catches it.

6. **ffmpeg with libass.** Confirm before relying on it:

   ```
   ffmpeg -hide_banner -version | findstr enable-libass
   ffmpeg -hide_banner -filters | findstr subtitles
   ```

   Both must produce output. A build without libass fails at *render* time, not
   install time — the worst moment to discover it. Put ffmpeg on `PATH`;
   `memoacts_core.render.ffmpeg_exe()` looks there first.

7. **Pre-seed the Whisper model** so nothing downloads during the workshop. Run
   one alignment on machine A (§6 step 2) — the model is fetched once and cached
   into the user profile, and the image then carries it.

   ⚠ Confirm where it caches and that the cache survives imaging; if the image
   is applied under a different user account, the cache path may not carry over.

8. **Fonts: nothing to do.** The pack ships Share Tech Mono under SIL OFL 1.1 in
   `assets/fonts/`, and burn-in resolves against that directory by default. Do
   *not* install the font system-wide — the point is that a fresh machine
   renders identical captions with no provisioning step.

## 4. What the facilitator runs vs what students run

⚠ **Revised 2026-08-21, and the change is load-bearing for imaging.** This
section used to say students never run alignment, because P1's prepared-inputs
model had a facilitator produce `shots.json` in advance. That is no longer true:
the graph is the teaching surface (`docs/INTERFACE_BRIEF.md`, `docs/PLAN.md`),
and **students press Run on `MemoActs — Align` themselves**, on their own
recording.

Consequences for the machine:

- The Whisper model must be **on both machines, pre-seeded, working offline**
  (§3.7). It is no longer a facilitator-only dependency that could be broken on
  B without anybody noticing until after the workshop.
- Alignment is ~90 s of CPU per student per re-record, and it lands in the
  rotation budget (§5) alongside the render.
- The facilitator's CLI (`tools/`) stays installed and stays working — it is the
  reference implementation and the recovery path — but nothing a student sees,
  types or is examined on is a terminal command.

The facilitator path, for reference and for §6:

```
python tools/generate_shots.py --project projects/<name> --lang en
```

→ `generated/shots.json`, a file a human can read and edit.

## 5. Rotation budget — check this before the day

16 students across 2 machines is ~8 per machine, so a render must not
monopolise a machine. Measure on the *actual* rented hardware:

```
python tools/render_reel.py --project projects/demo_en
```

Dev machine reference: **25 s for 415 frames** (13.8 s reel), subtitles free.
Scale linearly for the workshop project's length, then multiply by the number of
attempts a student realistically makes. **If a single render eats a meaningful
slice of a rotation slot, cut the exercise project's length rather than
discovering it live** — a shorter reel teaches the same pipeline.

## 6. Verification (run on A before imaging, and again on B after)

1. **Render the fixture end to end:**

   ```
   python tools/render_reel.py --project projects/demo_en
   ```

   Expect: 4 shots, 415 frames, 13.833 s, drift within a few ms, and one line
   reading `[MemoActs] 03_small.png: source supplies only 562px for a 1080px
   output (1.92x enlargement)` — **that warning is correct behaviour**, not a
   fault. The fixture deliberately contains a source too small for the output
   so the resolution guard is exercised. (It used to arrive as a bare Python
   `UserWarning` on stderr; the pipeline now collects it so the graph can show
   it too, and the CLI prints it with the same prefix the nodes use.)

2. **Alignment produces timings** (this also seeds the model, §3.7):

   ```
   python tools/generate_shots.py --project projects/demo_en --lang en
   ```

3. **Captions render in the right font.** Open the output around 11.5 s: the
   caption should be Share Tech Mono, white, bottom-centred, wrapped onto two
   lines. A different-looking font means `fontsdir` did not resolve and libass
   fell back — the render does *not* fail, so this must be checked by eye.

4. Confirm both machines produce byte-comparable output for the same input. They
   need not be identical (encoder threading can differ), but frame count and
   duration must match exactly.

5. **A rendered frame is not black.** The `--use-sage-attention` failure (§3.5)
   reports `success` and writes a file, so the only way to catch it is to look
   at the pixels: **a frame whose luminance standard deviation is ~0 is not an
   image.** Assert it on one generated frame, not by eye — the whole point is
   that it passes every other check.

6. **The node path, not only the CLI.** Every step above except this one
   exercises `memoacts_core` through `tools/`. Students use the graph, so open
   ComfyUI and confirm:

   - the pack loads and its nodes are listed under `memoacts` — the count is in
     `__init__.py`, and a node missing from the menu means an import failed
     silently at startup;
   - `Project → Align → Shot Table → Subtitles → Render Reel` runs end to end on
     `projects/demo_en` and produces the same frame count and duration as step 1;
   - the shot table draws as a table inside its node, with thumbnails, and a
     focus rectangle dragged on a thumbnail changes one line of `shots.csv`.

## 7. Shared machines: student work, and resetting between rotations

Eight students per machine, one after another, and none of them should be able
to damage or lose another's work. **Undecided, and it must be decided before
imaging** — it changes the folder layout, so it is not a workshop-morning fix.

The questions, in the order they have to be answered:

- **Where does a student's project live?** `projects/<name>/` under the pack is
  what every document assumes and what the Project node's picker reads. Eight
  folders side by side is the simplest thing that works; it also means every
  student can see and overwrite every other student's edit.
- **What is reset between rotations, and what is kept?** Renders accumulate in
  ComfyUI's `output/`, which is shared and unnamed. A student's reel must be
  identifiable and recoverable after they have left the seat.
- **How does a student take their work home?** They arrive with their own
  script, recording and images and should leave with the reel and the folder
  that produced it.

None of this needs code. It needs a decision written down here, and then the
folder made that way on machine A before it is imaged.

## 8. Known gaps in this document

- **Not yet executed on a clean machine** — see the status note at the top. This
  is still the largest gap and everything else is downstream of it.
- ~~The ComfyUI node layer is not built yet, so §6 verifies the core library and
  CLI.~~ **Closed 2026-08-21**: the nodes exist and §6 step 6 verifies them.
- Student work isolation and machine reset between rotations are unresolved —
  now §7, with the questions written out rather than deferred to another file.
- **The three numbers that size the exercise have never been measured on the
  rented hardware**: one clean render, one `archive_soft` render, one alignment
  from cold. §2 and §5 carry dev-machine figures standing in for them.
- The Whisper cache location and whether it survives imaging (§3.7) is written
  from inspection, not from having imaged a machine.

### Retired here, from `HARDENING.md`

Recorded so they are not rediscovered as open questions:

- **USB model distribution and museum-Wi-Fi download contention** — retired
  2026-07-28. They solved the sixteen-personal-machines problem, which no longer
  exists. Replaced by pre-seeding (§3.7).
- **Dependency audit against unknown hardware** — same reason, replaced by §3.
- **Armenian narration alignment** — dropped with translation, SPEC v3.1.
- **The subtitle font** — closed 2026-07-28. Share Tech Mono is vendored into
  `assets/fonts/` under SIL OFL 1.1 and resolves by default (§3.8).
- **`ComfyUI-Olm-DragCrop` redistribution licence** (`SURVEY.md §3`) — no longer
  blocks imaging. The focus picker in the shot-table widget does that job inside
  the pack, so the machine image does not need to carry a package it may not
  redistribute. If DragCrop is ever reinstated, the licence question comes back
  with it.
- **Local-vs-Cloud behaviour differences** — not a machine-setup concern.
  They live in `GAPS.md` (#4 content-addressed uploads, #5 zeroed telemetry),
  which is where the two recorded so far already are.
- **An explicit local model path for `nodes/align.py`** — a code item, not a
  provisioning one. It is worth doing for reproducibility and it makes §3.7
  trivial, but it is now the pack's business rather than this document's.
