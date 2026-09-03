"""Effect-family nodes (SPEC §5.4) — wraps `memoacts_core.effects`.

Each family is one node that *adds itself* to an effect stack, so they chain:

    Preset ─→ Grade ─→ Grain ─→ Shake ─→ Apply Effects ─→ (SHOTS)

Chaining rather than one god-node keeps the graph readable and lets a shot take
just the families it needs. A later node in the chain overrides the same family
set earlier — including one set by a preset, which is the intended way to take
a preset and adjust a single knob.
"""
from __future__ import annotations

import copy

from comfy_api.latest import io

from ..memoacts_core import effects as fx
from .types import Effects, Shots


def _extend(stack: fx.EffectStack | None, **families) -> fx.EffectStack:
    """Copy the incoming stack and set one family on it."""
    out = copy.deepcopy(stack) if stack is not None else fx.EffectStack()
    for name, value in families.items():
        setattr(out, name, value)
    return out


class MemoActsEffectPreset(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsEffectPreset",
            display_name="MemoActs — Effect Preset",
            category="memoacts/effects",
            description="A named combination of the six families. Chain "
                        "family nodes after it to adjust individual knobs.",
            inputs=[
                io.Combo.Input("preset", options=sorted(fx.PRESETS),
                               default="archive_soft"),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, preset):
        return io.NodeOutput(fx.preset(preset))


class MemoActsGrade(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsGrade",
            display_name="MemoActs — Grade",
            category="memoacts/effects",
            description="Colour grade. A .cube LUT, if given, replaces the "
                        "parametric knobs entirely.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.Float.Input("exposure", default=0.0, min=-4.0, max=4.0,
                               step=0.05, tooltip="In stops."),
                io.Float.Input("contrast", default=0.0, min=-1.0, max=1.0,
                               step=0.01),
                io.Float.Input("saturation", default=0.0, min=-1.0, max=2.0,
                               step=0.01,
                               tooltip="-1 is fully desaturated."),
                io.Float.Input("temperature", default=0.0, min=-1.0, max=1.0,
                               step=0.01, tooltip="-1 cool … +1 warm."),
                io.Float.Input("lift", default=0.0, min=0.0, max=0.5,
                               step=0.01,
                               tooltip="Raises blacks — the faded-archive look."),
                io.String.Input("lut_path", default="",
                                tooltip="Optional .cube LUT; overrides the "
                                        "knobs above."),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, exposure, contrast, saturation, temperature, lift,
                lut_path, effects=None):
        return io.NodeOutput(_extend(effects, grade=fx.Grade(
            exposure=exposure, contrast=contrast, saturation=saturation,
            temperature=temperature, lift=lift, lut_path=lut_path)))


class MemoActsGrain(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsGrain",
            display_name="MemoActs — Grain",
            category="memoacts/effects",
            description="Film grain. Note that grain is expensive to encode: "
                        "the renderer switches x264 to `-tune grain` and caps "
                        "the bitrate when any shot carries it.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.Float.Input("amount", default=0.03, min=0.0, max=0.3,
                               step=0.005,
                               tooltip="Noise amplitude. Above ~0.06 reads as "
                                       "static rather than grain."),
                io.Float.Input("size", default=1.8, min=1.0, max=8.0, step=0.1,
                               tooltip="Grain scale in output pixels."),
                io.Boolean.Input("coloured", default=False,
                                 tooltip="Off = luminance grain, the filmic "
                                         "default and roughly half the cost."),
                io.Int.Input("seed", default=0, min=0, max=2 ** 31 - 1),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, amount, size, coloured, seed, effects=None):
        return io.NodeOutput(_extend(effects, grain=fx.Grain(
            amount=amount, size=size, coloured=coloured, seed=seed)))


class MemoActsShake(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsShake",
            display_name="MemoActs — Shake",
            category="memoacts/effects",
            description="Camera shake. Applied to the crop window inside the "
                        "source, so it is free and can never expose an edge.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.Float.Input("amplitude_px", default=4.0, min=0.0, max=60.0,
                               step=0.5,
                               tooltip="Peak offset in SOURCE pixels — a large "
                                       "source needs a larger value for the "
                                       "same visible movement."),
                io.Float.Input("frequency", default=6.0, min=0.1, max=30.0,
                               step=0.1, tooltip="Oscillations per second."),
                io.Int.Input("seed", default=0, min=0, max=2 ** 31 - 1,
                             tooltip="Shifts the phase so two shots do not "
                                     "shake in step."),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, amplitude_px, frequency, seed, effects=None):
        return io.NodeOutput(_extend(effects, shake=fx.Shake(
            amplitude_px=amplitude_px, frequency=frequency, seed=seed)))


class MemoActsTexture(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsTexture",
            display_name="MemoActs — Texture",
            category="memoacts/effects",
            description="Blends a looping overlay. The path may be a still "
                        "image or a video clip; a clip is streamed and looped, "
                        "never loaded whole.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.String.Input("path", default=""),
                io.Float.Input("opacity", default=0.25, min=0.0, max=1.0,
                               step=0.01),
                io.Combo.Input("blend", options=list(fx.BLEND_MODES),
                               default="overlay"),
                io.Float.Input("speed", default=1.0, min=0.05, max=4.0,
                               step=0.05,
                               tooltip="<1 slows the clip down."),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, path, opacity, blend, speed, effects=None):
        return io.NodeOutput(_extend(effects, texture=fx.Texture(
            path=path, opacity=opacity, blend=blend, speed=speed)))


class MemoActsFrameOverlay(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsFrameOverlay",
            display_name="MemoActs — Frame Overlay",
            category="memoacts/effects",
            description="Composites an alpha PNG over everything — borders, "
                        "vignettes, dust plates.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.String.Input("path", default=""),
                io.Float.Input("opacity", default=1.0, min=0.0, max=1.0,
                               step=0.01),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, path, opacity, effects=None):
        return io.NodeOutput(_extend(effects, frame=fx.FrameOverlay(
            path=path, opacity=opacity)))


class MemoActsSharpen(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSharpen",
            display_name="MemoActs — Sharpen",
            category="memoacts/effects",
            description="Unsharp mask. Runs last in the pipeline so it is not "
                        "amplifying the grain added before it.",
            inputs=[
                Effects.Input("effects", optional=True),
                io.Float.Input("amount", default=0.4, min=0.0, max=2.0,
                               step=0.05),
                io.Float.Input("radius", default=1.2, min=0.1, max=10.0,
                               step=0.1),
                io.Int.Input("threshold", default=3, min=0, max=255),
            ],
            outputs=[Effects.Output("EFFECTS")],
        )

    @classmethod
    def execute(cls, amount, radius, threshold, effects=None):
        return io.NodeOutput(_extend(effects, sharpen=fx.Sharpen(
            amount=amount, radius=radius, threshold=threshold)))


class MemoActsApplyEffects(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsApplyEffects",
            display_name="MemoActs — Apply Effects",
            category="memoacts/effects",
            description="Attaches an effect stack to one shot, or to every "
                        "shot. Chain several to give shots different looks.",
            inputs=[
                Shots.Input("shots"),
                Effects.Input("effects"),
                io.Int.Input("shot_id", default=0, min=0, max=999,
                             tooltip="1-based shot number, or 0 for all."),
            ],
            outputs=[Shots.Output("SHOTS")],
        )

    @classmethod
    def execute(cls, shots, effects, shot_id):
        # Shallow-copy the wrapper and the effect map, but NOT the shot table:
        # the doc is untouched here, and deep-copying it per effect node would
        # be pure waste on a long reel.
        out = dict(shots)
        out["effects"] = dict(shots.get("effects") or {})

        ids = [s["id"] for s in out["doc"]["shots"]]
        if shot_id and shot_id not in ids:
            raise ValueError(f"no shot {shot_id}; this table has 1..{len(ids)}")
        for sid in ids:
            if shot_id in (0, sid):
                out["effects"][sid] = effects
        return io.NodeOutput(out)
