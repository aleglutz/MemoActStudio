"""Sound design — "what is heard under the voice" (SPEC §5.6).

The last stage of the reel, and the only one whose material does not exist yet
when the project folder is made: pages turning, footsteps down a corridor, a
door pulled shut, a shutter. SPEC §5.6 leaves two ways to get them and asks for
neither exclusively — a curated CC0 library, or generation with an open-weight
audio model. These four nodes take the second path and accept the first for
free: a cue whose `file` column names a recording somebody found plays exactly
like a cue whose sound was generated an hour ago, because by the time the mixer
runs there is only a wav on disk either way.

    Shot Table ─→ Sound Design ─→ SFX Prompt ─→ [ any text-to-audio graph ]
                       │                                     │
                       │                              Save SFX ─→ sources/sfx/
                       ↓
                    SFX Bed ─→ (audio) ─→ Render Reel

Sound Design is one sentence — "this scene needs a sound" — and the other three
are the loop that answers it. The middle two run once per sound, which ComfyUI
already has an idiom for: set the batch count to the number of cues and let
`index` increment itself. The bed is built once, at the end, from whatever is
on disk by then.

**The narration is never touched here.** The bed is a separate track; the mixer
reads the recording only to know where the voice is, and the mux adds the two
without re-timing either. That is the project non-negotiable, and it is what
makes ducking safe: the only signal ever attenuated is the sound effects layer.
"""
from __future__ import annotations

from pathlib import Path

import torch
from comfy_api.latest import io, ui

from .memoacts_core import sfx
from .memoacts_core.pipeline import (ProjectError, build_sfx_bed,
                                     console_progress, read_sound_design)
from .nodes_types import Shots, SfxCue, SfxCues

#: Appended to every prompt unless the widget is emptied. Stable Audio Open and
#: its relatives were trained on sound libraries, and a library recording is
#: what these words describe: one event, close, dry, nothing else in the room.
#: Without them the model reaches for music, which is never what a cue wants.
DEFAULT_STYLE = ("single sound effect, field recording, close mono source, "
                 "dry, clean, no music, no speech")

#: What to steer away from. "Room reverb" is on the list on purpose: the reel
#: places these sounds under a voice recorded in one acoustic, and a second
#: acoustic underneath it is the thing that makes a mix sound assembled.
DEFAULT_NEGATIVE = ("music, melody, singing, speech, voice, narration, "
                    "hiss, hum, distortion, low quality, heavy reverb")

#: Stable Audio Open's own floor. A latent shorter than this has too few tokens
#: to hold an event, and the node clamps rather than letting the sampler fail.
MIN_SECONDS = 1.0


class MemoActsSoundDesign(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSoundDesign",
            display_name="MemoActs — Sound Design",
            category="memoacts",
            description=(
                "The sound design as a table: one row per sound, saying which "
                "shot it belongs to, how long it is, how loud it sits under the "
                "voice, and — in words — what it is. Leave the box empty and it "
                "reads sfx.csv; type in it and it writes sfx.csv. Run it first: "
                "everything downstream works from the rows it resolves."
            ),
            is_output_node=True,
            inputs=[
                Shots.Input("shots"),
                io.String.Input(
                    "cues", multiline=True, default="",
                    tooltip="sfx.csv, editable here. Columns: shot, at, dur, "
                            "gain, fade, duck, loop, file, seed, prompt, notes. "
                            "A row starting with # is a comment. Empty means "
                            "'read the file'.",
                ),
                io.Boolean.Input(
                    "save_to_csv", default=True,
                    tooltip="Write what is in the box back to <project>/sfx.csv "
                            "so the sound design outlives this workflow.",
                ),
            ],
            outputs=[SfxCues.Output("SFX")],
        )

    @classmethod
    def fingerprint_inputs(cls, shots, cues, save_to_csv):
        """Re-read when `sfx.csv` changes underneath an empty widget."""
        if cues.strip():
            return "widget"
        try:
            project = Path(shots["project_dir"])
            return str((project / "sfx.csv").stat().st_mtime_ns)
        except (OSError, KeyError, TypeError):
            return "0"

    @classmethod
    def execute(cls, shots, cues, save_to_csv):
        project = Path(shots["project_dir"])
        doc = shots["doc"]
        # One call, and it is the same one `tools/render_reel.py --sfx` makes:
        # two doors onto one orchestration is the rule this pack is built to.
        design = read_sound_design(project, doc, text=cues,
                                   write=save_to_csv)
        placed, warnings = design.placed, list(design.warnings)

        lines = [str(design.csv), ""]
        if design.is_template:
            lines += [
                "No sound design yet — a starter table was written, one "
                "commented row per shot.",
                "Uncomment a row, write what the shot should sound like in "
                "`prompt`, and run again.",
                "",
            ]
        total = float(doc.get("duration_s") or 0.0)
        for p in placed:
            where = f"shot {p.shot_id:02d}" if p.shot_id else "absolute"
            have = "have" if p.path else "MISSING"
            lines.append(
                f"{_clock(p.t_start)}–{_clock(p.t_end)}  {where:>9}  "
                f"{p.duration:5.2f}s  {p.cue.gain_db:+6.1f} dB  "
                f"duck {p.cue.duck_db:4.1f}  {have:>7}  {p.cue.filename}")
            lines.append(f"{'':>34}{p.cue.prompt or '(from file)'}")
        if not placed:
            lines.append("no sound cues yet")
        else:
            missing = sum(1 for p in placed if p.path is None)
            lines += ["", f"{len(placed)} cue(s) over {_clock(total)} of reel; "
                          f"{missing} still to generate"]
        if warnings:
            lines.append("")
            lines += [f"warning: {w}" for w in warnings]

        return io.NodeOutput(
            {"project_dir": str(project), "doc": doc, "csv": str(design.csv),
             "cues": design.cues, "placed": placed},
            ui=ui.PreviewText("\n".join(lines)))


class MemoActsSfxPrompt(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSfxPrompt",
            display_name="MemoActs — SFX Prompt",
            category="memoacts",
            description=(
                "Hands one row of the sound design to a text-to-audio graph: "
                "the prompt, what to avoid, and how many seconds to make. Set "
                "the batch count to the number of cues and `index` walks the "
                "table on its own — one queued run generates the whole reel's "
                "sound."
            ),
            is_output_node=True,
            inputs=[
                SfxCues.Input("design"),
                io.Int.Input(
                    "index", default=1, min=1, max=999,
                    control_after_generate=True,
                    tooltip="Which cue, 1-based, in the order the table lists "
                            "them. Leave 'control after generate' on increment "
                            "and a batch walks every row.",
                ),
                io.Int.Input(
                    "seed", default=0, min=0, max=0xffffffffffffffff,
                    control_after_generate=True,
                    tooltip="Recorded into sfx.csv by Save SFX, so a take you "
                            "liked can be made again.",
                ),
                io.String.Input("style", multiline=True, default=DEFAULT_STYLE,
                                tooltip="Added to every prompt. This is what "
                                        "keeps the model making sound effects "
                                        "rather than music."),
                io.String.Input("negative", multiline=True,
                                default=DEFAULT_NEGATIVE),
            ],
            outputs=[
                io.String.Output(display_name="positive"),
                io.String.Output(display_name="negative"),
                io.Float.Output(display_name="seconds"),
                io.Int.Output(display_name="seed"),
                SfxCue.Output("CUE"),
            ],
        )

    @classmethod
    def execute(cls, design, index, seed, style, negative):
        cues = design["cues"]
        if not cues:
            raise ValueError(
                "the sound design has no rows yet — write a prompt into "
                f"{design['csv']}, or into the Sound Design node")
        if index > len(cues):
            raise ValueError(
                f"cue {index} of {len(cues)}: the table ends before it. Set the "
                f"batch count to {len(cues)}, not higher.")
        cue = cues[index - 1]
        placed = next((p for p in design["placed"] if p.cue.row == cue.row),
                      None)

        seconds = cue.dur if cue.dur is not None else (
            placed.duration if placed else sfx.MAX_SECONDS)
        seconds = max(MIN_SECONDS, min(float(seconds), sfx.MAX_SECONDS))
        positive = ", ".join(p for p in (cue.prompt.strip(), style.strip()) if p)

        lines = [f"cue {index} of {len(cues)}  (row {cue.row + 1} of sfx.csv)",
                 f"{seconds:.2f}s, seed {seed}",
                 f"-> sources/sfx/{cue.filename}",
                 "",
                 positive]
        return io.NodeOutput(positive, negative, seconds, seed,
                             {**design, "cue": cue, "seed": seed,
                              "seconds": seconds},
                             ui=ui.PreviewText("\n".join(lines)))


class MemoActsSaveSfx(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSaveSfx",
            display_name="MemoActs — Save SFX",
            category="memoacts",
            description=(
                "Writes the generated sound into the project's sources/sfx/ "
                "under the name its row asked for, and records that name and "
                "the seed back into sfx.csv — which is what lets the bed find "
                "it later, in another run, after a restart."
            ),
            is_output_node=True,
            inputs=[
                io.Audio.Input("audio"),
                SfxCue.Input("cue"),
                io.Float.Input(
                    "peak_dbfs", default=-1.0, min=-40.0, max=0.0, step=0.5,
                    tooltip="Normalise the take to this peak before saving, so "
                            "the gain column in the table means the same thing "
                            "for every sound. 0 saves it as generated.",
                ),
                io.Float.Input(
                    "head_db_below_peak", default=20.0, min=0.0, max=90.0,
                    step=1.0,
                    tooltip="Where the take really starts: the first moment "
                            "within this many dB of its own loudest point. "
                            "Everything before it is cut, so the sound lands "
                            "on the cue instead of after it. 90 keeps the take "
                            "whole.",
                ),
            ],
            outputs=[io.Audio.Output("audio")],
            # Declared for the same reason every stock save node declares them:
            # `ui.PreviewAudio` writes the workflow into the preview file, and
            # without these two `cls.hidden` is not populated to write from.
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
        )

    @classmethod
    def execute(cls, audio, cue, peak_dbfs, head_db_below_peak):
        payload = cue
        the_cue: sfx.Cue = payload["cue"]
        project = Path(payload["project_dir"])

        data = audio_to_numpy(audio)
        head = _onset(data, head_db_below_peak)
        if 0 < head < data.shape[1]:
            data = data[:, head:]
        peak = float(abs(data).max()) if data.size else 0.0
        if peak_dbfs < 0.0 and peak > 0.0:
            data = data * ((10.0 ** (peak_dbfs / 20.0)) / peak)

        path = project / sfx.SFX_DIR / the_cue.filename
        sfx.write_wav(path, data)

        table = sfx.read_table(Path(payload["csv"]))
        if table.rows:
            sfx.stamp(table, the_cue, filename=the_cue.filename,
                      seed=payload.get("seed"))
            sfx.write_table(Path(payload["csv"]), table)

        seconds = data.shape[1] / sfx.SAMPLE_RATE
        print(f"[MemoActs] sfx row {the_cue.row + 1}: {the_cue.filename}, "
              f"{seconds:.2f}s, {head / sfx.SAMPLE_RATE:.2f}s of head trimmed, "
              f"seed {payload.get('seed')}")

        saved = {"waveform": torch.from_numpy(data).unsqueeze(0),
                 "sample_rate": sfx.SAMPLE_RATE}
        return io.NodeOutput(saved, ui=ui.PreviewAudio(saved, cls=cls))


class MemoActsSfxBed(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSfxBed",
            display_name="MemoActs — SFX Bed",
            category="memoacts",
            description=(
                "Mixes every sound in the table into one track the length of "
                "the reel — placed, faded, and stepped back under the voice — "
                "and writes it to generated/sfx_bed.wav. Wire its output into "
                "Render Reel's sfx input. The narration is only listened to "
                "here, never changed."
            ),
            is_output_node=True,
            inputs=[
                SfxCues.Input("design"),
                io.Float.Input(
                    "master_gain_db", default=0.0, min=-40.0, max=12.0,
                    step=0.5,
                    tooltip="The whole layer up or down at once, after the "
                            "per-row gains. This is the knob to reach for "
                            "first when the sound design is 'too much'.",
                ),
                io.Boolean.Input(
                    "duck_under_voice", default=True,
                    tooltip="Step each sound back by its own duck value while "
                            "the narrator is speaking. Off makes the table's "
                            "gains audible on their own, which is how you "
                            "judge them.",
                ),
            ],
            outputs=[io.Audio.Output("sfx_bed")],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
        )

    @classmethod
    def execute(cls, design, master_gain_db, duck_under_voice):
        project = Path(design["project_dir"])
        doc = design["doc"]
        placed = design["placed"]
        total = float(doc.get("duration_s") or 0.0)

        try:
            out, notes = build_sfx_bed(project, doc, placed,
                                       master_db=master_gain_db,
                                       duck=duck_under_voice,
                                       progress=_say)
        except ProjectError as exc:
            raise ValueError(str(exc)) from exc

        played = [p for p in placed if p.path is not None]
        lines = [str(out), "",
                 f"{len(played)} of {len(placed)} cue(s) mixed over "
                 f"{_clock(total)}"]
        for p in played:
            lines.append(f"  {_clock(p.t_start)}  {p.duration:5.2f}s  "
                         f"{p.cue.gain_db:+6.1f} dB  {p.cue.filename}")
        for n in notes:
            lines.append(f"warning: {n}")

        audio = {"waveform": torch.from_numpy(sfx.decode(out)).unsqueeze(0),
                 "sample_rate": sfx.SAMPLE_RATE}
        return io.NodeOutput(audio, ui=ui.PreviewAudio(audio, cls=cls))


#: The pipeline's own phrasing, in the ComfyUI console. Deliberately not
#: reworded: the CLI prints these lines verbatim too, and two doors describing
#: the same fact differently is the drift this pack was restructured to make
#: impossible.
_say = console_progress("[MemoActs] ")


def _clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{seconds % 60:05.2f}"


def audio_to_numpy(audio: dict):
    """An AUDIO socket as float32 [channels, samples] at the mix rate.

    Shared with the render node, which accepts any AUDIO as its sound design
    layer — a bed built here, or a track a student loaded from a CC0 library
    with ComfyUI's own Load Audio. Both arrive as the same dict, and this is
    the one place that knows what is in it.
    """
    import numpy as np
    wave = audio["waveform"]
    if wave.ndim == 3:
        wave = wave[0]
    rate = int(audio.get("sample_rate", sfx.SAMPLE_RATE))
    if rate != sfx.SAMPLE_RATE:
        import torchaudio
        wave = torchaudio.functional.resample(wave, rate, sfx.SAMPLE_RATE)
    data = wave.detach().to("cpu", torch.float32).numpy()
    if data.shape[0] == 1:                  # mono take, stereo bed
        data = np.repeat(data, 2, axis=0)
    return np.ascontiguousarray(data[:2])


def audio_at_own_rate(audio: dict, *, keep_batch: bool = False):
    """An AUDIO socket as float32, at the rate and channels it arrived in.

    The other reading of the same socket is `audio_to_numpy` above, which
    resamples to 44.1 kHz and forces stereo — right for a layer about to be
    mixed, wrong for a voice about to be muxed. This one is the master
    recording: whatever the voice workflow produced is what lands in
    `sources/narration.wav`, and every timing in the reel is measured against
    it.

    `keep_batch` says which end of the batch dimension the caller wants. The
    voice nodes shape a whole batch of takes; the narration writer takes the
    first and writes one file.
    """
    wave = audio["waveform"]
    if wave.ndim == 1:                      # bare mono, no channel axis
        wave = wave[None, :]
    if keep_batch:
        if wave.ndim == 2:                  # [channels, samples]
            wave = wave[None, ...]
    elif wave.ndim == 3:                    # [batch, channels, samples]
        wave = wave[0]
    rate = int(audio.get("sample_rate") or sfx.SAMPLE_RATE)
    return wave.detach().to("cpu", torch.float32).numpy(), rate


#: Kept in front of the onset, so the attack transient survives the trim. An
#: event cut exactly at its threshold crossing loses its front edge, which is
#: most of what makes a slam sound like a slam.
PRE_ROLL_S = 0.02


def _onset(data, below_peak_db: float) -> int:
    """Where the take actually starts.

    A generated sound routinely opens with a second or two of *almost* nothing
    — not digital silence, so an absolute threshold does not find it, but the
    room the model imagined before the event happens. Measured against the
    take's own peak instead, the onset is where it sounds like it is: a page
    turn generated at 3 s came back with the pages at 1.75 s, and left alone it
    would have landed a second and a half after the cut it was written for.
    """
    import numpy as np
    if below_peak_db >= 90.0 or not data.size:
        return 0
    level = np.abs(data).max(axis=0)
    peak = float(level.max())
    if peak <= 0.0:
        return 0
    above = np.flatnonzero(level > peak * 10.0 ** (-below_peak_db / 20.0))
    if not above.size:
        return 0
    return max(0, int(above[0]) - int(PRE_ROLL_S * sfx.SAMPLE_RATE))
