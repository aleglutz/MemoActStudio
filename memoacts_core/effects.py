"""The six effect families (SPEC §5.4) — grade, grain, texture, frame, shake,
sharpen.

Parameterised families, not fixed effects: the reference creator's "~20 effects
that work" are these six with different settings, so the presets in `PRESETS`
are named argument sets rather than separate code paths.

**Composite order deviates from SPEC §5.4 on one point, deliberately.** The spec
lists shake last. It cannot go there: translating an already-composited frame
would drag the frame overlay along with it (a vignette has to stay nailed to the
viewport) and would expose empty edges. Shake is therefore *geometric* — it
offsets the crop window inside the source image, so it costs nothing, produces
no edges, and is what "camera shake" physically means. Everything else follows
the spec order:

    crop(+shake) → resize → grade → grain → texture → frame → sharpen

Sharpen runs last so it is not amplifying its own grain.

No GPU and no model anywhere in this module, by construction (SPEC §3 Branch A).
"""
from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

BLEND_MODES = ("overlay", "soft_light", "screen", "multiply", "normal")


# --------------------------------------------------------------------------
# family parameter objects
# --------------------------------------------------------------------------

@dataclass
class Shake:
    """Camera shake, applied to the crop window (see module docstring)."""
    amplitude_px: float = 4.0     # peak offset in SOURCE pixels
    frequency: float = 6.0        # oscillations per second
    rotate_deg: float = 0.0       # reserved; rotation needs crop margin
    seed: int = 0


@dataclass
class Grade:
    """Colour grade. A .cube LUT wins if given; otherwise the parametric knobs."""
    lut_path: str = ""
    exposure: float = 0.0         # stops
    contrast: float = 0.0         # -1..1 around mid grey
    saturation: float = 0.0       # -1..1
    temperature: float = 0.0      # -1 cool .. 1 warm
    lift: float = 0.0             # raises blacks — the "faded archive" look


@dataclass
class Grain:
    amount: float = 0.05          # std-dev in 0..1 units
    size: float = 1.5             # grain scale in output pixels; >1 is coarser
    coloured: bool = False        # False = luminance grain, the filmic default
    seed: int = 0


@dataclass
class Texture:
    """Looping overlay. `path` may be a still image or a video clip."""
    path: str = ""
    opacity: float = 0.25
    blend: str = "overlay"
    speed: float = 1.0            # <1 slows the clip (observed usage: ~0.4)


@dataclass
class FrameOverlay:
    path: str = ""                # alpha PNG, composited over everything
    opacity: float = 1.0


@dataclass
class Sharpen:
    amount: float = 0.4           # 0..2
    radius: float = 1.2
    threshold: int = 3


@dataclass
class EffectStack:
    grade: Grade | None = None
    grain: Grain | None = None
    texture: Texture | None = None
    frame: FrameOverlay | None = None
    shake: Shake | None = None
    sharpen: Sharpen | None = None

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in
                   ("grade", "grain", "texture", "frame", "shake", "sharpen"))


#: Named presets, expressed as settings of the families above — extend this
#: table rather than adding new code paths.
#:
#: ⚠ **These values are placeholders, not calibrated.** SPEC §5.4 says to ship
#: the reference creator's observed effects as named presets; her actual reels
#: have not been measured, so these are plausible starting points chosen by eye
#: on synthetic test images. A flat synthetic frame exaggerates grain badly
#: compared with a real photograph, so expect to revise upward on real
#: material. Calibrating them against her reels is an open task.
PRESETS: dict[str, dict] = {
    "none": {},
    "archive_soft": {
        "grade": Grade(contrast=-0.10, saturation=-0.25, lift=0.04,
                       temperature=0.15),
        "grain": Grain(amount=0.028, size=1.8),
    },
    "archive_harsh": {
        "grade": Grade(contrast=0.18, saturation=-0.45, lift=0.02),
        "grain": Grain(amount=0.050, size=2.4),
        "sharpen": Sharpen(amount=0.6),
    },
    "cold_document": {
        "grade": Grade(temperature=-0.25, saturation=-0.15, contrast=0.06),
        "grain": Grain(amount=0.020, size=1.2),
    },
    "handheld": {
        "shake": Shake(amplitude_px=5.0, frequency=5.0),
        "grain": Grain(amount=0.025, size=1.6),
    },
    "newsreel": {
        "grade": Grade(saturation=-1.0, contrast=0.22, lift=0.05),
        "grain": Grain(amount=0.055, size=2.0),
        "shake": Shake(amplitude_px=3.0, frequency=8.0),
        "sharpen": Sharpen(amount=0.5),
    },
}


# --------------------------------------------------------------------------
# shake — geometric, consumed by the renderer at crop time
# --------------------------------------------------------------------------

def shake_offsets(shake: Shake, n_frames: int, fps: int) -> list[tuple[int, int]]:
    """Per-frame (dx, dy) crop offsets in source pixels.

    Two incommensurable sine components per axis rather than random jitter:
    random per-frame offsets read as digital noise, whereas a wobble reads as a
    hand. The seed shifts the phase so two shots do not shake identically.
    """
    if n_frames <= 0:
        return []
    rng = np.random.default_rng(shake.seed)
    px, py = rng.uniform(0, 2 * math.pi, 2)
    a, f = shake.amplitude_px, shake.frequency
    out = []
    for i in range(n_frames):
        t = i / max(fps, 1)
        dx = a * (0.6 * math.sin(2 * math.pi * f * t + px)
                  + 0.4 * math.sin(2 * math.pi * f * 0.37 * t + px * 1.7))
        dy = a * (0.6 * math.sin(2 * math.pi * f * 0.83 * t + py)
                  + 0.4 * math.sin(2 * math.pi * f * 0.29 * t + py * 1.3))
        out.append((int(round(dx)), int(round(dy))))
    return out


# --------------------------------------------------------------------------
# grade
# --------------------------------------------------------------------------

def load_cube_lut(path: Path) -> tuple[np.ndarray, int]:
    """Parse an Adobe .cube 3D LUT into an (N,N,N,3) float array.

    .cube stores entries with red varying fastest, so the table is reshaped
    (B,G,R,3) and transposed — getting that backwards silently swaps the red
    and blue response, which looks like a broken grade rather than a bad index.
    """
    size = 0
    values: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        head, *rest = line.split()
        if head.upper() == "LUT_3D_SIZE":
            size = int(rest[0])
        elif head.upper() in ("TITLE", "DOMAIN_MIN", "DOMAIN_MAX", "LUT_1D_SIZE"):
            continue
        else:
            try:
                values.append((float(head), float(rest[0]), float(rest[1])))
            except (ValueError, IndexError):
                continue
    if not size or len(values) != size ** 3:
        raise ValueError(
            f"{path.name}: expected {size ** 3} entries for LUT_3D_SIZE {size}, "
            f"found {len(values)}")
    table = np.asarray(values, dtype=np.float32).reshape(size, size, size, 3)
    return table.transpose(2, 1, 0, 3), size


def _apply_lut(rgb: np.ndarray, table: np.ndarray, size: int) -> np.ndarray:
    """Trilinear interpolation through a 3D LUT. rgb is float 0..1, (H,W,3)."""
    idx = np.clip(rgb, 0.0, 1.0) * (size - 1)
    lo = np.floor(idx).astype(np.int32)
    hi = np.clip(lo + 1, 0, size - 1)
    frac = (idx - lo).astype(np.float32)

    r0, g0, b0 = lo[..., 0], lo[..., 1], lo[..., 2]
    r1, g1, b1 = hi[..., 0], hi[..., 1], hi[..., 2]
    fr = frac[..., 0:1], frac[..., 1:2], frac[..., 2:3]

    def at(r, g, b):
        return table[r, g, b]

    c00 = at(r0, g0, b0) * (1 - fr[0]) + at(r1, g0, b0) * fr[0]
    c01 = at(r0, g0, b1) * (1 - fr[0]) + at(r1, g0, b1) * fr[0]
    c10 = at(r0, g1, b0) * (1 - fr[0]) + at(r1, g1, b0) * fr[0]
    c11 = at(r0, g1, b1) * (1 - fr[0]) + at(r1, g1, b1) * fr[0]
    c0 = c00 * (1 - fr[1]) + c10 * fr[1]
    c1 = c01 * (1 - fr[1]) + c11 * fr[1]
    return c0 * (1 - fr[2]) + c1 * fr[2]


_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def grade_matrix(g: Grade) -> tuple[np.ndarray, np.ndarray]:
    """Collapse the whole parametric grade into one 3×3 matrix and offset.

    Every knob is *linear* in the pixel's RGB — including saturation, which
    looks like it needs a separate luma pass but is just a mix towards the
    weighted grey axis:

        exposure     x -> x * 2**e                     (per channel)
        lift         x -> lift + x*(1 - lift)          (per channel)
        contrast     x -> (x - 0.5)*(1 + c) + 0.5      (per channel)
        temperature  x -> x * [1+t, 1, 1-t]            (per channel)
        saturation   x -> luma + (x - luma)*s,  luma = w·x   (mixes channels)

    So `y = x @ M + b` reproduces all five in a single pass. This is not
    micro-optimisation: profiling put saturation alone at **76 ms/frame** at
    1080×1920, because the naive form allocates several 24 MB intermediates to
    compute a luma reduction and broadcast it back. The matrix form does the
    same work in one matmul.

    (A first attempt folded only the four per-channel knobs and barely helped —
    the measurement, not the reasoning, is what identified saturation.)
    """
    a_exp = 2.0 ** g.exposure
    a_lift, b_lift = 1.0 - g.lift, g.lift
    a_con, b_con = 1.0 + g.contrast, -0.5 * g.contrast
    t = g.temperature * 0.12
    a_tmp = np.array([1.0 + t, 1.0, 1.0 - t], dtype=np.float64)

    # Per-channel affine so far: y1 = x*A + B
    A = a_exp * a_lift * a_con * a_tmp
    B = a_tmp * (a_con * b_lift + b_con)

    # Saturation as a mix: y2_c = s*y1_c + (1-s)*Σ_k w_k*y1_k
    s = 1.0 + g.saturation
    w = _LUMA.astype(np.float64)

    # M[k, c] = coefficient of x_k in y2_c, for `y = x @ M`.
    M = A[:, None] * ((1.0 - s) * w[:, None] + s * np.eye(3))
    b = s * B + (1.0 - s) * float(w @ B)
    return M.astype(np.float32), b.astype(np.float32)


def apply_grade(rgb: np.ndarray, g: Grade,
                lut: tuple[np.ndarray, int] | None) -> np.ndarray:
    if lut is not None:
        return np.clip(_apply_lut(rgb, lut[0], lut[1]), 0.0, 1.0)
    M, b = grade_matrix(g)
    out = rgb @ M + b
    return np.clip(out, 0.0, 1.0, out=out)


# --------------------------------------------------------------------------
# grain
# --------------------------------------------------------------------------

def apply_grain(rgb: np.ndarray, gr: Grain, frame_index: int) -> np.ndarray:
    """Additive grain.

    Generated at reduced resolution and scaled up: that is both what gives grain
    a *size* and why this is affordable — synthesising noise at full 1080×1920
    for every frame is the slow way to get a less filmic result.
    """
    h, w = rgb.shape[:2]
    scale = max(1.0, float(gr.size))
    nh, nw = max(1, round(h / scale)), max(1, round(w / scale))
    # Frame index in the seed: a pattern fixed across frames reads as dirt on
    # the lens rather than as grain.
    rng = np.random.default_rng(gr.seed * 1_000_003 + frame_index)
    planes = 3 if gr.coloured else 1
    noise = rng.normal(0.0, gr.amount, (nh, nw, planes)).astype(np.float32)

    if (nh, nw) != (h, w):
        # Resize in float32 (PIL mode "F"), never via uint8 — a round trip
        # through 8 bits would quantise noise of amplitude ~0.05 down to a
        # handful of levels and turn grain into visible banding.
        noise = np.stack([
            np.asarray(Image.fromarray(noise[..., c], mode="F")
                       .resize((w, h), Image.Resampling.BILINEAR),
                       dtype=np.float32)
            for c in range(planes)
        ], axis=-1)
        # Smoothing removes variance; restore the requested amplitude so `size`
        # changes the grain's scale without also changing how strong it looks.
        measured = float(noise.std())
        if measured > 1e-6:
            noise *= gr.amount / measured

    return np.clip(rgb + noise, 0.0, 1.0)


# --------------------------------------------------------------------------
# blending, texture and frame overlays
# --------------------------------------------------------------------------

def blend(base: np.ndarray, top: np.ndarray, mode: str,
          opacity: float) -> np.ndarray:
    if mode == "multiply":
        mixed = base * top
    elif mode == "screen":
        mixed = 1.0 - (1.0 - base) * (1.0 - top)
    elif mode == "overlay":
        mixed = np.where(base < 0.5, 2 * base * top,
                         1.0 - 2 * (1.0 - base) * (1.0 - top))
    elif mode == "soft_light":
        mixed = np.where(
            top < 0.5,
            base - (1.0 - 2 * top) * base * (1.0 - base),
            base + (2 * top - 1.0) * (np.sqrt(np.clip(base, 0, 1)) - base))
    else:                                          # "normal"
        mixed = top
    return np.clip(base + (mixed - base) * opacity, 0.0, 1.0)


class TextureSource:
    """Frames of the texture layer, looping forever.

    A still image yields the same frame every time. A video is streamed through
    ffmpeg — never decoded into memory as a whole, since the observed texture
    clip is ~65 s and would be several GB at output resolution.
    """

    def __init__(self, path: Path, out_w: int, out_h: int, speed: float = 1.0):
        self.path, self.out_w, self.out_h = path, out_w, out_h
        self.speed = max(0.01, speed)
        self._still: np.ndarray | None = None
        self._proc: subprocess.Popen | None = None
        self._log = None
        self._cur: np.ndarray | None = None
        self._cur_index = -1

        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                   ".tif", ".tiff"):
            img = Image.open(path).convert("RGB").resize(
                (out_w, out_h), Image.Resampling.LANCZOS)
            self._still = np.asarray(img, dtype=np.float32) / 255.0

    def _ffmpeg(self) -> str:
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()

    def _open(self) -> None:
        self.close()
        import tempfile
        self._log = tempfile.TemporaryFile()
        self._proc = subprocess.Popen(
            [self._ffmpeg(), "-v", "error", "-i", str(self.path),
             "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-vf", f"scale={self.out_w}:{self.out_h}", "-"],
            stdout=subprocess.PIPE, stderr=self._log)

    def _next_raw(self) -> np.ndarray:
        need = self.out_w * self.out_h * 3
        if self._proc is None:
            self._open()
        assert self._proc is not None and self._proc.stdout is not None
        buf = self._proc.stdout.read(need)
        if len(buf) < need:                        # end of clip -> loop
            self._open()
            assert self._proc is not None and self._proc.stdout is not None
            buf = self._proc.stdout.read(need)
            if len(buf) < need:
                raise RuntimeError(
                    f"could not read a frame from texture {self.path.name}")
        return (np.frombuffer(buf, dtype=np.uint8)
                .reshape(self.out_h, self.out_w, 3).astype(np.float32) / 255.0)

    def frame(self, index: int) -> np.ndarray:
        if self._still is not None:
            return self._still
        want = int(index * self.speed)
        while self._cur_index < want or self._cur is None:
            self._cur = self._next_raw()
            self._cur_index += 1
        return self._cur

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdout:
                    self._proc.stdout.close()
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:                      # noqa: BLE001
                pass
            self._proc = None
        if self._log is not None:
            self._log.close()
            self._log = None


def load_overlay(path: Path, out_w: int, out_h: int) -> tuple[np.ndarray, np.ndarray]:
    """An alpha PNG frame: returns (rgb, alpha) already at output size."""
    img = Image.open(path).convert("RGBA").resize(
        (out_w, out_h), Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr[..., :3], arr[..., 3:4]


# --------------------------------------------------------------------------
# the per-frame pipeline
# --------------------------------------------------------------------------

class EffectPipeline:
    """Applies an EffectStack to frames. Holds the loaded assets.

    Built once per shot; `close()` releases the texture decoder. Shake is NOT
    handled here — it is geometric and consumed by the renderer at crop time.
    """

    def __init__(self, stack: EffectStack, out_w: int, out_h: int):
        self.stack, self.out_w, self.out_h = stack, out_w, out_h
        self._lut = None
        self._texture: TextureSource | None = None
        self._overlay: tuple[np.ndarray, np.ndarray] | None = None

        g = stack.grade
        if g is not None and g.lut_path:
            self._lut = load_cube_lut(Path(g.lut_path))
        if stack.texture is not None and stack.texture.path:
            self._texture = TextureSource(
                Path(stack.texture.path), out_w, out_h, stack.texture.speed)
        if stack.frame is not None and stack.frame.path:
            self._overlay = load_overlay(Path(stack.frame.path), out_w, out_h)

    def apply(self, image: Image.Image, frame_index: int) -> Image.Image:
        s = self.stack
        if s.is_empty():
            return image

        rgb = np.asarray(image, dtype=np.float32) / 255.0

        if s.grade is not None:
            rgb = apply_grade(rgb, s.grade, self._lut)
        if s.grain is not None and s.grain.amount > 0:
            rgb = apply_grain(rgb, s.grain, frame_index)
        if self._texture is not None:
            rgb = blend(rgb, self._texture.frame(frame_index),
                        s.texture.blend, s.texture.opacity)
        if self._overlay is not None:
            ov_rgb, ov_a = self._overlay
            rgb = rgb * (1.0 - ov_a * s.frame.opacity) + \
                ov_rgb * (ov_a * s.frame.opacity)

        out = Image.fromarray(
            np.clip(rgb * 255.0, 0, 255).astype(np.uint8), mode="RGB")

        # Last, so it is not sharpening the grain it just added.
        if s.sharpen is not None and s.sharpen.amount > 0:
            out = out.filter(ImageFilter.UnsharpMask(
                radius=s.sharpen.radius,
                percent=int(s.sharpen.amount * 100),
                threshold=s.sharpen.threshold))
        return out

    def close(self) -> None:
        if self._texture is not None:
            self._texture.close()
            self._texture = None


def preset(name: str) -> EffectStack:
    """An EffectStack from a named preset. Unknown names raise, rather than
    silently returning an empty stack that looks like a broken effect."""
    if name not in PRESETS:
        raise ValueError(f"unknown preset {name!r}; have {sorted(PRESETS)}")
    import copy
    return EffectStack(**copy.deepcopy(PRESETS[name]))
