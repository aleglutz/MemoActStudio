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
import sys
from dataclasses import dataclass
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
#: `--scale` multiplies both, which is how far a shot can push in: at 1440 wide
#: the reel can reach 1.33x, and a map that travels from a country to a town
#: needs more than that. Rebound in main(), so every helper below reads the
#: chosen size rather than being handed it.
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

#: Alternative palettes, sampled from the reel's own document scans rather than
#: chosen: the act pages and the Reims protocol sit either side of these maps,
#: and their paper measures 239-249 / 221-240 / 198-215 across the four scans —
#: warm by about +38 red over blue — with ink between 69,49,43 and 132,101,89.
#: Taking land from paper and water from ink is what ties the drawn material to
#: the photographed material; the flags stay flags, since a wash that drifted
#: with the palette would stop being a national colour.
#:
#: `--palette` picks one. `terrain` is the original and stays the default, so a
#: plate rebuilt from an old command line comes back unchanged.
PALETTES: dict[str, dict] = {
    "terrain": {
        "sea_deep": (10, 26, 38), "sea_shelf": (20, 46, 62),
        "land": (96, 100, 78), "coast": (196, 214, 224),
        "border": (120, 126, 118), "flag_alpha": 0.55, "relief_gain": 1.35,
    },
    # Paper and ink: the strongest reading of the documents, and the largest
    # break from the current look — land is the page, water is what was
    # written on it.
    "paper": {
        "sea_deep": (46, 36, 32), "sea_shelf": (94, 76, 64),
        "land": (214, 199, 173), "coast": (250, 243, 224),
        "border": (150, 132, 112), "flag_alpha": 0.58, "relief_gain": 1.15,
    },
    # The same idea carried into the water as well: a tea-stained plate with
    # no cool anywhere, closest to the aged Russian scan.
    "sepia": {
        "sea_deep": (84, 68, 56), "sea_shelf": (132, 112, 92),
        "land": (198, 181, 154), "coast": (238, 226, 204),
        "border": (160, 140, 118), "flag_alpha": 0.62, "relief_gain": 1.10,
    },
    # Paper land, but the water keeps the blue-black of the signatures rather
    # than the brown of the typescript: the least distance from the reel as it
    # stands, and sea that still reads unmistakably as sea.
    "ink": {
        "sea_deep": (28, 32, 44), "sea_shelf": (62, 70, 84),
        "land": (216, 206, 188), "coast": (244, 238, 224),
        "border": (126, 120, 106), "flag_alpha": 0.55, "relief_gain": 1.20,
    },
}


def use_palette(name: str) -> None:
    """Rebind the module's palette. Same reasoning as --scale: these are read
    as module state by every helper below, and threading a palette object
    through each would be a wider change than picking a colour deserves."""
    global SEA_DEEP, SEA_SHELF, LAND_BASE, COAST_RGB, BORDER_RGB
    global FLAG_ALPHA, LAND_RELIEF_GAIN
    p = PALETTES[name]
    SEA_DEEP = np.array(p["sea_deep"], dtype=np.float32)
    SEA_SHELF = np.array(p["sea_shelf"], dtype=np.float32)
    LAND_BASE = np.array(p["land"], dtype=np.float32)
    COAST_RGB = np.array(p["coast"], dtype=np.float32)
    BORDER_RGB = np.array(p["border"], dtype=np.float32)
    FLAG_ALPHA = p["flag_alpha"]
    LAND_RELIEF_GAIN = p["relief_gain"]


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


# --- Crimea and Sevastopol ---------------------------------------------------
#
# Natural Earth's admin-0 country layer assigns the Crimean peninsula to
# RUSSIA, and the committed 1:50m file is no exception. Verified against it on
# 2026-08-22: Sevastopol, Simferopol, Yalta, Kerch, Yevpatoria, Dzhankoi and
# Feodosia all fall inside the Russia polygon, and the peninsula is a single
# discrete part of that MultiPolygon (bounds 32.51,44.39 - 36.58,46.22) which
# touches no Russian mainland.
#
# Left alone this is not a subtle cartographic quibble -- it is visible in the
# finished plate. The 2:18 shot washes Ukraine in its flag colours, so an
# uncorrected Crimea renders as unhighlighted land: a hole punched in Ukraine,
# under a line about Ukraine moving its commemoration date.
#
# So the geometry is corrected here rather than accepted. Germany, the EU and
# UN General Assembly Resolution 68/262 do not recognise the 2014 annexation,
# and this project is funded by the Auswaertiges Amt -- this is a compliance
# requirement, not a style preference.
#
# The correction is deliberately written to VERIFY rather than assume, because
# Natural Earth's handling has moved between releases: it locates the offending
# part by probe points instead of by index, does nothing if a future release
# already assigns the peninsula to Ukraine, and raises if the result still
# fails the check. A silent no-op here would be the worst outcome.

#: Towns spread across the peninsula, including Sevastopol, which is
#: administratively separate from the Autonomous Republic of Crimea.
CRIMEA_PROBES: list[tuple[str, float, float]] = [
    ("Sevastopol", 33.5333, 44.6000),
    ("Simferopol", 34.1000, 44.9521),
    ("Yalta",      34.1667, 44.5000),
    ("Kerch",      36.4700, 45.3600),
    ("Yevpatoria", 33.3667, 45.1900),
    ("Dzhankoi",   34.3931, 45.7086),
    ("Feodosia",   35.3800, 45.0300),
]

#: Generous box around the peninsula. A part is only ever moved if it lies
#: WHOLLY inside this and carries a probe, so a polygon that also held Russian
#: mainland could never be reassigned by accident.
CRIMEA_ENVELOPE = (31.9, 43.9, 37.1, 46.6)


def _point_in_ring(lon: float, lat: float, ring) -> bool:
    """Ray casting against one closed ring of (lon, lat) pairs."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            if lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _polygon_parts(geom: dict) -> list:
    """GeoJSON geometry -> list of polygons, each [exterior, *holes].

    Unlike rings() above, this keeps the holes: the renderer can ignore them,
    but a containment test that ignored them would be wrong.
    """
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def _covers(geom: dict, lon: float, lat: float) -> bool:
    for poly in _polygon_parts(geom):
        if _point_in_ring(lon, lat, poly[0]) and not any(
                _point_in_ring(lon, lat, h) for h in poly[1:]):
            return True
    return False


def _within_envelope(poly) -> bool:
    x0, y0, x1, y1 = CRIMEA_ENVELOPE
    return all(x0 <= x <= x1 and y0 <= y <= y1
               for ring in poly for x, y in ((p[0], p[1]) for p in ring))


def correct_crimea(features: list[dict], verbose: bool = True) -> list[dict]:
    """Render Crimea and Sevastopol as Ukraine, whatever the source file says.

    Moves any admin-0 part that sits wholly inside the Crimea envelope and
    carries one of the probe towns out of every other country and into
    Ukraine, then re-tests every probe and raises if the fix did not take.
    """
    by_name = {name_of(f["properties"]): f for f in features}
    ukraine = by_name.get("Ukraine")
    if ukraine is None:
        raise SystemExit("crimea check: no Ukraine feature in the geodata")

    moved: list[tuple[str, int]] = []
    claimed: list = []
    for feat in features:
        owner = name_of(feat["properties"])
        if owner == "Ukraine":
            continue
        parts = _polygon_parts(feat["geometry"])
        keep = []
        for idx, poly in enumerate(parts):
            is_crimea = _within_envelope(poly) and any(
                _point_in_ring(lon, lat, poly[0])
                for _, lon, lat in CRIMEA_PROBES)
            if is_crimea:
                claimed.append(poly)
                moved.append((owner, idx))
            else:
                keep.append(poly)
        if len(keep) != len(parts):
            feat["geometry"] = {"type": "MultiPolygon", "coordinates": keep}

    if claimed:
        ua_parts = _polygon_parts(ukraine["geometry"]) + claimed
        ukraine["geometry"] = {"type": "MultiPolygon", "coordinates": ua_parts}

    # Verify, always -- including when nothing was moved, which is the case a
    # future Natural Earth release would produce and must still be checked.
    failures = []
    for label, lon, lat in CRIMEA_PROBES:
        in_ua = _covers(ukraine["geometry"], lon, lat)
        others = [name_of(f["properties"]) for f in features
                  if name_of(f["properties"]) != "Ukraine"
                  and _covers(f["geometry"], lon, lat)]
        if verbose:
            verdict = "Ukraine" if in_ua else (", ".join(others) or "<nothing>")
            print(f"  crimea check  {label:<11} -> {verdict}")
        if not in_ua or others:
            failures.append((label, in_ua, others))

    if verbose:
        if moved:
            where = ", ".join(f"{o} part #{i}" for o, i in moved)
            print(f"  crimea check  corrected: moved {where} -> Ukraine")
        else:
            print("  crimea check  source already assigns Crimea to Ukraine; "
                  "no correction needed")

    if failures:
        raise SystemExit(
            "crimea check FAILED -- refusing to render a map that does not "
            f"show Crimea as Ukraine: {failures}")
    return features


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


@dataclass
class Wash:
    """One country's flag wash, ready to be blended at any strength.

    Cropped to the country's bounding box. A country covers a small part of the
    plate, and compositing the whole frame per country per frame is most of the
    cost of an animated fill — Latvia is under 2 % of the pixels.
    """
    name: str
    box: tuple[int, int, int, int]       # y0, y1, x0, x1
    mask: np.ndarray
    lit: np.ndarray
    edge: np.ndarray


def _plate(feats, view, relief) -> np.ndarray:
    """Everything under the flags: sea, lit land, borders. Never animates."""
    land = fill_mask([p for _, polys in feats for p in polys], view)
    land_soft = np.asarray(
        Image.fromarray((land * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(2.0)), dtype=np.float32) / 255.0

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
    return (img * (1 - 0.30 * borders[..., None])
            + BORDER_RGB * (0.30 * borders[..., None]))


def _washes(feats, highlight: list[str], view, relief) -> list[Wash]:
    """One `Wash` per highlighted country, in the order named."""
    by_name = {n.lower(): (n, p) for n, p in feats}
    out: list[Wash] = []
    for want in highlight:
        hit = by_name.get(want.lower())
        if hit is None:
            continue
        name, polys = hit
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
        # through the colour — a flat fill reads as a sticker.
        lit = np.clip(wash * (1.0 + (relief[..., None] - 1.0) * LAND_RELIEF_GAIN),
                      0, 255)
        edge = outline_mask(polys, view, 3)

        ys0, ys1 = int(max(by0 - 4, 0)), int(min(by1 + 4, OUT_H))
        xs0, xs1 = int(max(bx0 - 4, 0)), int(min(bx1 + 4, OUT_W))
        out.append(Wash(name, (ys0, ys1, xs0, xs1),
                        mask[ys0:ys1, xs0:xs1],
                        lit[ys0:ys1, xs0:xs1],
                        edge[ys0:ys1, xs0:xs1]))
    return out


def compose(plate: np.ndarray, washes: list[Wash],
            alphas: list[float]) -> np.ndarray:
    """The plate with each wash blended at its own strength (0..1)."""
    img = plate.copy()
    for w, a in zip(washes, alphas):
        if a <= 0.0:
            continue
        y0, y1, x0, x1 = w.box
        sub = img[y0:y1, x0:x1]
        aa = (FLAG_ALPHA * a * w.mask)[..., None]
        sub *= (1 - aa)
        sub += w.lit * aa
        ee = (0.85 * a * w.edge)[..., None]
        sub *= (1 - ee)
        sub += COAST_RGB * ee
    return img


def _ease(t: float) -> float:
    """Cosine ease, matching `memoacts_core.schedule` so a wash arriving and a
    camera moving feel like the same hand."""
    t = min(max(t, 0.0), 1.0)
    return (1 - math.cos(math.pi * t)) / 2


def stagger(n: int, t: float, *, fill: float, fade: float) -> list[float]:
    """Strength of each of `n` washes at time `t`, arriving one after another.

    They arrive in the order the countries were named, because the narration
    names them in order and a map that fills all at once says "these three"
    where the line says "Latvia, Estonia and Lithuania".
    """
    if n <= 0:
        return []
    step = 0.0 if n == 1 else max(fill - fade, 0.0) / (n - 1)
    return [_ease((t - i * step) / fade if fade > 0 else 1.0) for i in range(n)]


def parse_marker(spec: str) -> tuple[float, float, str]:
    """`lon,lat[,label]` -> (lon, lat, label). Decimal degrees, east/north +."""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) < 2:
        raise SystemExit(f"marker {spec!r}: expected lon,lat[,label]")
    try:
        lon, lat = float(parts[0]), float(parts[1])
    except ValueError:
        raise SystemExit(f"marker {spec!r}: lon and lat must be decimal degrees")
    return lon, lat, ",".join(parts[2:]).strip()


def draw_markers(img: np.ndarray, view,
                 markers: list[tuple[float, float, str]]) -> np.ndarray:
    """Pin a place the narration names but the geodata does not carry.

    Natural Earth 1:50m is country outlines: there is no Reims in it, and at
    this scale there is no terrain feature that says "here" either. So a town
    is drawn rather than found — a dot, and its name in the reel's own caption
    face so the map speaks in the same voice as the subtitles.

    Sized as a fraction of the plate, which means the pin *grows* as a shot
    pushes into it. That is the intended reading: the closer the camera gets,
    the more the label asserts itself.
    """
    if not markers:
        return img
    from PIL import ImageFont

    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    r = max(4, OUT_W // 200)
    try:
        font = ImageFont.truetype(
            str(ROOT / "assets" / "fonts" / "ShareTechMono-Regular.ttf"),
            max(14, OUT_W // 40))
    except OSError:
        font = ImageFont.load_default()

    dark = tuple(int(v) for v in SEA_DEEP)
    light = tuple(int(v) for v in COAST_RGB)
    for lon, lat, label in markers:
        x, y = to_pixels(np.array([project(lon, lat)], dtype=np.float64), view)[0]
        # Ring first, then the dot: over a pale wash the dot alone disappears.
        d.ellipse([x - r * 2.6, y - r * 2.6, x + r * 2.6, y + r * 2.6],
                  outline=dark, width=max(2, r // 2))
        d.ellipse([x - r * 2.0, y - r * 2.0, x + r * 2.0, y + r * 2.0],
                  outline=light, width=max(2, r // 2))
        d.ellipse([x - r, y - r, x + r, y + r], fill=light, outline=dark)
        if label:
            d.text((x + r * 3.6, y - r * 1.6), label, font=font, fill=light,
                   stroke_width=max(2, r // 2), stroke_fill=dark)
    return np.asarray(im, dtype=np.float32)


def marker_focus(view, lon: float, lat: float, width: float) -> str:
    """The `focus` value shots.csv needs to end a push-in on this marker.

    Printed rather than left to be measured off the finished plate by eye: the
    shot list wants fractions of the source, and getting them from the same
    projection that drew the dot is the only way they agree exactly.
    """
    x, y = to_pixels(np.array([project(lon, lat)], dtype=np.float64), view)[0]
    return f"{x / OUT_W:.3f} {y / OUT_H:.3f} {width:.3f}"


def draw(features: list[dict], highlight: list[str], dest: Path,
         context: float = 2.6, relief_path: Path = DEFAULT_RELIEF,
         markers: list[tuple[float, float, str]] | None = None) -> Path:
    """The finished plate as a single image — every wash at full strength."""
    feats = [(name_of(f["properties"]), projected_rings(f)) for f in features]
    feats = [(n, p) for n, p in feats if p]
    view = view_for(feats, highlight, context)
    relief = sample_relief(view, Image.open(relief_path).convert("L"))
    washes = _washes(feats, highlight, view, relief)
    img = compose(_plate(feats, view, relief), washes, [1.0] * len(washes))
    img = draw_markers(img, view, markers or [])

    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(dest)
    for lon, lat, label in markers or []:
        print(f"  marker {label or '(unnamed)'} at {lon},{lat} -> "
              f"shots.csv focus \"{marker_focus(view, lon, lat, 1 / 2.6)}\" "
              f"(third number is the end width; smaller pushes in further)")
    return dest


def sequence(features: list[dict], highlight: list[str], dest: Path, *,
             frames: int, fps: int = 30, fill: float = 5.0, fade: float = 1.2,
             already: list[str] | None = None, context: float = 2.6,
             relief_path: Path = DEFAULT_RELIEF) -> Path:
    """The plate as a clip whose flags wash in one country at a time.

    `already` names countries that are filled from the first frame — the reel
    moves west across two map shots, and a country that has already changed its
    calendar has not un-changed it by the next line. Carrying them keeps the
    second plate a continuation rather than a fresh assertion.

    Written as a video because the renderer already treats footage as "a still
    that changes every frame" (memoacts_core.video): the shot then takes any
    motion preset, and nothing in the reel path has to know this one is drawn.
    """
    already = already or []
    ordered = already + [h for h in highlight if h not in already]

    feats = [(name_of(f["properties"]), projected_rings(f)) for f in features]
    feats = [(n, p) for n, p in feats if p]
    # Framed on what is arriving, not on everything shown. Including the
    # carried-over countries in the fit stretched the second plate from the
    # Baltics to Ukraine and then padded that by the context factor, which put
    # the whole of Europe on screen and made the two countries the line is
    # actually about too small to read. Carried flags are continuity, not
    # subject; they appear if they fall inside the frame.
    view = view_for(feats, highlight, context)
    relief = sample_relief(view, Image.open(relief_path).convert("L"))

    plate = _plate(feats, view, relief)
    held = _washes(feats, already, view, relief)
    arriving = _washes(feats, [h for h in ordered if h not in already],
                       view, relief)

    def gen():
        for i in range(frames):
            t = i / fps
            alphas = [1.0] * len(held) + stagger(len(arriving), t,
                                                 fill=fill, fade=fade)
            img = compose(plate, held + arriving, alphas)
            yield Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    sys.path.insert(0, str(ROOT))
    from memoacts_core.render import encode
    dest.parent.mkdir(parents=True, exist_ok=True)
    # crf 8: flat washes over shaded relief band badly at ordinary rates, and
    # this is an authored source the reel will crop into, not a delivery file.
    encode(gen(), dest, fps, crf=8, out_w=OUT_W, out_h=OUT_H, max_mbps=None)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON)
    ap.add_argument("--relief", type=Path, default=DEFAULT_RELIEF)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--highlight", nargs="*", default=[])
    ap.add_argument("--name", default="map")
    ap.add_argument("--context", type=float, default=2.6)
    ap.add_argument("--frames", type=int, default=0,
                    help="render a clip of this many frames whose flags wash "
                         "in one country at a time, instead of a finished PNG")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--fill", type=float, default=5.0,
                    help="seconds for every wash to have arrived (default: 5)")
    ap.add_argument("--fade", type=float, default=1.2,
                    help="seconds one country takes to arrive (default: 1.2)")
    ap.add_argument("--already", nargs="*", default=[],
                    help="countries already washed in the first frame, carried "
                         "over from an earlier map shot")
    ap.add_argument("--marker", action="append", default=[],
                    help="lon,lat[,label] — pin a town the geodata has no "
                         "record of; repeatable. Stills only")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="multiply the plate size (default 1440x2560). A shot "
                         "can push in by the plate's own factor over the 1080 "
                         "output, so 2.0 buys a 2.67x move instead of 1.33x")
    ap.add_argument("--palette", default="terrain", choices=sorted(PALETTES),
                    help="land and water colours; the non-default ones are "
                         "sampled from the reel's document scans")
    args = ap.parse_args()

    use_palette(args.palette)

    if args.scale != 1.0:
        # Rebound rather than threaded through: every helper here reads these
        # as module state, and a second size argument on each would be a wider
        # change than the feature deserves.
        global OUT_W, OUT_H
        OUT_W, OUT_H = int(OUT_W * args.scale) // 2 * 2, \
            int(OUT_H * args.scale) // 2 * 2
        print(f"plate {OUT_W}x{OUT_H} "
              f"(reach {OUT_W / 1080:.2f}x over a 1080-wide output)")

    markers = [parse_marker(m) for m in args.marker]
    data = json.loads(args.geojson.read_text(encoding="utf-8"))
    # Not optional and deliberately without a --skip flag: every plate this
    # tool draws must show Crimea and Sevastopol as Ukraine. See above.
    correct_crimea(data["features"])
    if args.frames:
        if markers:
            print("markers are drawn on stills only; ignoring --marker")
        dest = sequence(data["features"], args.highlight,
                        args.out / f"{args.name}.mp4", frames=args.frames,
                        fps=args.fps, fill=args.fill, fade=args.fade,
                        already=args.already, context=args.context,
                        relief_path=args.relief)
        print(f"wrote {dest}  {args.frames} frames  "
              f"arriving={args.highlight or '(none)'}  "
              f"already={args.already or '(none)'}")
        return 0
    dest = draw(data["features"], args.highlight,
                args.out / f"{args.name}.png", args.context, args.relief,
                markers)
    print(f"wrote {dest}  highlight={args.highlight or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
