"""`sfx.csv` — the sound design, kept out of the shot table.

The reel already carries two decisions per shot: what is *said* (`script.md`,
ground truth) and what is *seen* (`shots.csv`, the edit). Sound design is a
third: what is *heard* under the voice — pages turning, footsteps down a
corridor, a door pulled shut, a shutter. It is a separate file for the same
reason `shots.csv` is separate from the script: it changes on its own schedule,
long after the words are fixed, and re-doing it must never risk the text.

Format — a header row, one row per sound, `#` opens a comment. Every column but
`prompt` is optional and a blank cell means the default:

    shot,at,dur,gain,fade,duck,loop,file,seed,prompt,notes
    3,,2.5,-14,0.05 0.6,8,,,,pages of an old book turning slowly close dry paper,
    0:41,-0.3,1.2,-9,,10,,,,a heavy wooden door slams shut in a stone hallway,
    ,0:00,,-26,2 3,4,yes,room_tone.wav,,,empty museum hall room tone

`shot` addresses the shot the sound belongs to, by **number** or by the **cue
timecode** written in the script — the same two handles `shots.csv` uses, and
cues are the safer one for the same reason: inserting a line renumbers shots,
but a cue still points at the line it was written for. Leave `shot` blank and
`at` becomes an absolute position in the reel, which is what an ambience bed
that ignores the edit wants.

`at` is where the sound starts relative to the shot, in seconds, and it may be
negative: a door slam usually lands a beat *before* the cut it motivates.

`dur` is how long the sound is — what gets generated, and what gets played. Left
blank it is the shot's own length, capped at `MAX_SECONDS`. A sound is allowed
to outlast its shot; tails are not a mistake.

`gain` is in dB and it is negative, because this layer sits *under* a voice.
`fade` is `in out` in seconds (one number sets both). `duck` is how far this
sound steps back while the narrator is actually speaking, in dB — the one
automatic mix move, and the reason the layer never fights the voice.

`loop` repeats a short file to fill `dur`, which is how twelve seconds of room
tone comes out of a three-second recording.

`file` names the recording under `sources/sfx/`. Left blank, it is derived from
the row so that generating and mixing agree without anyone naming anything; the
generator writes the name back into this column, together with the `seed` that
produced it, so a take can be reproduced or deliberately re-rolled.

Nothing here touches the narration. The bed this module builds is a separate
track, and the narration reaches the mux exactly as it was recorded — that is a
project non-negotiable (SPEC §5.6) and it is enforced by construction: the only
signal these functions ever modify is the sound effects layer.
"""
from __future__ import annotations

import csv
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .shotlist import parse_timecode, write_csv

#: Where recordings live, generated or found. Beside `images/` and `maps/`,
#: because a plate the tool drew and a scan a person found are the same kind of
#: thing to a shot — and so are a generated slam and a recorded one.
SFX_DIR = "sources/sfx"

#: The mix runs at the sample rate the narration is delivered at and the audio
#: model generates at. Everything is resampled here on the way in.
SAMPLE_RATE = 44100

#: Longest single sound. Stable Audio Open generates up to 47 s; past that a
#: request is a bed, and a bed loops.
MAX_SECONDS = 47.0

#: Defaults for the cells left blank. A sound effect under a voice-over is
#: quiet, opens fast, closes slowly, and steps back while the voice is present.
DEFAULT_GAIN_DB = -14.0
DEFAULT_FADE_IN = 0.02
DEFAULT_FADE_OUT = 0.25
DEFAULT_DUCK_DB = 8.0

#: The ducking detector: speech is present when the narration is above this,
#: and the step down takes this long to arrive and this long to release.
DUCK_FLOOR_DB = -40.0
DUCK_ATTACK_S = 0.03
DUCK_RELEASE_S = 0.30

COLUMNS = ("shot", "at", "dur", "gain", "fade", "duck", "loop", "file",
           "seed", "prompt", "notes")

_TRUE = {"1", "yes", "y", "true", "t", "on", "loop"}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Cue:
    """One row of `sfx.csv`, already typed.

    `row` is the index of the row in the file, and it is what the generator and
    the mixer agree on: the graph selects a cue by position in this list, and
    the file name derived below is a function of that position, so two nodes
    running minutes apart still mean the same sound.
    """
    row: int = 0
    key: str = ""                       # the `shot` cell as written
    index: int | None = None            # 1-based shot number, if given that way
    cue: float | None = None            # cue timecode, if given that way
    at: float = 0.0                     # offset from the shot, or absolute
    dur: float | None = None            # None = the shot's own length
    gain_db: float = DEFAULT_GAIN_DB
    fade_in: float = DEFAULT_FADE_IN
    fade_out: float = DEFAULT_FADE_OUT
    duck_db: float = DEFAULT_DUCK_DB
    loop: bool = False
    file: str = ""
    seed: int | None = None
    prompt: str = ""
    notes: str = ""

    @property
    def stem(self) -> str:
        """The recording's name when the row does not give one.

        Derived from the row number and the first words of the prompt, so a
        folder of takes reads as a shot list rather than as a hash dump.
        """
        words = [w for w in _SLUG_RE.sub("-", self.prompt.lower()).split("-")
                 if w]
        slug = ""
        for w in words:                     # whole words only — a name cut in
            if len(slug) + len(w) + 1 > 40:  # the middle reads as corruption
                break
            slug = w if not slug else slug + "-" + w
        return f"{self.row + 1:02d}_{slug or 'sfx'}"

    @property
    def filename(self) -> str:
        return self.file.strip() or f"{self.stem}.wav"


@dataclass
class Placed:
    """A cue with its questions answered: when, how long, and from which file."""
    cue: Cue
    shot_id: int | None
    t_start: float
    duration: float
    path: Path | None                   # None = nothing recorded yet

    @property
    def t_end(self) -> float:
        return self.t_start + self.duration


@dataclass
class CueTable:
    """`sfx.csv` as written — header, rows, comments and all.

    Round-trippable on purpose, exactly like `shotlist.ShotTable`: the file is
    the author's, an unknown column is theirs to keep, and a node that writes a
    generated filename back into one cell must not quietly reformat the other
    ten.
    """
    fieldnames: list[str] = field(default_factory=lambda: list(COLUMNS))
    rows: list[dict[str, str]] = field(default_factory=list)


def read_table(path: Path) -> CueTable:
    """Read `sfx.csv`. A missing file is an empty table, not an error."""
    if not path.exists():
        return CueTable()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        names = list(reader.fieldnames or COLUMNS)
    lowered = [(n or "").strip().lower() for n in names]
    for c in COLUMNS:                   # a file written before a column existed
        if c not in lowered:
            names.append(c)
    return CueTable(fieldnames=names, rows=rows)


def write_table(path: Path, table: CueTable) -> Path:
    """Write `sfx.csv` back, through the crash-safe path `shots.csv` uses.

    A sound design is as hand-made and as unregenerable as an edit decision,
    and Save SFX rewrites this file from inside a graph run — which is exactly
    where an interruption lands.
    """
    return write_csv(path, table.fieldnames,
                     ({k: (row.get(k) or "") for k in table.fieldnames}
                      for row in table.rows))


def parse_text(text: str) -> CueTable:
    """A table typed into a text box rather than read off disk.

    The Sound Design node holds the table in a widget, which means a person can
    paste four lines with no header at all. Accept that: if the first line does
    not look like a header, the canonical column order is assumed.
    """
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return CueTable()
    head = [c.strip().lower() for c in next(csv.reader([lines[0]]))]
    if "prompt" in head or "shot" in head:
        body, names = lines[1:], head
    else:
        body, names = lines, list(COLUMNS)
    rows = [dict(zip(names, r)) for r in csv.reader(body)]
    return CueTable(fieldnames=list(names), rows=rows)


def to_text(table: CueTable) -> str:
    """The table as the widget shows it — header first, rows as written."""
    out = [",".join(table.fieldnames)]
    for row in table.rows:
        out.append(",".join(_quote(row.get(k) or "") for k in table.fieldnames))
    return "\n".join(out)


def _quote(cell: str) -> str:
    needs = any(ch in cell for ch in (",", '"', "\n"))
    return '"' + cell.replace('"', '""') + '"' if needs else cell


def template(doc: dict) -> CueTable:
    """A starter table: one commented row per shot, carrying what it says.

    Deliberately all comments. An empty file teaches nothing about the format,
    and a file full of live rows would generate eleven sounds nobody asked for
    the first time somebody presses Run.
    """
    table = CueTable()
    for s in doc.get("shots", []):
        text = (s.get("text") or "").strip()
        head = (text[:60] + "…") if len(text) > 60 else (text or "(silent)")
        table.rows.append({"shot": "# " + str(s["id"]), "notes": head})
    return table


def cues_from_table(table: CueTable) -> tuple[list[Cue], list[str]]:
    """Type the rows. Comments and blank lines drop out; bad cells warn."""
    cues: list[Cue] = []
    warnings: list[str] = []
    for n, raw in enumerate(table.rows):
        row = {(k or "").strip().lower(): (v or "").strip()
               for k, v in raw.items() if k is not None}
        key = row.get("shot", "")
        if key.startswith("#"):
            continue
        if not any(row.get(c) for c in COLUMNS):
            continue
        cue = Cue(row=n, key=key, prompt=row.get("prompt", ""),
                  file=row.get("file", ""), notes=row.get("notes", ""))
        if key:
            if key.isdigit():
                cue.index = int(key)
            else:
                cue.cue = parse_timecode(key)
                if cue.cue is None:
                    warnings.append(
                        "row " + str(n + 1) + ": " + repr(key) + " is neither "
                        "a shot number nor a cue timecode; ignored")
                    continue
        cue.at = _number(row.get("at"), 0.0, n, "at", warnings,
                         timecode=not key)
        dur = row.get("dur", "")
        cue.dur = None if not dur else _number(dur, None, n, "dur", warnings)
        cue.gain_db = _number(row.get("gain"), DEFAULT_GAIN_DB, n, "gain",
                              warnings)
        cue.duck_db = _number(row.get("duck"), DEFAULT_DUCK_DB, n, "duck",
                              warnings)
        cue.fade_in, cue.fade_out = _fades(row.get("fade", ""), n, warnings)
        cue.loop = row.get("loop", "").lower() in _TRUE
        seed = row.get("seed", "")
        cue.seed = int(seed) if seed.lstrip("-").isdigit() else None
        if not cue.prompt and not cue.file:
            warnings.append(
                "row " + str(n + 1) + ": neither a prompt nor a file — there "
                "is nothing to make and nothing to play")
            continue
        cues.append(cue)
    return cues, warnings


def _number(value, default, n: int, col: str, warnings: list[str],
            timecode: bool = False):
    value = (value or "").strip()
    if not value:
        return default
    if timecode:
        parsed = parse_timecode(value)
        if parsed is not None:
            return parsed
    try:
        return float(value)
    except ValueError:
        warnings.append("row " + str(n + 1) + ": " + col + "=" + repr(value)
                        + " is not a number; using " + str(default))
        return default


def _fades(value: str, n: int, warnings: list[str]) -> tuple[float, float]:
    parts = [p for p in re.split(r"[,\s/]+", value.strip()) if p]
    if not parts:
        return DEFAULT_FADE_IN, DEFAULT_FADE_OUT
    try:
        nums = [max(0.0, float(p)) for p in parts]
    except ValueError:
        warnings.append("row " + str(n + 1) + ": fade=" + repr(value)
                        + " is not one or two numbers; using the defaults")
        return DEFAULT_FADE_IN, DEFAULT_FADE_OUT
    return (nums[0], nums[0]) if len(nums) == 1 else (nums[0], nums[1])


#: Columns the generator writes and a person does not. They are the record of
#: what was actually made, so a table typed somewhere else must not silently
#: throw them away — see `carry_generated`.
GENERATED = ("file", "seed")


def carry_generated(table: CueTable, on_disk: CueTable) -> CueTable:
    """Keep what was generated, when the rows come from somewhere else.

    The Sound Design node holds the table in a box, and the box wins over the
    file — which is right for everything a person writes and wrong for the two
    cells the generator writes back. Without this, every run of the node
    overwrote `file` and `seed` with the blanks the box still had, and the seed
    of a take somebody liked was gone one run later. Observed on a live run,
    2026-08-24, which is why the rule is here and not in a comment.

    Carried by row position, and only when the prompt still matches: a rewritten
    prompt describes a different sound, so the recording made for the old one is
    stale and losing its name is the correct outcome.
    """
    for i, row in enumerate(table.rows):
        if i >= len(on_disk.rows):
            break
        was = on_disk.rows[i]
        if _cell(row, "prompt").strip() != _cell(was, "prompt").strip():
            continue
        for column in GENERATED:
            if not _cell(row, column).strip() and _cell(was, column).strip():
                row[_column(table, column)] = _cell(was, column)
    return table


def _cell(row: dict[str, str], name: str) -> str:
    for key, value in row.items():
        if (key or "").strip().lower() == name:
            return value or ""
    return ""


def stamp(table: CueTable, cue: Cue, *, filename: str,
          seed: int | None = None) -> CueTable:
    """Record what was actually generated, in the row that asked for it.

    The generator names the file; the mixer has to find it minutes later, in a
    different run, possibly after ComfyUI restarted. Writing the name back into
    the table is what makes the two halves of the workflow one workflow.
    """
    if 0 <= cue.row < len(table.rows):
        row = table.rows[cue.row]
        row[_column(table, "file")] = filename
        if seed is not None:
            row[_column(table, "seed")] = str(seed)
    return table


def _column(table: CueTable, name: str) -> str:
    """The header cell for a column, however the author capitalised it."""
    for field_name in table.fieldnames:
        if (field_name or "").strip().lower() == name:
            return field_name
    table.fieldnames.append(name)
    return name


def resolve(project: Path, doc: dict, cues: list[Cue]
            ) -> tuple[list[Placed], list[str]]:
    """Answer each cue's three questions against the shot table.

    Where it starts, how long it runs, and which file it plays. A cue that
    addresses no shot is a warning and is dropped — a sound placed at an
    invented time is worse than a missing one, because it will be heard and not
    understood.
    """
    shots = doc.get("shots", [])
    by_index = {s["id"]: s for s in shots}
    by_cue: dict[float, dict] = {}
    for s in shots:
        c = s.get("cue")
        if c is not None:
            by_cue.setdefault(float(c), s)
    total = float(doc.get("duration_s") or 0.0)

    placed: list[Placed] = []
    warnings: list[str] = []
    for cue in cues:
        shot = None
        if cue.index is not None:
            shot = by_index.get(cue.index)
            if shot is None:
                warnings.append(
                    "row " + str(cue.row + 1) + ": no shot " + str(cue.index)
                    + "; this table has 1.." + str(len(shots)))
                continue
        elif cue.cue is not None:
            shot = by_cue.get(cue.cue)
            if shot is None:
                warnings.append(
                    "row " + str(cue.row + 1) + ": no shot is cued at "
                    + repr(cue.key) + "; check the script's timecodes")
                continue

        if shot is None:                       # absolute placement in the reel
            t_start = max(0.0, cue.at)
            length = total
        else:
            t_start = max(0.0, float(shot["t_start"]) + cue.at)
            length = float(shot["t_end"]) - float(shot["t_start"])

        duration = cue.dur if cue.dur is not None else min(length, MAX_SECONDS)
        if duration <= 0:
            warnings.append("row " + str(cue.row + 1) + ": duration is "
                            + format(duration, ".2f") + "s; nothing to place")
            continue

        path = project / SFX_DIR / cue.filename
        placed.append(Placed(cue=cue, shot_id=shot["id"] if shot else None,
                             t_start=t_start, duration=duration,
                             path=path if path.exists() else None))
    return placed, warnings


# --------------------------------------------------------------------------
# Signals. Everything below deals in float32 [channels, samples] at SAMPLE_RATE.
# --------------------------------------------------------------------------

def decode(path: Path, sr: int = SAMPLE_RATE, channels: int = 2) -> np.ndarray:
    """Any audio file the project can hold, as float32 [channels, samples].

    Through ffmpeg rather than a decoding library, for two reasons: ffmpeg is
    already a hard requirement of the render, and it reads the mp3, m4a and wav
    a narration arrives as with one code path instead of three.
    """
    from .render import ffmpeg_exe
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path),
           "-f", "f32le", "-acodec", "pcm_f32le",
           "-ac", str(channels), "-ar", str(sr), "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError("could not decode " + path.name + ": "
                           + proc.stderr.decode("utf-8", "replace")[-400:])
    data = np.frombuffer(proc.stdout, dtype=np.float32)
    if data.size == 0:
        raise RuntimeError(path.name + " decoded to no audio at all")
    return data.reshape(-1, channels).T.copy()


def write_wav(path: Path, data: np.ndarray, sr: int = SAMPLE_RATE) -> Path:
    """Write float [channels, samples] as 24-bit PCM.

    24-bit and not 16: this layer is mixed a dozen dB down and then attenuated
    again under the voice, and quantisation noise that is inaudible at full
    scale is not inaudible after 20 dB of gain reduction. `wave` is in the
    standard library, so the pack gains no dependency for it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(np.asarray(data, dtype=np.float32).T, -1.0, 1.0)
    ints = np.round(clipped * 8388607.0).astype("<i4").reshape(-1)
    # int32 little-endian, then drop every fourth (most significant) byte.
    raw = np.frombuffer(ints.tobytes(), dtype=np.uint8).reshape(-1, 4)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(int(data.shape[0]))
        fh.setsampwidth(3)
        fh.setframerate(sr)
        fh.writeframes(raw[:, :3].tobytes())
    return path


def fit(signal: np.ndarray, samples: int, loop: bool) -> np.ndarray:
    """Make a recording exactly `samples` long — by looping, or by ending."""
    if signal.shape[1] == samples:
        return signal
    if signal.shape[1] > samples:
        return signal[:, :samples]
    if not loop:
        out = np.zeros((signal.shape[0], samples), dtype=np.float32)
        out[:, :signal.shape[1]] = signal
        return out
    reps = int(np.ceil(samples / signal.shape[1]))
    return np.tile(signal, (1, reps))[:, :samples]


def envelope(signal: np.ndarray, sr: int = SAMPLE_RATE, *,
             floor_db: float = DUCK_FLOOR_DB, attack: float = DUCK_ATTACK_S,
             release: float = DUCK_RELEASE_S) -> np.ndarray:
    """Where the voice is, as 0..1 per sample.

    A gate rather than a follower: what the mix needs to know is *is the
    narrator speaking*, not how loudly. A follower makes the sound effects
    breathe with every syllable, which is audible and awful; a gate with a fast
    attack and a slow release steps out of the way once and comes back once.
    """
    mono = signal.mean(axis=0)
    win = max(1, int(sr * 0.02))
    pad = (-len(mono)) % win
    frames = np.pad(mono, (0, pad)).reshape(-1, win)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    open_ = (20.0 * np.log10(rms + 1e-12) > floor_db).astype(np.float32)
    gate = np.repeat(open_, win)[:len(mono)]

    # One-pole smoothing, attack rising and release falling. Vectorising this
    # is possible and unreadable; a 150 s narration is 6.6 M samples and the
    # loop below costs a few seconds once per bed.
    a = float(np.exp(-1.0 / max(1.0, attack * sr)))
    r = float(np.exp(-1.0 / max(1.0, release * sr)))
    out = np.empty_like(gate)
    level = 0.0
    for i in range(gate.shape[0]):
        target = float(gate[i])
        coeff = a if target > level else r
        level = target + coeff * (level - target)
        out[i] = level
    return out


def render_bed(placed: list[Placed], total_s: float, *,
               narration: Path | None = None, master_db: float = 0.0,
               sr: int = SAMPLE_RATE) -> tuple[np.ndarray, list[str]]:
    """Mix the placed cues into one stereo track the length of the reel.

    The narration is *read* here and never written: it supplies the ducking
    envelope and nothing else. What comes back is the sound effects layer alone,
    which is what lets the mux add it to an untouched voice track.
    """
    notes: list[str] = []
    n = max(1, int(round(total_s * sr)))
    bed = np.zeros((2, n), dtype=np.float32)

    duck = None
    if narration is not None and any(p.cue.duck_db > 0 for p in placed):
        env = envelope(decode(narration, sr), sr)
        duck = np.zeros(n, dtype=np.float32)
        duck[:min(n, len(env))] = env[:n]

    for p in placed:
        if p.path is None:
            notes.append("row " + str(p.cue.row + 1) + ": no recording yet for "
                         + p.cue.filename + " — generate it, or name a file")
            continue
        try:
            clip = decode(p.path, sr)
        except RuntimeError as exc:
            notes.append("row " + str(p.cue.row + 1) + ": " + str(exc))
            continue

        want = int(round(p.duration * sr))
        if not p.cue.loop and clip.shape[1] < want * 0.5:
            notes.append(
                "row " + str(p.cue.row + 1) + ": " + p.cue.filename + " is "
                + format(clip.shape[1] / sr, ".1f") + "s against "
                + format(p.duration, ".1f") + "s asked for — the rest is "
                "silence. Set loop=yes for a bed.")
        clip = fit(clip, want, p.cue.loop) * _shape(want, p.cue.fade_in,
                                                    p.cue.fade_out, sr)
        clip = clip * (10.0 ** (p.cue.gain_db / 20.0))

        start = int(round(p.t_start * sr))
        end = min(n, start + want)
        if start >= n:
            notes.append("row " + str(p.cue.row + 1) + ": starts at "
                         + format(p.t_start, ".2f") + "s, past the end of the "
                         "reel (" + format(total_s, ".2f") + "s); dropped")
            continue
        if end < start + want:
            notes.append("row " + str(p.cue.row + 1) + ": runs "
                         + format((start + want - end) / sr, ".2f")
                         + "s past the end of the reel; the tail is cut")
        piece = clip[:, :end - start]
        if duck is not None and p.cue.duck_db > 0:
            floor = 10.0 ** (-p.cue.duck_db / 20.0)
            piece = piece * (1.0 - (1.0 - floor) * duck[start:end])
        bed[:, start:end] += piece

    bed *= 10.0 ** (master_db / 20.0)
    peak = float(np.abs(bed).max()) if bed.size else 0.0
    if peak > 0.99:
        # Scaling rather than clipping: the bed is one layer of a mix, and a
        # clipped layer stays clipped through everything downstream.
        bed *= 0.99 / peak
        notes.append("the bed peaked at "
                     + format(20 * np.log10(peak), "+.1f") + " dBFS and was "
                     "pulled down " + format(20 * np.log10(peak / 0.99), ".1f")
                     + " dB — the gains in the table are louder than they read")
    return bed, notes


def _shape(samples: int, fade_in: float, fade_out: float,
           sr: int) -> np.ndarray:
    """A fade envelope, cosine rather than linear so the ends are inaudible."""
    env = np.ones(samples, dtype=np.float32)
    a = min(int(fade_in * sr), samples)
    b = min(int(fade_out * sr), samples - a if samples > a else 0)
    if a > 0:
        env[:a] = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, a,
                                                 dtype=np.float32))
    if b > 0:
        env[samples - b:] = 0.5 + 0.5 * np.cos(
            np.linspace(0.0, np.pi, b, dtype=np.float32))
    return env
