"""Voiceover post-processing — "this is my voice, as I want it heard".

Workflow 1 of three (`docs/PLAN.md`). It ends where the reel begins: the voice
is authored once, here, and **alignment listens to the result**. Every timing in
the reel is measured against the recording Align heard, so nothing after Align
can re-time the voice without invalidating all of them. That is why this stage
is first and why it is a workflow of its own rather than a branch of the reel
graph — the alignment cache keys on the recording's mtime, and a chain that
rewrites the recording on every Run buys a 90-second re-alignment for turning an
EQ knob.

Everything here works on one take at a time: float32 `[channels, samples]` plus
a sample rate, in and out. **The rate and the channel count are never changed**
— unlike `sfx.py`, whose bed is deliberately forced to 44.1 kHz stereo. This is
the master recording, and it reaches the project in whatever it was authored in.

The DSP is pedalboard (Rubber Band time-stretch + JUCE DSP), scipy and
pyloudnorm. All three are imported lazily, so a machine that has not run
`pip install -r requirements.txt` yet still loads the pack and fails with a
sentence naming the missing package instead of taking every other node down
with it — see `docs/WORKSHOP_MACHINE_SETUP.md` §3.3, where pedalboard is called
out as a compiled wheel to check *before* the September image is made.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Guards a division by an amplitude that may legitimately be zero.
_EPS = 1e-9

#: Denoise methods, in the order the widget offers them.
METHODS = ["spectral_gate", "noise_gate"]

#: Scale degrees in semitones from the root, for Auto-Tune.
SCALES = {
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
}

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

#: pyloudnorm's own floor: BS.1770 integrates 400 ms blocks and cannot measure
#: a take shorter than one of them.
MIN_LOUDNESS_S = 0.4

#: How to install a missing package, for machines where the reflex — running
#: `pip` in a shell — installs into a different interpreter and changes nothing.
_PIP = ("<ComfyUI-Easy-Install>\\python_embeded\\python.exe -m pip install")


class MissingDependency(RuntimeError):
    """A package this stage needs is not installed in *this* Python."""


def _pedalboard():
    try:
        import pedalboard
    except ImportError as exc:                              # pragma: no cover
        raise MissingDependency(
            f"pedalboard is not installed in the Python ComfyUI runs on. "
            f"Install it with:  {_PIP} pedalboard") from exc
    return pedalboard


def _scipy_signal():
    try:
        from scipy import signal
    except ImportError as exc:                              # pragma: no cover
        raise MissingDependency(
            f"scipy is not installed in the Python ComfyUI runs on — it "
            f"normally ships with ComfyUI, so this install is unusual. "
            f"Install it with:  {_PIP} scipy") from exc
    return signal


def _pyloudnorm():
    try:
        import pyloudnorm
    except ImportError as exc:                              # pragma: no cover
        raise MissingDependency(
            f"pyloudnorm is not installed in the Python ComfyUI runs on. "
            f"Install it with:  {_PIP} pyloudnorm") from exc
    return pyloudnorm


def db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _envelope(detector, sample_rate: int, time_ms: float):
    """One-pole envelope follower; vectorised, so it stays fast on long files."""
    lfilter = _scipy_signal().lfilter
    alpha = float(np.exp(-1.0 / max(sample_rate * time_ms / 1000.0, 1.0)))
    return lfilter([1.0 - alpha], [1.0, -alpha], detector)


def _contiguous(item):
    return np.ascontiguousarray(item, dtype=np.float32)


def pitch_time(item, sample_rate: int, *, pitch_semitones: float,
               tempo_factor: float):
    """Independent tempo and pitch change (Rubber Band, formant preserving)."""
    if abs(tempo_factor - 1.0) < 1e-6 and abs(pitch_semitones) < 1e-6:
        return item
    return _pedalboard().time_stretch(
        _contiguous(item),
        sample_rate,
        stretch_factor=float(tempo_factor),
        pitch_shift_in_semitones=float(pitch_semitones),
        high_quality=True,
        preserve_formants=True,
    )


def de_ess(item, sample_rate: int, *, freq: int, threshold_db: float,
           ratio: float):
    """Band-limited downward compression on the sibilance range."""
    signal = _scipy_signal()
    nyquist = sample_rate / 2.0
    cutoff = min(float(freq), nyquist * 0.99) / nyquist
    sos = signal.butter(2, cutoff, btype="highpass", output="sos")

    high = signal.sosfilt(sos, item, axis=-1).astype(np.float32)
    low = item - high
    # Link channels so the stereo image does not shift when gain is pulled.
    detector = np.abs(high).max(axis=0)
    env = _envelope(detector, sample_rate, time_ms=40.0)
    env_db = 20.0 * np.log10(np.maximum(env, _EPS))
    over_db = np.maximum(env_db - float(threshold_db), 0.0)
    reduction_db = -over_db * (1.0 - 1.0 / float(ratio))
    gain = np.power(10.0, reduction_db / 20.0).astype(np.float32)
    return low + high * gain[None, :]


def compress(item, sample_rate: int, *, threshold_db: float, ratio: float,
             attack_ms: float, release_ms: float, makeup_gain_db: float):
    """Level-evening compressor with makeup gain."""
    pedalboard = _pedalboard()
    board = pedalboard.Pedalboard([
        pedalboard.Compressor(
            threshold_db=float(threshold_db),
            ratio=float(ratio),
            attack_ms=float(attack_ms),
            release_ms=float(release_ms),
        ),
        pedalboard.Gain(gain_db=float(makeup_gain_db)),
    ])
    return board(_contiguous(item), sample_rate, reset=True)


def normalize_peak(item, *, peak_dbfs: float):
    """Scale so the loudest sample lands exactly on `peak_dbfs`."""
    peak = float(np.abs(item).max()) if item.size else 0.0
    if peak <= _EPS:
        return item
    return item * (db_to_lin(peak_dbfs) / peak)


def denoise(item, sample_rate: int, *, method: str, strength: float):
    """Gentle broadband noise reduction that keeps room tone intact."""
    if strength <= 0.0:
        return item
    if method == "noise_gate":
        pedalboard = _pedalboard()
        board = pedalboard.Pedalboard([
            pedalboard.NoiseGate(
                threshold_db=-60.0 + 25.0 * float(strength),
                ratio=1.5 + 4.0 * float(strength),
                attack_ms=1.0,
                release_ms=100.0,
            )
        ])
        return board(_contiguous(item), sample_rate, reset=True)
    return _spectral_gate(item, sample_rate, float(strength))


def _spectral_gate(item, sample_rate: int, strength: float):
    signal = _scipy_signal()
    n_samples = item.shape[-1]
    nperseg, noverlap = 2048, 1536
    _, _, spec = signal.stft(item, fs=sample_rate, nperseg=nperseg,
                             noverlap=noverlap, axis=-1)
    mag = np.abs(spec)
    # Quiet percentile per frequency bin approximates the steady noise floor.
    floor = np.percentile(mag, 10, axis=-1, keepdims=True)
    threshold = floor * (1.0 + 6.0 * strength)
    # Wiener-style soft mask -- avoids the musical artefacts of a hard gate.
    mask = (mag ** 2) / (mag ** 2 + threshold ** 2 + _EPS)
    _, cleaned = signal.istft(spec * mask, fs=sample_rate, nperseg=nperseg,
                              noverlap=noverlap, time_axis=-1, freq_axis=-2)
    cleaned = np.atleast_2d(np.asarray(cleaned, dtype=np.float32))
    if cleaned.shape[-1] < n_samples:
        cleaned = np.pad(cleaned, ((0, 0), (0, n_samples - cleaned.shape[-1])))
    return cleaned[:, :n_samples]


def track_f0(mono, sample_rate: int, hop: int, frame: int, fmin: float,
             fmax: float):
    """YIN pitch tracking. Returns per-frame f0 in Hz, NaN where unvoiced.

    Written out here rather than pulled from librosa, whose numba paths are
    broken against the NumPy in this env.
    """
    tau_min = max(int(sample_rate / fmax), 2)
    tau_max = min(int(sample_rate / fmin), frame // 2)
    window = frame - tau_max
    if window < 64 or len(mono) < frame:
        return np.zeros(0), hop

    n_frames = 1 + (len(mono) - frame) // hop
    out = np.full(n_frames, np.nan)
    taus = np.arange(tau_min, tau_max + 1)
    nfft = 1 << int(np.ceil(np.log2(frame + window)))

    for i in range(n_frames):
        x = mono[i * hop: i * hop + frame]
        if np.sqrt(np.mean(x * x)) < 1e-3:      # silence
            continue
        x = x - x.mean()
        head = x[:window]
        energy_head = float(np.dot(head, head))
        cumulative = np.concatenate(([0.0], np.cumsum(x * x)))
        energy_shifted = cumulative[taus + window] - cumulative[taus]
        corr = np.fft.irfft(
            np.fft.rfft(x, nfft) * np.conj(np.fft.rfft(head, nfft)), nfft
        )[taus]
        diff = energy_head + energy_shifted - 2.0 * corr
        # cumulative mean normalised difference (the "Y" in YIN)
        norm = diff * np.arange(1, len(diff) + 1) / np.maximum(np.cumsum(diff), 1e-12)

        below = np.flatnonzero(norm < 0.15)
        if len(below):
            # First dip under the threshold, then walk to the bottom of it.
            # Taking the global minimum instead would land on 2x the period
            # (the classic YIN octave error); taking the first index under the
            # threshold lands on the dip's leading edge, where the parabolic
            # step below is meaningless.
            k = int(below[0])
            while k + 1 < len(norm) and norm[k + 1] < norm[k]:
                k += 1
        else:
            k = int(np.argmin(norm))
        if norm[k] > 0.6:                        # too aperiodic to trust
            continue
        # parabolic interpolation for sub-sample period accuracy
        if 0 < k < len(diff) - 1:
            a, b, c = diff[k - 1], diff[k], diff[k + 1]
            denom = a - 2 * b + c
            shift = 0.5 * (a - c) / denom if abs(denom) > 1e-20 else 0.0
        else:
            shift = 0.0
        out[i] = sample_rate / (taus[k] + shift)
    return out, hop


def auto_tune(item, sample_rate: int, *, key: str, scale: str,
              retune_ms: float, strength: float, max_correction: float,
              preserve_formants: bool):
    """Pull drifting pitch toward a scale.

    NOT a hard T-Pain snap. The Rubber Band backend follows a pitch curve
    faithfully only up to roughly 1-2 Hz (measured: correlation 0.95 at 1 Hz,
    0.72 at 2 Hz, 0.00 at 8 Hz). Speech moves at syllable rate, 4-8 Hz, so
    asking for an instant snap produces artefacts rather than tuning -- which is
    why `retune_ms` floors at 150 instead of 0.
    """
    if strength <= 0.0:
        return item

    lfilter = _scipy_signal().lfilter
    pedalboard = _pedalboard()
    degrees = np.array(SCALES[scale], dtype=np.float64)
    root = float(KEYS.index(key))
    # pedalboard ignores pitch changes more frequent than 1024 samples, so
    # tracking any finer just throws detail away
    hop, frame = 1024, 2048

    n_samples = item.shape[-1]
    mono = item.mean(axis=0).astype(np.float64)
    f0, hop_used = track_f0(mono, sample_rate, hop, frame, fmin=55.0, fmax=500.0)
    if len(f0) == 0:
        return item

    voiced = ~np.isnan(f0)
    correction = np.zeros(len(f0), dtype=np.float64)
    if voiced.any():
        midi = 69.0 + 12.0 * np.log2(f0[voiced] / 440.0)
        # distance from the root, folded into one octave
        rel = np.mod(midi - root, 12.0)
        # nearest allowed degree, wrapping across the octave seam
        cand = np.concatenate([degrees - 12.0, degrees, degrees + 12.0])
        nearest = cand[np.argmin(np.abs(rel[:, None] - cand[None, :]), axis=1)]
        delta = np.clip(nearest - rel, -max_correction, max_correction) * strength
        # Carry the curve across unvoiced gaps instead of dropping to zero.
        # Toggling between a correction and 0 every few frames is far faster
        # than the stretcher can track and just adds noise.
        correction = np.interp(np.arange(len(f0)), np.flatnonzero(voiced), delta)

    frame_rate = sample_rate / float(hop_used)
    alpha = float(np.exp(-1.0 / max(frame_rate * retune_ms / 1000.0, 1e-6)))
    correction = lfilter([1.0 - alpha], [1.0, -alpha], correction)

    # per-frame correction -> per-sample curve pedalboard can consume
    centres = np.arange(len(correction)) * hop_used + frame / 2.0
    per_sample = np.interp(
        np.arange(n_samples), centres, correction, left=0.0, right=0.0
    ).astype(np.float64)

    shifted = pedalboard.time_stretch(
        _contiguous(item),
        sample_rate,
        stretch_factor=1.0,
        pitch_shift_in_semitones=per_sample,
        high_quality=True,
        preserve_formants=bool(preserve_formants),
    )
    # a varying curve makes the stretcher drift a few ms; this audio is the
    # reel's master clock, so pin the length back to the input
    if shifted.shape[-1] > n_samples:
        shifted = shifted[:, :n_samples]
    elif shifted.shape[-1] < n_samples:
        shifted = np.pad(shifted, ((0, 0), (0, n_samples - shifted.shape[-1])))
    return shifted.astype(np.float32)


@dataclass(frozen=True)
class Loudness:
    """What a meter reads off one take."""

    lufs: float
    peak_db: float
    duration: float
    sample_rate: int
    channels: int

    @property
    def measured(self) -> bool:
        return self.duration >= MIN_LOUDNESS_S

    def __str__(self) -> str:
        loudness = (f"{self.lufs:.2f} LUFS" if self.measured
                    else f"n/a (needs {MIN_LOUDNESS_S}s)")
        return (f"{loudness} | peak {self.peak_db:.2f} dBFS | "
                f"{self.duration:.2f}s | {self.sample_rate} Hz | "
                f"{self.channels}ch")


def measure_loudness(item, sample_rate: int) -> Loudness:
    """ITU-R BS.1770 integrated loudness, with the sample peak beside it."""
    duration = item.shape[-1] / float(sample_rate)
    peak_db = 20.0 * np.log10(max(float(np.abs(item).max()), _EPS))
    if duration < MIN_LOUDNESS_S:
        lufs = float("-inf")
    else:
        lufs = float(_pyloudnorm().Meter(sample_rate).integrated_loudness(item.T))
    return Loudness(lufs=lufs, peak_db=peak_db, duration=duration,
                    sample_rate=int(sample_rate), channels=int(item.shape[0]))
