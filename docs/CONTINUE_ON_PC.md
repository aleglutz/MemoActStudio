# Moving the reel back to the Windows machine

Written 2026-08-17, after a fortnight of work on a MacBook. The repository is
the same one the Windows install has always had at
`ComfyUI\custom_nodes\MemoActStudio`; what follows brings it up to date without
losing anything, and takes about fifteen minutes, most of it a git pull and one
rebuild command.

## What actually has to travel

Almost nothing. The rule this project has followed since the first move applies
again: **outputs are rebuilt, not copied** — a copied output can silently
disagree with the inputs it claims to come from.

| | where it is | travels? |
|---|---|---|
| every code and text change (14 commits) | git | **yes — `git push` / `git pull`** |
| `narration.wav` | not versioned | **yes — the only irreplaceable file** |
| `images/New_York_May-8_1945.jpg` | not versioned | **yes — added on the Mac** |
| `images/GIoS_Wehrmacht_Signed_Ru_p2.jpg` | not versioned | **yes — added on the Mac** |
| `sources/narration_master.aac` | not versioned | optional, it is the original of the WAV |
| `maps/*`, `composites/*` | not versioned | no — one command rebuilds them |
| `generated/*`, `out/*` | not versioned | no — `generate_shots.py` and `render_reel.py` make them |
| the `.venv` on the Mac | — | no. Windows uses ComfyUI's embedded Python |

Everything else in `images/` and `video/` came *from* the Windows machine in the
first place and is already there.

## 1. On the Mac, before you leave it

```bash
cd ~/Documents/MemoActs/MemoActStudio
git status                 # expect a clean tree
git log --oneline origin/main..HEAD
git push
```

The log should list about eight commits, ending at `e2290b1` ("1:09 arrives at
the handshake; 1:58 carries its source"). If `git status` shows anything
uncommitted, commit it first — `_to_delete/` and
`archive/script_with_appended_tail.md` are the two known untracked leftovers and
neither needs to travel.

Then copy three files off the machine by whatever route you prefer:

```
projects/legends_of_surrender/narration.wav
projects/legends_of_surrender/images/New_York_May-8_1945.jpg
projects/legends_of_surrender/images/GIoS_Wehrmacht_Signed_Ru_p2.jpg
```

`narration.wav` is 31 MB and is the one file in this project that cannot be
regenerated from anything else.

## 2. On the PC, in PowerShell

```powershell
cd C:\Users\Aleg\beehAIve\ComfyUI-Easy-Install\ComfyUI-Easy-Install\ComfyUI\custom_nodes\MemoActStudio
git status
git pull
```

If the Windows tree has uncommitted changes from before the Mac trip, commit or
stash them *before* pulling. Line endings are not a hazard: `.gitattributes`
froze the repository to LF in August precisely for this move.

Put the three files in place:

```
projects\legends_of_surrender\narration.wav
projects\legends_of_surrender\images\New_York_May-8_1945.jpg
projects\legends_of_surrender\images\GIoS_Wehrmacht_Signed_Ru_p2.jpg
```

**Exactly one `narration.*` may sit in the project folder.** The generator looks
for `narration.mp3` first and otherwise takes whichever `narration.*` it finds,
so if an older one is still there, move it into `sources\`.

## 3. Check the environment before spending a render on it

Everything below runs on ComfyUI's embedded Python, never a system one:

```powershell
$py = "C:\Users\Aleg\beehAIve\ComfyUI-Easy-Install\ComfyUI-Easy-Install\python_embeded\python.exe"
& $py -c "import stable_whisper, num2words, numpy, PIL; print('deps ok')"
ffmpeg -filters | findstr subtitles
```

The second command must print a line. An ffmpeg without libass renders every
frame and *then* fails at the mux — the most expensive place to discover it.
(On the Mac this bit: Homebrew's core formula no longer ships libass. The
Windows build has always had it, so this is a check, not a task.)

One thing that no longer matters: `torchaudio.info` was removed in torchaudio
2.9 and used to break alignment. The length of the narration is read with
ffprobe now, so the torchaudio version is irrelevant on this machine.

## 4. Rebuild the generated media — one command

```powershell
& $py tools\rebuild_media.py --project projects\legends_of_surrender
```

That runs the five builds recorded in `projects\legends_of_surrender\REBUILD.md`
— two animated map plates, the France plate with the Reims pin, two stacked
stills, and the page-move clip — with the exact arguments, so nothing depends on
retyping sixteen keyframes into PowerShell. `REBUILD.md` remains the
authoritative record of what each one is and why; the script only spares you the
quoting.

Expect about a minute and a half in total, and one warning:

    WARNING the path magnifies a page to 2.60x its own pixels

That is deliberate and recorded — the act's first page is a 1024x1410 scan and
the shot reads it at 27 lines to the frame. `UPSCALE.md` forbids *silent*
enlargement, not enlargement.

## 5. Align and render

```powershell
& $py tools\generate_shots.py --project projects\legends_of_surrender --lang en
& $py tools\render_reel.py    --project projects\legends_of_surrender
```

The first run may download the Whisper model again if this machine's cache was
cleared. Alignment takes a couple of minutes; the render is about 4 945 frames.

## 6. What the output should say

`generated\report.txt`:

- **20 shots**, none `[ESTIMATED]`, confidence between 0.63 and 0.91
- narration duration **164.82 s**, total frames **4 945**
- **no** `cue … matches no block` warnings — the shot list and the script agree
- six enlargement warnings, the largest being the Treptow frame at x2.24

The render prints `video 164.833 s vs narration 164.821 s (drift +12 ms)`. That
is frame quantisation, not a fault.

Then watch for the four things changed last:

1. captions across the **middle** of the frame, not the bottom
2. their plate at **0.80** — check it against the black-and-white shots
3. **1:09** pushing in to Truman and Churchill's handshake
4. **1:58** carrying `S. Loznitsa, Victory Day, 2018` under its Berlin tag, for
   the whole shot

## 7. Still open, and nothing to do with the move

- The Loznitsa frame is quoted with a credit but **not cleared**. `SOURCES.md`
  is the record; the rights question is unanswered.
- `New_York_May-8_1945.jpg` has no entry in `SOURCES.md` at all, which by that
  file's own rule means unchecked rather than clear.
- `docs\PLAN.md` still reads as of 2026-08-10: it marks A1/A2 done and does not
  know that C1–C3 landed. Item **B** — several shots per narration block — is
  genuinely still open.
- Upscaling the act scans is planned on this machine. When it happens, divide
  every `s` in the page-move command by the upscale factor; the framing does not
  move.
