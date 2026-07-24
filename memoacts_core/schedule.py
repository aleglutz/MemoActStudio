"""Motion schedules: per-frame crop rects for the list-map graph (proven in
the 2026-07-24 crux test) and, later, for the P2 motion engine (SPEC §5.3).

All rects are (x, y, w, h) in source pixels, 9:16 aspect, cosine-eased,
float-computed and rounded at the last step.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

ASPECT = 9 / 16
PRESETS = ("static", "zoom_in", "zoom_out", "pan_lr", "pan_rl", "pan_ud", "pan_du")


@dataclass
class Motion:
    preset: str = "static"
    rate: float = 0.06        # zoom fraction per shot (SPEC §5.2: slow zoom ~4-8 %)
    anchor: str = "center"    # center | top


@dataclass
class ShotSchedule:
    xs: list[int] = field(default_factory=list)
    ys: list[int] = field(default_factory=list)
    ws: list[int] = field(default_factory=list)
    hs: list[int] = field(default_factory=list)
    clamped: bool = False
    max_zoom: float = 1.0     # how far this source could zoom before < out_w

    def csv(self) -> dict[str, str]:
        j = lambda v: ",".join(map(str, v))
        return {"w": j(self.ws), "h": j(self.hs), "x": j(self.xs), "y": j(self.ys)}

    def chunks(self, max_frames: int) -> list["ShotSchedule"]:
        n = len(self.ws)
        if n <= max_frames:
            return [self]
        out = []
        for a in range(0, n, max_frames):
            b = min(a + max_frames, n)
            out.append(ShotSchedule(self.xs[a:b], self.ys[a:b], self.ws[a:b],
                                    self.hs[a:b], self.clamped, self.max_zoom))
        return out


def _ease(t: float) -> float:
    return (1 - math.cos(math.pi * t)) / 2


def base_window(src_w: int, src_h: int) -> tuple[float, float]:
    """Largest 9:16 window inside the source."""
    if src_w / src_h > ASPECT:
        return src_h * ASPECT, float(src_h)
    return float(src_w), src_w / ASPECT


def compute(src_w: int, src_h: int, n_frames: int, motion: Motion,
            out_w: int = 1080) -> ShotSchedule:
    """Per-frame crop rects. Resolution guard (SPEC §5.2): the crop window may
    never go below out_w pixels wide — rate is clamped, never silently upscaled."""
    w0, h0 = base_window(src_w, src_h)
    sched = ShotSchedule()
    sched.max_zoom = w0 / out_w

    rate = max(0.0, motion.rate)
    preset = motion.preset if motion.preset in PRESETS else "static"

    # guard: deepest window used by this preset is w0 * (1 - rate)
    min_w = w0 * (1 - rate) if preset != "static" else w0
    if min_w < out_w:
        rate = max(0.0, 1 - out_w / w0)
        sched.clamped = True

    for i in range(n_frames):
        t = _ease(i / (n_frames - 1)) if n_frames > 1 else 0.0
        if preset == "static":
            z = 1.0
        elif preset == "zoom_in":
            z = 1.0 - rate * t
        elif preset == "zoom_out":
            z = 1.0 - rate * (1 - t)
        else:  # pans hold the zoomed size and translate
            z = 1.0 - rate
        w = w0 * z
        h = w / ASPECT
        # anchor placement
        cx = src_w / 2
        cy = h0 / 2 if motion.anchor == "top" else src_h / 2
        x, y = cx - w / 2, cy - h / 2
        if preset in ("pan_lr", "pan_rl"):
            span = src_w - w
            p = t if preset == "pan_lr" else 1 - t
            x = span * p
        elif preset in ("pan_ud", "pan_du"):
            span = src_h - h
            p = t if preset == "pan_ud" else 1 - t
            y = span * p
        # clamp into source and round (even sizes for encoder friendliness)
        w_i = int(round(w / 2)) * 2
        h_i = int(round(h / 2)) * 2
        x_i = int(round(min(max(x, 0), src_w - w_i)))
        y_i = int(round(min(max(y, 0), src_h - h_i)))
        sched.ws.append(w_i)
        sched.hs.append(h_i)
        sched.xs.append(x_i)
        sched.ys.append(y_i)
    return sched


def default_motion(shot_index: int) -> Motion:
    """Zero-input defaults (SPEC §5.2): alternate direction, slow zoom."""
    cycle = ("zoom_in", "pan_lr", "zoom_out", "pan_rl")
    return Motion(preset=cycle[shot_index % len(cycle)], rate=0.06)


def frames_for(spans_s: list[tuple[float, float]], fps: int) -> list[int]:
    """Contiguous frame counts from span boundaries — cumulative rounding so
    the total exactly matches the timeline."""
    counts, prev = [], 0
    for _, t_end in spans_s:
        edge = int(round(t_end * fps))
        counts.append(max(edge - prev, 1))
        prev = edge
    return counts
