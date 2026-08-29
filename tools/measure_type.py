"""What the act's typewriter actually did, in numbers (SPEC 5.2c).

    python tools/measure_type.py --scan .../GIoS_Wehrmacht_Signed_Ru.jpg

Every constant in `render_page.py` says in its comment that it was fitted to
this scan. The jitter constants say it too, and they were the one set fitted by
eye. This measures them instead.

Three numbers come out, all in units of the escapement's advance so they carry
across a change of sheet size:

    advance, pitch      the machine's own grid, from the letters
    baseline scatter    how far a letter sits off its line, after the line's
                        own skew is taken out -- the two are different faults
                        and `Typist.line` already models them separately
    grid scatter        the same sideways: how far a letter lands off the cell
                        the escapement advanced into

The separation matters. A line typed askew is one number for the whole line and
reads as paper fed crooked; a letter off its baseline is a number per glyph and
reads as a typebar. Measure them together and the scatter comes out too big,
put both into the per-glyph term and the sheet reads as if it were shaken.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def ink_mask(rgb: np.ndarray, drop: float) -> np.ndarray:
    lum = rgb.mean(2).astype(np.float32)
    h, w = lum.shape
    small = cv2.resize(lum, (max(2, w // 24), max(2, h // 24)), interpolation=cv2.INTER_AREA)
    small = cv2.dilate(small, np.ones((5, 5), np.uint8))
    field = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    return ((field - lum) > drop).astype(np.uint8)


def lines_of(mask: np.ndarray, min_rows: int) -> list[tuple[int, int]]:
    rows = mask.sum(1)
    on = rows > max(3, rows.max() * 0.02)
    out, start = [], None
    for y, v in enumerate(on):
        if v and start is None:
            start = y
        elif not v and start is not None:
            if y - start >= min_rows:
                out.append((start, y))
            start = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=Path, required=True)
    ap.add_argument("--drop", type=float, default=26.0)
    ap.add_argument("--min-rows", type=int, default=8)
    args = ap.parse_args()

    rgb = np.asarray(Image.open(args.scan).convert("RGB"), dtype=np.float32)
    mask = ink_mask(rgb, args.drop)
    bands = lines_of(mask, args.min_rows)
    print(f"{args.scan.name}  {rgb.shape[1]}x{rgb.shape[0]}  {len(bands)} typed lines")

    advances, base_sd, grid_sd, skews, heights = [], [], [], [], []
    for y0, y1 in bands:
        band = mask[y0:y1]
        n, _, stats, cent = cv2.connectedComponentsWithStats(band, 8)
        # A letter, not a speck and not two letters run together: taller than a
        # third of the band and no wider than the band is tall.
        keep = [i for i in range(1, n)
                if stats[i, cv2.CC_STAT_HEIGHT] > (y1 - y0) * 0.33
                and stats[i, cv2.CC_STAT_WIDTH] < (y1 - y0) * 1.1
                and stats[i, cv2.CC_STAT_AREA] > 12]
        if len(keep) < 12:
            continue
        x = np.array([stats[i, cv2.CC_STAT_LEFT] for i in keep], float)
        bot = np.array([stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT]
                        for i in keep], float)
        hgt = np.array([stats[i, cv2.CC_STAT_HEIGHT] for i in keep], float)
        order = np.argsort(x)
        x, bot, hgt = x[order], bot[order], hgt[order]
        # Only letters of the one height. A descender hangs below the baseline
        # and a lower-case letter without one stops above the cap line: measure
        # a mixture and what comes out is the alphabet's shape, not the
        # machine's scatter. This is the difference between an upper bound and
        # a measurement, and it was worth another pass to get.
        med = np.median(hgt)
        fit = np.abs(hgt - med) < med * 0.10
        if fit.sum() < 10:
            continue
        x, bot = x[fit], bot[fit]

        # The advance is the smallest step the escapement makes; a space is two
        # of them and a gap between words is more, so take the low quartile of
        # the steps rather than their mean.
        step = np.diff(x)
        step = step[step > 2]
        if step.size < 8:
            continue
        adv = float(np.median(step[step < np.percentile(step, 40)]))
        if not 6 < adv < 60:
            continue

        # The line's own skew, and what is left after it: the glyph's.
        k, b = np.polyfit(x, bot, 1)
        resid = bot - (k * x + b)
        # Sideways, against the grid the escapement actually walked.
        cell = np.round((x - x[0]) / adv)
        kx, bx = np.polyfit(cell, x, 1)
        gresid = x - (kx * cell + bx)

        advances.append(adv)
        heights.append(float(np.median(hgt)))
        base_sd.append(float(resid.std()))
        grid_sd.append(float(gresid.std()))
        skews.append(float(k))

    if not advances:
        raise SystemExit("no line gave enough clean letters; lower --drop")

    adv = float(np.median(advances))
    pitch = float(np.median(np.diff([b[0] for b in bands])))
    b_sd, g_sd = float(np.median(base_sd)), float(np.median(grid_sd))
    skew = float(np.median(np.abs(skews)))
    print(f"  lines measured      {len(advances)}")
    print(f"  advance             {adv:.2f} px      cap height {np.median(heights):.1f} px")
    print(f"  line pitch          {pitch:.1f} px    = {pitch / adv:.3f} advance")
    print(f"  baseline scatter    {b_sd:.2f} px     = {b_sd / adv:.4f} advance (sd)")
    print(f"  grid scatter        {g_sd:.2f} px     = {g_sd / adv:.4f} advance (sd)")
    print(f"  line skew           {skew * 1000:.2f} px per 1000 px  "
          f"= {np.degrees(np.arctan(skew)):.3f} deg")
    print()
    print("  render_page.Typist.line draws both from a uniform, whose sd is its")
    print("  half-range over sqrt(3). To match, set")
    print(f"    vertical   uniform(-{b_sd / adv * 3 ** 0.5:.3f}, {b_sd / adv * 3 ** 0.5:.3f}) advance")
    print(f"    horizontal uniform(-{g_sd / adv * 3 ** 0.5:.3f}, {g_sd / adv * 3 ** 0.5:.3f}) advance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
