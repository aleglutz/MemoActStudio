"""Motion schedules: per-frame crop rects for the list-map graph (proven in
the 2026-07-24 crux test) and, later, for the P2 motion engine (SPEC §5.3).

All rects are (x, y, w, h) in source pixels, 9:16 aspect, cosine-eased,
float-computed and rounded at the last step.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

ASPECT = 9 / 16
PRESETS = ("static", "zoom_in", "zoom_out", "pan_lr", "pan_rl", "pan_ud",
           "pan_du", "square_in", "fit")


@dataclass
class Motion:
    preset: str = "static"
    rate: float = 0.06        # zoom fraction per shot (SPEC §5.2: slow zoom ~4-8 %)
    anchor: str = "center"    # center | top
    #: Where in the source the shot is *about*, as `(cx, cy, w)` in fractions of
    #: the source: a centre plus the window's width. Height follows from 9:16.
    #:
    #: `rate` says how much the frame breathes; `focus` says what it ends on, and
    #: they answer different questions. A rate is a fraction of the whole frame —
    #: 4-8 % is a drift, and asking it to reach one face in a group photograph
    #: would mean a rate near 1.0, which the resolution guard would refuse
    #: anyway. So a shot that lands on a detail states the detail instead, and
    #: the preset decides the direction of travel: `zoom_in` opens wide and
    #: arrives here, `zoom_out` starts here and pulls back, `static` holds it.
    #: `rate` is unused when a focus is set. Pans ignore it (see `compute`).
    focus: tuple[float, float, float] | None = None


@dataclass
class ShotSchedule:
    xs: list[int] = field(default_factory=list)
    ys: list[int] = field(default_factory=list)
    ws: list[int] = field(default_factory=list)
    hs: list[int] = field(default_factory=list)
    clamped: bool = False
    max_zoom: float = 1.0     # how far this source could zoom before < out_w
    #: Height the image occupies in the *output* frame, per frame. Empty for
    #: every preset but `square_in`, and empty means "fills the frame", which is
    #: what every other preset does and what the renderer assumed outright
    #: before this existed. Width is always the full output width.
    dst_hs: list[int] = field(default_factory=list)

    def csv(self) -> dict[str, str]:
        j = lambda v: ",".join(map(str, v))
        out = {"w": j(self.ws), "h": j(self.hs), "x": j(self.xs), "y": j(self.ys)}
        if self.dst_hs:
            out["dst_h"] = j(self.dst_hs)
        return out

    def chunks(self, max_frames: int) -> list["ShotSchedule"]:
        n = len(self.ws)
        if n <= max_frames:
            return [self]
        out = []
        for a in range(0, n, max_frames):
            b = min(a + max_frames, n)
            out.append(ShotSchedule(self.xs[a:b], self.ys[a:b], self.ws[a:b],
                                    self.hs[a:b], self.clamped, self.max_zoom,
                                    self.dst_hs[a:b]))
        return out


def _ease(t: float) -> float:
    return (1 - math.cos(math.pi * t)) / 2


def base_window(src_w: int, src_h: int, aspect: float = ASPECT
                ) -> tuple[float, float]:
    """Largest window of `aspect` (w/h) inside the source. Defaults to 9:16."""
    if src_w / src_h > aspect:
        return src_h * aspect, float(src_h)
    return float(src_w), src_w / aspect


#: Presets a focus can steer. The pans are excluded by construction: their whole
#: shape is "hold one size and traverse", so a destination window would either
#: contradict the traversal or replace it.
FOCUSABLE = ("static", "zoom_in", "zoom_out")


def focus_window(src_w: int, src_h: int, focus: tuple[float, float, float],
                 w0: float, out_w: int = 1080, aspect: float = ASPECT
                 ) -> tuple[float, float, float, float, bool]:
    """Resolve `(cx, cy, w)` fractions into a pixel window `(w, h, cx, cy)`.

    Returns the window plus whether it had to be widened. Two ceilings apply and
    both are the resolution guard in different clothes: the window may not be
    narrower than the output (that would enlarge), and it may not be wider than
    the base 9:16 window (there is no more image to show). The centre is left
    alone here — `compute` clamps the rect into the source once it has one.
    """
    cxf, cyf, wf = focus
    w = min(wf * src_w, w0)
    clamped = False
    if w < out_w:
        w = min(float(out_w), w0)
        clamped = True
    h = w / aspect
    if h > src_h:                      # taller than the source: fall back to it
        h = float(src_h)
        w = h * aspect
    return w, h, cxf * src_w, cyf * src_h, clamped


def focus_limits(src_w: int, src_h: int, out_w: int = 1080,
                 aspect: float = ASPECT) -> tuple[float, float]:
    """The `w` fractions a focus may usefully name, as `(narrowest, widest)`.

    The same two ceilings `focus_window` enforces, said before the fact instead
    of after it: no narrower than the output (that would enlarge) and no wider
    than the base window (there is no more image). A picker needs them in
    advance to stop the person drawing a rectangle it will then quietly widen —
    which is the whole difference between a warning and a choice (`GAPS.md`).

    Both are fractions of the source width, as `Motion.focus` is. When a source
    is too small to fill the output at all the two collapse to the same number:
    every window is the widest one, and the guard is going to enlarge whatever
    is chosen.
    """
    w0, _ = base_window(src_w, src_h, aspect)
    return min(float(out_w), w0) / src_w, w0 / src_w


def compute(src_w: int, src_h: int, n_frames: int, motion: Motion,
            out_w: int = 1080, aspect: float = ASPECT) -> ShotSchedule:
    """Per-frame crop rects. Resolution guard (SPEC §5.2): the crop window may
    never go below out_w pixels wide — rate is clamped, never silently upscaled.

    `aspect` is the shape being filled, w/h. It defaults to the 9:16 reel frame,
    and exists because a stacked band is 1080x636 — the same presets, the same
    guard, a different rectangle. Nothing else in the motion vocabulary changes.
    """
    w0, h0 = base_window(src_w, src_h, aspect)
    sched = ShotSchedule()
    sched.max_zoom = w0 / out_w

    rate = max(0.0, motion.rate)
    preset = motion.preset if motion.preset in PRESETS else "static"

    if preset == "fit" and src_w / src_h > aspect:
        # Show the whole frame, full output width, letterboxed. There is no crop
        # at all, so a landscape source is *reduced* rather than enlarged —
        # 1280x800 lands at 1080x675, a 0.84x downscale, where the same source
        # cropped to 9:16 would have to invent 2.4x. The bands are the price and
        # they are honest: nothing outside them was ever filmed.
        #
        # It reuses square_in's dst_hs channel, which already means "the image
        # occupies this much of the frame's height"; the renderer needs nothing
        # new. Unlike square_in the value is constant, because there is nothing
        # to travel towards once the whole frame is on screen.
        w_i = (src_w // 2) * 2
        h_i = (src_h // 2) * 2
        dst_h = int(round(out_w * h_i / w_i / 2)) * 2
        sched.max_zoom = w_i / out_w
        for _ in range(n_frames):
            sched.ws.append(w_i)
            sched.hs.append(h_i)
            sched.xs.append(0)
            sched.ys.append(0)
            sched.dst_hs.append(dst_h)
        return sched
    if preset == "fit":
        # Already at least as tall as 9:16, so fitting to width would overflow
        # the frame. There is nothing to letterbox — hold the ordinary window.
        preset = "static"

    if preset == "square_in":
        # The image opens as a square inset and pushes in until it is
        # full-bleed. Two things move together: the destination grows from
        # out_w x out_w to the whole frame, and the crop follows the
        # destination's aspect, so the field of view narrows as the frame opens.
        # The push-in is therefore geometric — `rate` adds nothing and is
        # ignored — and the final frame is exactly the ordinary 9:16 window,
        # which is why the resolution guard needs no special case here.
        out_h = out_w / aspect
        for i in range(n_frames):
            t = _ease(i / (n_frames - 1)) if n_frames > 1 else 0.0
            dst_h = out_w + (out_h - out_w) * t
            w, h = base_window(src_w, src_h, out_w / dst_h)
            w_i = int(round(w / 2)) * 2
            h_i = int(round(h / 2)) * 2
            sched.ws.append(w_i)
            sched.hs.append(h_i)
            sched.xs.append(int(round(min(max((src_w - w_i) / 2, 0),
                                          max(src_w - w_i, 0)))))
            sched.ys.append(int(round(min(max((src_h - h_i) / 2, 0),
                                          max(src_h - h_i, 0)))))
            sched.dst_hs.append(int(round(dst_h / 2)) * 2)
        return sched

    if motion.focus is not None and preset in FOCUSABLE:
        # Travel between the whole frame and the stated detail. `static` simply
        # sits at the detail; zoom_in arrives, zoom_out departs. Width and
        # centre are interpolated together on the same eased t, so the framing
        # never drifts sideways faster than it closes.
        fw, fh, fcx, fcy, sched.clamped = focus_window(
            src_w, src_h, motion.focus, w0, out_w, aspect)
        cx0 = src_w / 2
        cy0 = h0 / 2 if motion.anchor == "top" else src_h / 2
        for i in range(n_frames):
            t = _ease(i / (n_frames - 1)) if n_frames > 1 else 0.0
            u = 1.0 if preset == "static" else (t if preset == "zoom_in" else 1 - t)
            w = w0 + (fw - w0) * u
            h = w / aspect
            cx = cx0 + (fcx - cx0) * u
            cy = cy0 + (fcy - cy0) * u
            w_i = int(round(w / 2)) * 2
            h_i = int(round(h / 2)) * 2
            sched.ws.append(w_i)
            sched.hs.append(h_i)
            sched.xs.append(int(round(min(max(cx - w / 2, 0),
                                          max(src_w - w_i, 0)))))
            sched.ys.append(int(round(min(max(cy - h / 2, 0),
                                          max(src_h - h_i, 0)))))
        return sched

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
        h = w / aspect
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
