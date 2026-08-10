"""Stylised map of Europe with named countries filled in their flag colours.

    python tools/render_map.py --out projects/<name>/maps \n        --name map_poland_ukraine --highlight Poland Ukraine

Why this is drawn and not generated: a diffusion model invents coastlines and
smears borders, and a wrong map of Europe in a museum film about historical
memory is worse than no map. The geometry is Natural Earth (public domain,
1:50m), rendered with matplotlib. It is authored graphics — there is no
provenance question of the kind that hangs over synthetic "archival" imagery
(SPEC §9.7).

Countries are filled with their flag's stripes clipped to the country outline,
rather than one flat colour, because a single colour is ambiguous between
several of the countries this reel names.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.patches import Rectangle                           # noqa: E402
from matplotlib.path import Path as MplPath                        # noqa: E402
from matplotlib.patches import PathPatch                           # noqa: E402

#: Flag stripes, in draw order. "h" = horizontal bands, "v" = vertical.
#: The United Kingdom is approximated: a Union Jack clipped to an island
#: outline reads as noise at this size, so it takes its three colours as bands.
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

#: Frame and view. The extent has to hold Reims and London in the west and
#: Armenia in the east, which is wider than a 9:16 frame wants — so the map
#: sits as a band with clear ground above and below, echoing the reel's own
#: stacked-band language rather than fighting it.
#: Vendored so the tool runs offline — see assets/geo/SOURCE.md.
DEFAULT_GEOJSON = (Path(__file__).resolve().parents[1]
                  / "assets" / "geo" / "ne_50m_admin_0_countries.geojson")

#: 1440x2560 rather than 1080x1920: a plate made at exactly output size has no
#: headroom and cannot move, the same trap the stacked composites hit.
OUT_W, OUT_H = 1440, 2560
LON_MIN, LON_MAX = -11.0, 47.0
LAT_MIN, LAT_MAX = 34.0, 71.0
LAT0 = math.radians((LAT_MIN + LAT_MAX) / 2)

INK = "#0B0B0A"          # sea
LAND = "#3A3833"         # countries not being named
BORDER = "#565349"
COAST = "#5C5A55"


def project(lon: float, lat: float) -> tuple[float, float]:
    """Equirectangular with a cosine correction at the view's mid-latitude.

    Not an equal-area projection and not trying to be — it keeps Europe's
    proportions plausible at this scale without a projection dependency.
    """
    return lon * math.cos(LAT0), lat


def rings(geom: dict) -> list[list[tuple[float, float]]]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def country_paths(feature: dict) -> list[MplPath]:
    out = []
    for ring in rings(feature["geometry"]):
        pts = [project(x, y) for x, y in ring]
        # Skip far-flung territories (French Guiana, Russian Far East) that
        # would otherwise stretch the view to nothing.
        if not any(LON_MIN <= x / math.cos(LAT0) <= LON_MAX and
                   LAT_MIN <= y <= LAT_MAX for x, y in pts):
            continue
        out.append(MplPath(pts))
    return out


def name_of(props: dict) -> str:
    for key in ("NAME_EN", "NAME", "ADMIN"):
        if props.get(key):
            return props[key]
    return ""


def view_for(features: list[dict], highlight: list[str], context: float
             ) -> tuple[float, float, float, float]:
    """Frame the shot on what is being named.

    A Europe-wide view makes the Baltic states about a hundredth of the frame,
    which is useless under a line that is *about* the Baltic states. So the
    view is fitted to the highlighted countries and then opened out by
    `context` so the viewer still reads "Europe" rather than an anonymous
    coastline. With nothing highlighted, the whole continent is shown.
    """
    wanted = {h.lower() for h in highlight}
    xs, ys = [], []
    for f in features:
        if name_of(f["properties"]).lower() not in wanted:
            continue
        for path in country_paths(f):
            v = path.vertices
            xs += [v[:, 0].min(), v[:, 0].max()]
            ys += [v[:, 1].min(), v[:, 1].max()]

    fx0, fx1 = project(LON_MIN, 0)[0], project(LON_MAX, 0)[0]
    if not xs:
        cx, cy = (fx0 + fx1) / 2, (LAT_MIN + LAT_MAX) / 2
        half_x = (fx1 - fx0) / 2
    else:
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        half_x = max((max(xs) - min(xs)) / 2,
                     (max(ys) - min(ys)) / 2 * OUT_W / OUT_H) * context

    # Never open out past the whole continent, and never crop tighter than a
    # frame that still shows neighbours.
    half_x = min(half_x, (fx1 - fx0) / 2)
    half_x = max(half_x, project(3.5, 0)[0])
    half_y = half_x * OUT_H / OUT_W
    return cx - half_x, cx + half_x, cy - half_y, cy + half_y


def draw(features: list[dict], highlight: list[str], dest: Path,
         title: str = "", context: float = 2.6) -> Path:
    fig_w, fig_h = OUT_W / 100, OUT_H / 100
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    fig.patch.set_facecolor(INK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(INK)

    vx0, vx1, vy0, vy1 = view_for(features, highlight, context)
    ax.set_xlim(vx0, vx1)
    ax.set_ylim(vy0, vy1)
    ax.axis("off")

    wanted = {h.lower() for h in highlight}
    for f in features:
        name = name_of(f["properties"])
        paths = country_paths(f)
        if not paths:
            continue
        lit = name.lower() in wanted

        for path in paths:
            ax.add_patch(PathPatch(path, facecolor=LAND, edgecolor=BORDER,
                                   linewidth=0.6, zorder=1))
        if not lit:
            continue

        orient, colours = FLAGS.get(name, ("h", ["#FFFFFF"]))
        # One flag across the whole country, not one per polygon. Measured per
        # polygon, Estonia's islands each got a complete blue/black/white of
        # their own and read as confetti beside the mainland.
        bx0 = min(p.vertices[:, 0].min() for p in paths)
        bx1 = max(p.vertices[:, 0].max() for p in paths)
        by0 = min(p.vertices[:, 1].min() for p in paths)
        by1 = max(p.vertices[:, 1].max() for p in paths)
        for path in paths:
            n = len(colours)
            for i, col in enumerate(colours):
                if orient == "h":
                    # first colour on top, as flags are read
                    y = by1 - (by1 - by0) * (i + 1) / n
                    rect = Rectangle((bx0, y), bx1 - bx0, (by1 - by0) / n,
                                     facecolor=col, edgecolor="none", zorder=2)
                else:
                    x = bx0 + (bx1 - bx0) * i / n
                    rect = Rectangle((x, by0), (bx1 - bx0) / n, by1 - by0,
                                     facecolor=col, edgecolor="none", zorder=2)
                ax.add_patch(rect)
                rect.set_clip_path(path, transform=ax.transData)
            ax.add_patch(PathPatch(path, facecolor="none", edgecolor=COAST,
                                   linewidth=1.4, zorder=3))

    if title:
        ax.text(0.5, 0.055, title, transform=ax.transAxes, ha="center",
                va="center", color="#E8E4DA", fontsize=26,
                family="monospace", zorder=4)

    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, facecolor=INK)
    plt.close(fig)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--highlight", nargs="*", default=[])
    ap.add_argument("--name", default="map")
    ap.add_argument("--title", default="")
    ap.add_argument("--context", type=float, default=2.6,
                    help="how far to open out past the named countries")
    args = ap.parse_args()

    data = json.loads(args.geojson.read_text(encoding="utf-8"))
    dest = draw(data["features"], args.highlight,
                args.out / f"{args.name}.png", args.title, args.context)
    print(f"wrote {dest}  highlight={args.highlight or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
