# Workshop machine setup — September offline workshop

Provisioning procedure for the **two rented machines** (SPEC §0, `HARDENING.md`).
Build machine A by following this exactly, verify with §6, then image it onto
machine B. Do not hand-install twice — divergence between the two machines is
the failure mode that costs workshop time on the day.

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
   .\python_embeded\python.exe -m pip install stable-ts num2words
   ```

   ⚠ `stable-ts` pulls `openai-whisper` and depends on torch, which ComfyUI
   already ships — so the increment should be small. Verify it does not
   reinstall or upgrade torch; if it tries, stop and pin instead, because a
   torch swap can break the ComfyUI install itself.

4. **ffmpeg with libass.** Confirm before relying on it:

   ```
   ffmpeg -hide_banner -version | findstr enable-libass
   ffmpeg -hide_banner -filters | findstr subtitles
   ```

   Both must produce output. A build without libass fails at *render* time, not
   install time — the worst moment to discover it. Put ffmpeg on `PATH`;
   `memoacts_core.render.ffmpeg_exe()` looks there first.

5. **Pre-seed the Whisper model** so nothing downloads during the workshop. Run
   one alignment on machine A (§6 step 2) — the model is fetched once and cached
   into the user profile, and the image then carries it.

   ⚠ Confirm where it caches and that the cache survives imaging; if the image
   is applied under a different user account, the cache path may not carry over.

6. **Fonts: nothing to do.** The pack ships Share Tech Mono under SIL OFL 1.1 in
   `assets/fonts/`, and burn-in resolves against that directory by default. Do
   *not* install the font system-wide — the point is that a fresh machine
   renders identical captions with no provisioning step.

## 4. What the facilitator runs vs what students run

Alignment needs the speech model and is a *preparation* step, not a workshop
step (SPEC §4, prepared-inputs model):

```
python tools/generate_shots.py --project projects/<name> --lang en
```

→ `generated/shots.json`, a file a human can read and edit. Students start from
there. Keep this in mind when imaging: students never need to run alignment, so
a model problem on machine B is a facilitator problem, not a workshop blocker.

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

   Expect: 4 shots, 415 frames, 13.833 s, drift within a few ms, and one
   `UserWarning` about `03_small.png` being enlarged 1.92× — **that warning is
   correct behaviour**, not a fault. The fixture deliberately contains a source
   too small for the output so the resolution guard is exercised.

2. **Alignment produces timings** (this also seeds the model, §3.5):

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

## 7. Known gaps in this document

- Not yet executed on a clean machine — see the status note at the top.
- The ComfyUI node layer is not built yet, so §6 verifies the **core library and
  CLI**, not the nodes students will actually use. Extend §6 once the pack's
  nodes exist.
- Student work isolation and machine reset between rotations are unresolved
  (`HARDENING.md`).
