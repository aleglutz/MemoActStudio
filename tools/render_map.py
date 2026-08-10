"""Terrain map of Europe with named countries washed in their flag colours.

    python tools/render_map.py --out projects/<name>/maps \
        --name map_poland_ukraine --highlight Poland Ukraine

Why this is drawn and not generated: a diffusion model invents coastlines and
smears borders, and a wrong map of Europe in a museum film about historical
memory is worse than no map. Geometry and shaded relief are both Natural Earth
(public domain — assets/geo/SOURCE.md). It is authored graphics, so the
provenance question that hangs over synthetic "archival" imagery (SPEC §9.7)
does not arise — which matters for the shots about present-day politics.

Composited in numpy rather than drawn with matplotlib patches, because the
things that make it read — relief shading through the land, flags as a
translucent wash rather than a flat fill, and the exact land/sea contrast —
are all per-pixel decisions.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

#: Flag stripes, top to bottom (or left to right for "v"). The United Kingdom
#: is approximated: a Union Jack clipped to an island outline reads as noise at
#: this size, so it takes its three colours as bands.
FLAGS: dict[str, tuple[str, list[str]]] = {
    "Germany":        ("h", ["#000000", "#DD0000", "#FFCE00"]),
    "France":         ("v", ["#002395", "#FFFFFF", "#ED2939"]),
    "United Kingdom": ("h", ["#012169", "#FFFFFF", "#C8102E"]),
    "Russia":         ("h", ["#FFFFFF", "#0039A6", "#D52B1E"]),
    "Armenia":        ("h", ["#D90012", "#0033A0", "#F2A800"]),
    "Latvia":         ("h", ["#9E3039", "#FFFFFF", "#9E3039"]),
    "Estonia":        ("h", ["#0072CE", "#000000", "#FFFFFF"]),
    "Lithuania":      ("h", ["#FDB913", "#006A44", "#C1272D"]),
    "Poland":         ("h", ["#FFFFFF", "#DC143C"]),
    "Ukraine":        ("h", ["#0057B7", "#FFD700"]),
}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEOJSON = ROOT / "assets" / "geo" / "ne_50m_admin_0_countries.geojson"
DEFAULT_RELIEF = ROOT / "assets" / "geo" / "relief_europe_50m.png"

#: Window the relief crop covers, in degrees (assets/geo/SOURCE.md).
RELIEF_LON = (-15.0, 55.0)
RELIEF_LAT = (30.0, 75.0)

#: 1440x2560, not 1080x1920: a plate made at exactly output size has no
#: headroom and cannot move — the trap the stacked composites hit.
OUT_W, OUT_H = 1440, 2560
LON_MIN, LON_MAX = -11.0, 47.0
LAT_MIN, LAT_MAX = 34.0, 71.0
LAT0 = math.radians((LAT_MIN + LAT_MAX) / 2)

#: Palette. The first pass put warm grey land on near-black sea and read as
#: dirty; the fix is to make the sea unmistakably water — cool, deep, and well
#: separated in both hue and value — and to let the relief carry the land's
#: variation instead of a flat fill doing it.
SEA_DEEP = np.array([10, 26, 38], dtype=np.float32)
SEA_SHELF = np.array([20, 46, 62], dtype=np.float32)
#: Base colour of unlit land. The raster is a HILLSHADE, not elevation — flat
#: ground carries the same value as water and only slopes darken or lighten.
#: So it multiplies this base rather than driving a lowland-to-peak ramp, which
#: is what the first pass did and why the whole continent came out one sand tone.
LAND_BASE = np.array([96, 100, 78], dtype=np.float32)
LAND_RELIEF_GAIN = 1.35
COAST_RGB = np.array([196, 214, 224], dtype=np.float32)
BORDER_RGB = np.array([120, 126, 118], dtype=np.float32)

FLAG_ALPHA = 0.55       # a wash, so the terrain still reads underneath


def project(lon: float, lat: float) -> tuple[float, float]:
    """Equirectangular with a cosine correction at the view's mid-latitude."""
    return lon * math.cos(LAT0), lat


def rings(geom: dict) -> list[list[tuple[float, float]]]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def name_of(props: dict) -> str:
    for key in ("NAME_EN", "NAME", "ADMIN"):
        if props.get(key):
            return props[key]
    return ""


def projected_rings(feature: dict) -> list[np.ndarray]:
    out = []
    for ring in rings(feature["geometry"]):
        pts = np.array([project(x, y) for x, y in ring], dtype=np.float64)
        lon = pts[:, 0] / math.cos(LAT0)
        # Drop far-flung territories that would otherwise stretch every view.
        if not ((lon >= LON_MIN) & (lon <= LON_MAX) &
                (pts[:, 1] >= LAT_MIN) & (pts[:, 1] <= LAT_MAX)).any():
            continue
        out.append(pts)
    return out


def view_for(feats: list[tuple[str, list[np.ndarray]]], highlight: list[str],
             context: float) -> tuple[float, float, float, float]:
    """Frame the shot on what is being named.

    A Europe-wide view makes the Baltic states about a hundredth of the frame,
    which is useless under a line that is *about* the Baltic states.
    """
    wanted = {h.lower() for h in highlight}
    xs, ys = [], []
    for name, polys in feats:
        if name.lower() not in wanted:
            continue
        for p in polys:
            xs += [p[:, 0].min(), p[:, 0].max()]
            ys += [p[:, 1].min(), p[:, 1].max()]

    fx0, fx1 = project(LON_MIN, 0)[0], project(LON_MAX, 0)[0]
    europe = ((fx0 + fx1) / 2, (LAT_MIN + LAT_MAX) / 2, (fx1 - fx0) / 2)
    if not xs:
        cx, cy, half_x = europe
    else:
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        half_x = max((max(xs) - min(xs)) / 2,
                     (max(ys) - min(ys)) / 2 * OUT_W / OUT_H) * context
        # A country bigger than the frame can hold drags the centre with it —
        # fitting the view to Russia points the camera at Siberia rather than
        # at Europe. Past that point, show the continent instead.
        if half_x >= europe[2]:
            cx, cy, half_x = europe
    half_x = max(half_x, project(3.5, 0)[0])
    half_y = half_x * OUT_H / OUT_W
    return cx - half_x, cx + half_x, cy - half_y, cy + half_y


def to_pixels(poly: np.ndarray, view) -> list[tuple[float, float]]:
    vx0, vx1, vy0, vy1 = view
    px = (poly[:, 0] - vx0) / (vx1 - vx0) * OUT_W
    py = (vy1 - poly[:, 1]) / (vy1 - vy0) * OUT_H       # north up
    return list(zip(px.tolist(), py.tolist()))


def fill_mask(polys: list[np.ndarray], view) -> np.ndarray:
    m = Image.new("L", (OUT_W, OUT_H), 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        pts = to_pixels(p, view)
        if len(pts) >= 3:
            d.polygon(pts, fill=255)
    return np.asarray(m, dtype=np.float32) / 255.0


def outline_mask(polys: list[np.ndarray], view, width: int) -> np.ndarray:
    m = Image.new("L", (OUT_W, OUT_H), 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        pts = to_pixels(p, view)
        if len(pts) >= 2:
            d.line(pts + [pts[0]], fill=255, width=width)
    return np.asarray(m, dtype=np.float32) / 255.0


#: Flat value the Natural Earth relief uses for water.
RELIEF_SEA = 206


def sample_relief(view, relief: Image.Image) -> np.ndarray:
    """Crop the relief to the view and resample to frame size, 0..1.

    A view can reach past the cropped window (the widest framings do). The
    missing margin is padded with the raster's own water value rather than
    clamped, which would stretch the coastline sideways to fill the gap.
    """
    vx0, vx1, vy0, vy1 = view
    lon0, lon1 = vx0 / math.cos(LAT0), vx1 / math.cos(LAT0)
    rw, rh = relief.size

    def fx(lon):
        return (lon - RELIEF_LON[0]) / (RELIEF_LON[1] - RELIEF_LON[0]) * rw

    def fy(lat):
        return (RELIEF_LAT[1] - lat) / (RELIEF_LAT[1] - RELIEF_LAT[0]) * rh

    x0, y0, x1, y1 = fx(lon0), fy(vy1), fx(lon1), fy(vy0)
    pad_l, pad_t = max(0.0, -x0), max(0.0, -y0)
    pad_r, pad_b = max(0.0, x1 - rw), max(0.0, y1 - rh)

    if pad_l or pad_t or pad_r or pad_b:
        canvas = Image.new("L", (int(rw + pad_l + pad_r), int(rh + pad_t + pad_b)),
                           RELIEF_SEA)
        canvas.paste(relief, (int(pad_l), int(pad_t)))
        relief = canvas
        x0 += pad_l; x1 += pad_l; y0 += pad_t; y1 += pad_t

    box = (max(0.0, x0), max(0.0, y0),
           min(float(relief.size[0]), x1), min(float(relief.size[1]), y1))
    patch = relief.resize((OUT_W, OUT_H), Image.Resampling.BICUBIC, box=box)
    a = np.asarray(patch, dtype=np.float32) / 255.0
    # Normalised so flat ground sits at 1.0: shadowed slopes fall below it and
    # lit faces rise above, which is what a hillshade actually encodes.
    return a / (RELIEF_SEA / 255.0)


def hexr(c: str) -> np.ndarray:
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def draw(features: list[dict], highlight: list[str], dest: Path,
         context: float = 2.6, relief_path: Path = DEFAULT_RELIEF) -> Path:
    feats = [(name_of(f["properties"]), projected_rings(f)) for f in features]
    feats = [(n, p) for n, p in feats if p]
    view = view_for(feats, highlight, context)

    land = fill_mask([p for _, polys in feats for p in polys], view)
    land_soft = np.asarray(
        Image.fromarray((land * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(2.0)), dtype=np.float32) / 255.0

    relief = sample_relief(view, Image.open(relief_path).convert("L"))

    # Sea: shallower near the coast, so the shoreline reads without a hard line.
    shelf = np.clip(land_soft * 2.4, 0, 1)[..., None]
    img = SEA_DEEP * (1 - shelf) + SEA_SHELF * shelf

    # Land: the hillshade lights a single base colour.
    shade = (1.0 + (relief - 1.0) * LAND_RELIEF_GAIN)[..., None]
    land_rgb = np.clip(LAND_BASE * shade, 0, 255)
    lm = land[..., None]
    img = img * (1 - lm) + land_rgb * lm

    # Borders under the flags, so a wash does not bury them.
    borders = outline_mask([p for _, polys in feats for p in polys], view, 1)
    img = img * (1 - 0.30 * borders[..., None]) + BORDER_RGB * (0.30 * borders[..., None])

    wanted = {h.lower() for h in highlight}
    for name, polys in feats:
        if name.lower() not in wanted:
            continue
        mask = fill_mask(polys, view)
        if mask.max() <= 0:
            continue
        orient, colours = FLAGS.get(name, ("h", ["#FFFFFF"]))

        # One flag across the whole country, not one per polygon — measured per
        # polygon, Estonia's islands each got a complete blue/black/white.
        allpts = np.concatenate([np.array(to_pixels(p, view)) for p in polys])
        # Clamp to the frame: a country reaching far off-screen (Russia) would
        # otherwise spread its three bands across a bbox many frames wide, and
        # the visible part would land inside a single stripe.
        bx0, by0 = max(allpts[:, 0].min(), 0.0), max(allpts[:, 1].min(), 0.0)
        bx1, by1 = min(allpts[:, 0].max(), OUT_W), min(allpts[:, 1].max(), OUT_H)
        if bx1 <= bx0 or by1 <= by0:
            continue

        wash = np.zeros((OUT_H, OUT_W, 3), dtype=np.float32)
        # Track coverage separately. Testing "is this pixel still zero" would
        # treat a black band as unpainted — which silently turned Germany's
        # black stripe gold and Estonia's black stripe white.
        painted = np.zeros((OUT_H, OUT_W), dtype=bool)
        n = len(colours)
        ys, xs = np.mgrid[0:OUT_H, 0:OUT_W]
        for i, col in enumerate(colours):
            if orient == "h":
                band = (ys >= by0 + (by1 - by0) * i / n) & \
                       (ys < by0 + (by1 - by0) * (i + 1) / n)
            else:
                band = (xs >= bx0 + (bx1 - bx0) * i / n) & \
                       (xs < bx0 + (bx1 - bx0) * (i + 1) / n)
            wash[band] = hexr(col)
            painted |= band
        wash[~painted] = hexr(colours[-1])      # rounding edge at the boundary

        # Multiply the wash by the relief so ridges and valleys stay visible
        # through the colour, then blend — a flat fill reads as a sticker.
        lit = wash * (1.0 + (relief[..., None] - 1.0) * LAND_RELIEF_GAIN)
        a = (FLAG_ALPHA * mask)[..., None]
        img = img * (1 - a) + np.clip(lit, 0, 255) * a

        edge = outline_mask(polys, view, 3)[..., None]
        img = img * (1 - 0.85 * edge) + COAST_RGB * (0.85 * edge)

    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON)
    ap.add_argument("--relief", type=Path, default=DEFAULT_RELIEF)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--highlight", nargs="*", default=[])
    ap.add_argument("--name", default="map")
    ap.add_argument("--context", type=float, default=2.6)
    args = ap.parse_args()

    data = json.loads(args.geojson.read_text(encoding="utf-8"))
    dest = draw(data["features"], args.highlight,
                args.out / f"{args.name}.png", args.context, args.relief)
    print(f"wrote {dest}  highlight={args.highlight or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
