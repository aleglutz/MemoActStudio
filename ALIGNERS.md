# ALIGNERS.md — §5.1 aligner evaluation (English only)

Date: 2026-07-24, **rescoped 2026-07-28 (SPEC v3.1).** Status: **stable-ts recommended; bake-off retargeted and substantially de-risked.**

> **v3.1 rescope.** The project is English-only — translation moved out of scope, and `projects/sidur` is no longer the dev fixture. This removes most of what made the aligner choice hard:
> - **Russian is no longer a requirement.** RU boundary accuracy was the discriminator that justified keeping whisperx in the running; on English every candidate is at its strongest.
> - **Armenian is gone**, so MMS_FA's 1100-language coverage — its main advantage — no longer buys anything. Its CC-BY-NC weights were always a licence problem (§2.5). It drops to a distant fallback.
> - **RU inflected number expansion is gone** (SPEC §10, closed). English `num2words` suffices, modulo year-pair reading.
> - **The bake-off material changes**: the Sidur RU narration is replaced by the forthcoming English script + narration (SPEC §6.2), not yet delivered.
>
> Net effect: **stable-ts is now very likely sufficient and the bake-off is a confirmation, not a selection.** Do not let it block implementation — the `Aligner` interface (§5.1) already makes the engine swappable.

## Problem restated

Input: narration audio + verbatim script. Output: start/end timestamps per sentence/block. We never transcribe for content — the script is ground truth; only *timing* is computed. Failure mode budget: acceptance §6.1 asks total duration ±0.2 s; per-boundary error of ~±100–150 ms is invisible at 30 fps subtitling. Constraints from spec: RU + EN minimum (DE/FR/HY later), Python 3.11+, Windows-friendly (participants, September offline workshop), small dependency surface (§7), open-source (§2.5), CPU-sufficient (§3 Branch A).

## Candidates

### 1. stable-ts (`align()`) — **recommended primary**

| Criterion | Assessment |
|---|---|
| Fit to problem | **Exact.** `align()` force-aligns *known text* to audio using any Whisper model — no transcription step, no matching layer to write. Word-level output; silence-suppression snaps boundaries to speech gaps (good for sentence cuts). |
| RU / EN | Both first-class Whisper languages. DE/FR later: same path. HY: exists in Whisper but weak — see MMS fallback. |
| Deps | `pip install stable-ts` → openai-whisper + torch. **ComfyUI already ships torch**, so the increment is small. Windows: pure pip, no compiler. |
| Model download | Whisper `base` ≈ 145 MB / `small` ≈ 484 MB, auto-fetched once. ⚠ Tension with acceptance §6.8 "no model downloads" — see decision point below. |
| CPU | 2.5-min audio with `base`/`small` on CPU: expected well under real-time for align-only. To be measured in bake-off. |
| Digits/names («1974») | Whisper tokenizer models numbers as spoken; worst case a digit token gets interpolated timing → maps cleanly to our `timing: estimated` flag. Text on screen is verbatim script regardless. |
| License / maintenance | MIT / actively maintained (2026 releases). Whisper models MIT. **Entire chain open.** |

### 2. whisperx — runner-up / bake-off benchmark

Transcribe (faster-whisper) → wav2vec2 CTC alignment; ±50 ms word accuracy claimed. RU has a default align model (`jonatasgrosman/wav2vec2-large-xlsr-53-russian`, Apache-2.0); EN uses torchaudio models. To use *known* text we must transcribe then sequence-match script↔recognition, keeping timings — an extra layer we'd write and own. Documented limitation: wav2vec2 cannot timestamp digits/special characters (interpolated). Heavier deps (ctranslate2/faster-whisper; Windows wheels exist). License BSD (TBV). **Verdict:** more moving parts for the same output; keep in the bake-off as accuracy benchmark — if it beats stable-ts by a clear margin on RU boundaries, the matching layer is worth it.

### 3. torchaudio `MMS_FA` (same model behind `ctc-forced-aligner`) — fallback

True forced aligner in torchaudio itself — **zero new packages** in a ComfyUI env; 1100+ languages incl. RU and **HY** (future-proof for the 5-language course). Costs: text must be romanized (uroman) and digits expanded to words before alignment (RU number inflection — real preprocessing work); MMS weights are **CC-BY-NC-4.0** ⚠ — clashes with the open-source-end-to-end line the same way the NC Whisper node does. **Verdict:** fallback, and the likely HY answer later; include in bake-off if cheap.

### 4. MFA (Montreal Forced Aligner) — rejected

Gold-standard phone-level alignment; `russian_mfa` + EN models exist. But: conda-forge-only install (Kaldi), OOV names need G2P runs, digits must be pre-expanded, corpus-directory workflow. A phonetics-lab tool, not a shippable dependency for participant machines. (MIT, fine — weight is the problem.)

### 5. aeneas — rejected

Right *idea* (known-text DTW alignment, no ASR), wrong decade: last release 2017, tested through Python 3.5, C extension + eSpeak external dependency (Windows/py3.11 install is the known nightmare), sentence-level granularity coarser than neural aligners, AGPL-3.0, unmaintained.

## First empirical numbers — 2026-08-10, synthetic material

The bake-off has still not run on human narration, but a scratch track built
with Kokoro TTS gave the first accuracy measurement this project has ever had,
because every segment boundary was known exactly by construction.

Material: `projects/legends_of_surrender`, 18 blocks, 319 words, 149 s, English,
stable-ts `small`. Each line was synthesised separately and placed on the
script's own cue grid, so the true speech onset is known to the sample.

| | |
|---|---|
| median boundary error | **69 ms** |
| p95 | **136 ms** |
| max | 172 ms |
| threshold (§bake-off) | p95 ≤ 150 ms → **PASS** |

**Read this as an optimistic bound, not a validation.** Synthetic speech is
cleaner than a human read: even pacing, no breaths, no false starts, no room
tone. The human narration will be harder, and the number that matters is the
one measured on it.

Two measurement notes worth keeping, since both would silently distort a repeat:

- Compare against **speech onset**, not the segment file start. Kokoro emits
  ~45 ms of lead-in silence per segment; measuring from file start inflated
  every error by that much and turned a PASS into a FAIL on the first attempt.
- Undo the deliberate `shot_lead_ms` before comparing. The pipeline pulls every
  boundary 100 ms early by design (SPEC §5.2); that is a feature, not error.

## Recommendation

**stable-ts primary; whisperx as benchmark in the bake-off; MMS_FA as no-new-deps fallback and the future Armenian path.** Proportional fallback + `timing: estimated` (spec §5.1) wraps whichever engine loses confidence, so the choice is not load-bearing for robustness — only for accuracy and install weight, where stable-ts wins on both for RU/EN.

## Bake-off protocol (next step, before freezing)

**Retargeted 2026-07-28** — English material, and now a confirmation run rather than a selection.

1. Material: the forthcoming **English** narration + script (SPEC §6.2), awaited from the project owner; hand-mark boundaries once (±1 frame) as reference.
2. Run stable-ts `align()` (base + small models, CPU). Add whisperx **only if stable-ts fails the threshold** — on English there is no longer a reason to pay for the sequence-matching layer up front. MMS_FA is dropped from the bake-off (its multilingual advantage is moot and its weights are NC).
3. Metrics: per-boundary absolute error (median/p95), digit/date-adjacent boundary errors specifically, wall-clock on CPU.
4. Accept if p95 boundary error ≤ 150 ms and CPU runtime ≤ audio duration; else escalate to whisperx.

Note the environment shift (SPEC v3.1 §3): students run on Cloud, where alignment cannot run at all (no aligner node exists) — so this engine runs **only** on the facilitator's and the production machine, per the prepared-inputs model (§4). Participant install weight, which drove much of the original comparison, is no longer a criterion.

## Decision points for review

1. **Acceptance §6.8 "no model downloads":** every viable aligner needs a model (~150–500 MB, one-time, CPU-run). Strictest reading forces aeneas (rejected). Proposed amendment: *"no GPU-class/diffusion checkpoints; the aligner's speech model (≤500 MB, auto-fetched once, CPU-executed) is exempt."*
2. **NC licenses** (MMS weights; ComfyUI-Whisper teaching node): acceptable as demo/fallback under the grant's open-source commitment, or excluded entirely?
3. Confirm stable-ts as primary so `nodes_align.py` is designed around a direct-alignment API (with the engine behind an interface, per the fallback chain).
