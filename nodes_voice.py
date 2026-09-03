"""Voice nodes — "this is my voice, as I want it heard" (docs/PLAN.md §1).

The first of the three workflows, and the one with no project in it: a take
comes off a microphone, is shaped here, and leaves through `Set Narration`,
which is the only node in the pack that writes into `sources/`.

    Load Audio ─→ EQ 3-Band ─→ Pitch / Time ─→ De-esser ─→ Compressor
                  (stock)      "read faster"   "tame the   "even the level"
                                                S sounds"
                                                            ↓
                          Set Narration ←─ Normalize ←─ Loudness Meter
                          "into my project"  "peak -1"    "what did I make?"

Every node takes an AUDIO and returns an AUDIO, so the chain can be cut
anywhere and any node can be bypassed — which is how it is taught: run the
meter first, then add only what the meter says is wrong.

**The rate and the channel count are never changed here**, and neither is the
length, except by Pitch / Time, which is the node whose whole job is length.
That matters downstream: `Align` measures every timing in the reel against the
recording it hears, so this is the last stage that may move the voice in time.

The DSP is `memoacts_core.voice`; these classes are widgets, ranges and
tooltips, exactly as the rest of the pack is built. Batched AUDIO is handled
here rather than there — the core works one take at a time.
"""
from __future__ import annotations

import numpy as np
import torch
from comfy_api.latest import io, ui

from .memoacts_core import voice
from .nodes_audio import audio_at_own_rate

#: The voice workflow's own submenu. The reel nodes sit in `memoacts`; these
#: are a stage before it and are opened from a different graph, so they are one
#: level down rather than mixed into the same list.
CATEGORY = "memoacts/audio"


def _pack(items, sample_rate: int) -> dict:
    """A list of `[channels, samples]` arrays back into an AUDIO socket."""
    stacked = np.stack(items, axis=0).astype(np.float32, copy=False)
    return {"waveform": torch.from_numpy(stacked), "sample_rate": sample_rate}


def _per_take(audio: dict, fn) -> dict:
    """Apply `fn(item, sample_rate)` to every take in the batch.

    A missing DSP package becomes a `ValueError` here, which is how every other
    node in this pack hands a domain error to ComfyUI — the message already
    names the package and the pip command.
    """
    data, sample_rate = audio_at_own_rate(audio, keep_batch=True)
    try:
        return _pack([fn(item, sample_rate) for item in data], sample_rate)
    except voice.MissingDependency as exc:
        raise ValueError(str(exc)) from exc


class MemoActsAudioPitchTime(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioPitchTime",
            display_name="MemoActs — Pitch / Time",
            category=CATEGORY,
            description=(
                "Speeds up or slows down speech without changing pitch. "
                "tempo_factor 1.15 = 15% faster. The one node here that "
                "changes the length of the take, so it belongs before "
                "alignment and nowhere after it."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "pitch_semitones", default=0.0, min=-24.0, max=24.0,
                    step=0.1,
                    tooltip="Transpose without changing the speed. Formants "
                            "are preserved, so a semitone or two reads as the "
                            "same person rather than a chipmunk.",
                ),
                io.Float.Input(
                    "tempo_factor", default=1.0, min=0.5, max=2.0, step=0.01,
                    tooltip="Speed, with the pitch held. 1.15 is 15% faster — "
                            "the usual fix for a read that is careful but too "
                            "slow for a vertical reel.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, pitch_semitones, tempo_factor):
        return io.NodeOutput(_per_take(audio, lambda item, rate: voice.pitch_time(
            item, rate, pitch_semitones=pitch_semitones,
            tempo_factor=tempo_factor)))


class MemoActsAudioDeEsser(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioDeEsser",
            display_name="MemoActs — De-esser",
            category=CATEGORY,
            description=(
                "Tames harsh S sounds above `freq` without dulling the whole "
                "track: the band is compressed on its own and added back."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Int.Input(
                    "freq", default=7000, min=2000, max=16000, step=100,
                    tooltip="Where sibilance starts for this voice. Lower it "
                            "until the S stops stinging and no further — too "
                            "low takes the consonants with it.",
                ),
                io.Float.Input(
                    "threshold_db", default=-8.0, min=-60.0, max=0.0, step=0.5,
                    tooltip="The level, inside that band only, above which "
                            "gain is pulled.",
                ),
                io.Float.Input(
                    "ratio", default=3.0, min=1.0, max=20.0, step=0.1,
                    tooltip="How hard it is pulled. 3 is gentle; above 8 the S "
                            "disappears rather than softens.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, freq, threshold_db, ratio):
        return io.NodeOutput(_per_take(audio, lambda item, rate: voice.de_ess(
            item, rate, freq=freq, threshold_db=threshold_db, ratio=ratio)))


class MemoActsAudioVocalCompressor(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioVocalCompressor",
            display_name="MemoActs — Vocal Compressor",
            category=CATEGORY,
            description=(
                "Evens out loud and quiet passages so narration sits at a "
                "steady level under a phone speaker in a noisy room."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "threshold_db", default=-18.0, min=-60.0, max=0.0,
                    step=0.5,
                    tooltip="Above this level the gain starts coming down. "
                            "Set it where the loud lines are, not where the "
                            "peaks are.",
                ),
                io.Float.Input("ratio", default=3.0, min=1.0, max=20.0,
                               step=0.1),
                io.Float.Input(
                    "attack_ms", default=8.0, min=0.1, max=100.0, step=0.1,
                    tooltip="How fast it reacts. Below ~5 ms it starts eating "
                            "the front of consonants, which reads as a lisp.",
                ),
                io.Float.Input("release_ms", default=120.0, min=10.0,
                               max=1000.0, step=1.0),
                io.Float.Input(
                    "makeup_gain_db", default=4.0, min=-12.0, max=24.0,
                    step=0.5,
                    tooltip="Put back what the compression took off. Roughly "
                            "the gain reduction you asked for.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, threshold_db, ratio, attack_ms, release_ms,
                makeup_gain_db):
        return io.NodeOutput(_per_take(audio, lambda item, rate: voice.compress(
            item, rate, threshold_db=threshold_db, ratio=ratio,
            attack_ms=attack_ms, release_ms=release_ms,
            makeup_gain_db=makeup_gain_db)))


class MemoActsAudioNormalize(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioNormalize",
            display_name="MemoActs — Normalize (peak)",
            category=CATEGORY,
            description=(
                "Scales the take so its loudest sample lands exactly on "
                "`peak_dbfs`. Run it last — compression after it undoes the "
                "result."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Float.Input(
                    "peak_dbfs", default=-1.0, min=-30.0, max=0.0, step=0.1,
                    tooltip="-1 dBFS leaves the headroom the AAC encoder at "
                            "the end of the reel needs; 0 invites clipping "
                            "that only appears after the encode.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, peak_dbfs):
        return io.NodeOutput(_per_take(
            audio, lambda item, _rate: voice.normalize_peak(
                item, peak_dbfs=peak_dbfs)))


class MemoActsAudioSpeechDenoise(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioSpeechDenoise",
            display_name="MemoActs — Speech Denoise",
            category=CATEGORY,
            description=(
                "Reduces steady hiss and hum. Unlike a Demucs vocal isolation "
                "it does not strip everything that is not a voice, so the room "
                "the recording was made in survives."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Combo.Input("method", options=voice.METHODS,
                               default="spectral_gate"),
                io.Float.Input(
                    "strength", default=0.5, min=0.0, max=1.0, step=0.05,
                    tooltip="0 passes the take through untouched. Past ~0.7 "
                            "the noise floor starts breathing between words, "
                            "which is more distracting than the hiss was.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, method, strength):
        return io.NodeOutput(_per_take(audio, lambda item, rate: voice.denoise(
            item, rate, method=method, strength=strength)))


class MemoActsAudioAutoTune(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioAutoTune",
            display_name="MemoActs — Auto-Tune",
            category=CATEGORY,
            description=(
                "Gentle pitch correction toward a scale — tunes drift and adds "
                "a processed sheen. Lower `retune_ms` is stronger; below ~150 "
                "the stretcher cannot follow the curve and you get artefacts "
                "instead of tuning."
            ),
            inputs=[
                io.Audio.Input("audio"),
                io.Combo.Input("key", options=voice.KEYS, default="C"),
                io.Combo.Input("scale", options=list(voice.SCALES),
                               default="chromatic"),
                io.Float.Input(
                    "retune_ms", default=300.0, min=150.0, max=1500.0,
                    step=10.0,
                    tooltip="How quickly the correction follows the voice. "
                            "Speech moves at 4–8 Hz and the backend tracks to "
                            "about 1–2 Hz, which is why this floors at 150.",
                ),
                io.Float.Input("strength", default=0.7, min=0.0, max=1.0,
                               step=0.05),
                io.Float.Input(
                    "max_correction", default=2.0, min=0.5, max=12.0, step=0.5,
                    tooltip="Semitones. Caps how far a note may be moved, so a "
                            "mis-tracked octave cannot throw a word.",
                ),
                io.Boolean.Input("preserve_formants", default=True),
            ],
            outputs=[io.Audio.Output("audio")],
        )

    @classmethod
    def execute(cls, audio, key, scale, retune_ms, strength, max_correction,
                preserve_formants):
        return io.NodeOutput(_per_take(audio, lambda item, rate: voice.auto_tune(
            item, rate, key=key, scale=scale, retune_ms=retune_ms,
            strength=strength, max_correction=max_correction,
            preserve_formants=preserve_formants)))


class MemoActsAudioLoudnessMeter(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsAudioLoudnessMeter",
            display_name="MemoActs — Loudness Meter (LUFS)",
            category=CATEGORY,
            description=(
                "Measures integrated loudness (ITU-R BS.1770) and sample peak, "
                "and passes the audio through unchanged. Instagram and TikTok "
                "normalise to about -14 LUFS: land near it and the platform "
                "leaves the reel alone."
            ),
            is_output_node=True,
            inputs=[io.Audio.Input("audio")],
            outputs=[
                io.Audio.Output(display_name="audio"),
                io.String.Output(display_name="report"),
                io.Float.Output(display_name="lufs"),
            ],
        )

    @classmethod
    def execute(cls, audio):
        data, sample_rate = audio_at_own_rate(audio, keep_batch=True)
        try:
            reading = voice.measure_loudness(data[0], sample_rate)
        except voice.MissingDependency as exc:
            raise ValueError(str(exc)) from exc
        report = str(reading)
        return io.NodeOutput(audio, report, reading.lufs,
                             ui=ui.PreviewText(report))
