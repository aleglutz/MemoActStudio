"""HTTP routes behind the shot-table widget.

The widget edits `shots.csv` — the same file the author edits by hand, and the
only place the edit decisions live. These routes are the door: they read the
project, merge the table onto the script's shots so every shot has a row to
show whether or not the file mentions it, and write the file back through
`shotlist.write_table`, which keeps the header, the unknown columns and the `#`
comment rows the author put there.

Everything here is deliberately thin. The knowledge of what a shot list means
belongs to `memoacts_core.shotlist`; what these add is HTTP, thumbnails and the
one merge the file format does not do for itself.

Routes are registered on ComfyUI's own aiohttp app, so they live at
`/memoacts/...` on the same origin as the UI and need no CORS or second port.
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from aiohttp import web

try:
    from server import PromptServer
    #: ComfyUI's own route table, so these live on the same origin as the UI.
    _ROUTES = PromptServer.instance.routes
except (ImportError, AttributeError):       # imported without a running server
    _ROUTES = web.RouteTableDef()

from .memoacts_core import effects as fx
from .memoacts_core import sfx as sfxlib
from .memoacts_core import shotlist
from .memoacts_core.pipeline import (ProjectError, create_project,
                                     merge_scene, read_project,
                                     split_scene)
from .memoacts_core.project import MEDIA_DIRS, sentences_of
from .memoacts_core.schedule import (FOCUSABLE, PRESETS as MOTION_PRESETS,
                                     base_window, focus_limits)
from .memoacts_core.video import is_video, probe
from .nodes_project import PROJECTS_DIR

#: Longest edge of a thumbnail. Big enough to frame a crop on, small enough
#: that twenty of them arrive at once without thought.
THUMB_PX = 480

#: The decision columns, in the order the widget shows them. `shot` is not one:
#: it addresses the row rather than deciding anything.
EDIT_COLUMNS = [c for c in shotlist.COLUMNS if c != "shot"]


def _project(request: web.Request) -> Path:
    """The project a request names, refusing anything outside `projects/`.

    The widget only ever names a folder it was given, but a route that takes a
    path from a browser and opens it has to say what it will not open.
    """
    name = request.query.get("project", "") or ""
    folder = Path(name)
    if not folder.is_absolute():
        folder = PROJECTS_DIR / name
    folder = folder.resolve()
    if PROJECTS_DIR.resolve() not in folder.parents:
        raise web.HTTPBadRequest(reason=f"not a project folder: {name}")
    if not folder.is_dir():
        raise web.HTTPNotFound(reason=f"no such project: {name}")
    return folder


def _cue_text(seconds: float | None) -> str:
    """The cue as the script writes it, which is how a row should address it."""
    if seconds is None:
        return ""
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def _cells(raw: dict[str, str]) -> dict[str, str]:
    """A row's decision cells exactly as the file spells them.

    Not the typed `ShotEdit`: an in-point written `0:40` types to `40.0`, and
    handing that back would rewrite the author's file on the next save for no
    reason anyone asked for. The widget shows what is written; the pipeline
    reads what it means.
    """
    lower = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
    return {c: lower.get(c, "") for c in EDIT_COLUMNS}


def _timings(folder: Path, texts: list[str]) -> tuple[list[dict] | None, str, float]:
    """Per-shot timings from the last compile, or a reason there are none.

    `generated/shots.json` already holds `t_start`, `t_end`, `n_frames` and
    `confidence` for every shot, written by the Shot Table node's last run. The
    storyline draws its bars from that: no aligner, no model, one file read.

    **The guard is the point of this function.** A `shots.json` left over from a
    different script would draw confident, wrong bars — `legends_of_surrender`
    has exactly that today, 20 shots against a 28-scene script, and
    `89-in-comfy` went 20 → 34 in one edit. So the file is used only when it
    describes *this* script: same number of shots, and the same words in each.
    Anything else is "no timing yet", which is honest and costs a Run to fix.
    """
    path = folder / "generated" / "shots.json"
    if not path.is_file():
        return None, "no timing yet — run Shot Table once to see it", 0.0
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{path.name} could not be read: {exc}", 0.0

    shots = doc.get("shots") or []
    if len(shots) != len(texts):
        return None, (f"the timing on disk is for {len(shots)} scenes and the "
                      f"script now has {len(texts)} — run Shot Table again"), 0.0
    if any((s.get("text") or "") != t for s, t in zip(shots, texts)):
        return None, ("the script has changed since the timing was computed — "
                      "run Shot Table again"), 0.0

    out = [{"t_start": s.get("t_start"), "t_end": s.get("t_end"),
            "n_frames": s.get("n_frames"),
            "confidence": s.get("confidence"),
            "estimated": bool(s.get("estimated"))} for s in shots]
    return out, "", float(doc.get("duration_s") or 0.0)


def _index_of(edit: shotlist.ShotEdit, cues: list[float | None]) -> int | None:
    """Which shot a row addresses — by number, or by the cue it was written for."""
    if edit.index is not None:
        return edit.index - 1 if 1 <= edit.index <= len(cues) else None
    if edit.cue is not None:
        for i, cue in enumerate(cues):
            if cue == edit.cue:
                return i
    return None


@_ROUTES.get("/memoacts/projects")
async def projects(request: web.Request) -> web.Response:
    names = sorted(p.name for p in PROJECTS_DIR.iterdir()
                   if p.is_dir() and not p.name.startswith(".")) \
        if PROJECTS_DIR.is_dir() else []
    return web.json_response({"projects": names})


@_ROUTES.get("/memoacts/shots")
async def shots(request: web.Request) -> web.Response:
    """The whole editing surface in one response.

    One entry per shot in the script, carrying what the shot says, what the
    table decided for it, and what it actually resolved to — because "which
    image did this shot end up with" is a different question from "which image
    did I name", and the second one is the one a person can answer wrongly.
    """
    folder = _project(request)
    try:
        read = read_project(folder)
    except ProjectError as exc:
        return web.json_response({"error": str(exc)}, status=400)

    table = shotlist.read_table(folder / "shots.csv")
    cues = [s.cue for s in read.script_shots]

    rows: list[dict | None] = [None] * len(read.script_shots)
    for raw, edit in shotlist.rows_with_edits(table):
        i = _index_of(edit, cues)
        if i is not None:
            rows[i] = _cells(raw)

    timings, timing_note, duration_s = _timings(
        folder, [s.text for s in read.script_shots])

    out = []
    for i, (shot, media) in enumerate(zip(read.script_shots, read.media)):
        out.append({
            "id": i + 1,
            "cue": _cue_text(shot.cue),
            "text": shot.text,
            "label_in_script": shot.label,
            "resolved": media.name,
            "resolved_dir": media.parent.name,
            "exists": media.exists(),
            "row": rows[i] or {c: "" for c in EDIT_COLUMNS},
            # None until a compile has run against this script. The storyline
            # draws bars from it and says why when it is missing, rather than
            # drawing nothing and leaving the reason to be guessed.
            "timing": timings[i] if timings else None,
            # Where this scene could honestly be cut in two. Sent with the
            # scene rather than fetched per click, and computed by the same
            # function the split itself uses, so the boundary the panel offers
            # is the boundary the script gets.
            "sentences": sentences_of([shot.text]),
        })
    return web.json_response({
        "project": folder.name,
        "timing_note": timing_note,
        "duration_s": duration_s,
        "columns": EDIT_COLUMNS,
        "motions": list(MOTION_PRESETS),
        "focusable": list(FOCUSABLE),
        "anchors": ["", "center", "top"],
        "effects": [""] + sorted(set(fx.PRESETS) - {"none"}),
        # What each look costs, as a multiple of a clean render (effects.COST).
        # Shown beside the name because it is the one edit decision that is paid
        # for in minutes, on a machine eight students are sharing.
        "effect_cost": fx.COST,
        "shots": out,
        "media": _media(folder),
        "warnings": read.warnings,
    })


@_ROUTES.post("/memoacts/shots")
async def save_shots(request: web.Request) -> web.Response:
    """Write the edits back into `shots.csv`, keeping everything else.

    A row is addressed by the cue the script wrote for it wherever there is
    one: inserting a line renumbers every shot after it, and a cue still points
    at the line it was written for. A shot whose decisions are all blank loses
    its row entirely, which is what keeps the file as short as the number of
    decisions actually made.
    """
    folder = _project(request)
    body = await request.json()
    incoming = {int(s["id"]): s.get("row", {}) for s in body.get("shots", [])}

    try:
        read = read_project(folder)
    except ProjectError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    cues = [s.cue for s in read.script_shots]
    path = folder / "shots.csv"
    table = shotlist.read_table(path)

    # A row this file already has, per shot, so an edit lands on it rather than
    # appending a second row addressing the same shot.
    existing: dict[int, dict[str, str]] = {}
    for raw, edit in shotlist.rows_with_edits(table):
        i = _index_of(edit, cues)
        if i is not None:
            existing[i + 1] = raw
    # By identity, not by value: two rows that happen to read the same are still
    # two rows, and comparing cells would drop both.
    rebuilt = {id(raw) for raw in existing.values()}

    kept: list[dict[str, str]] = []
    for raw in table.rows:
        key = shotlist.row_key(raw)
        if not key or key.startswith("#"):
            kept.append(raw)                       # comments and blanks, as written
            continue
        if id(raw) in rebuilt:
            continue                               # rebuilt below, in shot order
        kept.append(raw)                           # a row addressing nothing we know

    written = []
    for shot_id in sorted(incoming):
        cells = {c: (incoming[shot_id].get(c) or "").strip() for c in EDIT_COLUMNS}
        if not any(cells.values()):
            continue                               # no decisions: no row
        row = dict(existing.get(shot_id) or {})
        row.update(cells)
        cue = _cue_text(cues[shot_id - 1]) if shot_id <= len(cues) else ""
        row[_shot_column(table)] = cue or str(shot_id)
        written.append(row)

    table.rows = kept + written
    try:
        shotlist.write_table(path, table)
    except shotlist.TableLocked as exc:
        # A 400 with a sentence, not aiohttp's plain-text 500. The panel calls
        # `.json()` on the answer, and a 500 page is not JSON — which is how a
        # spreadsheet holding the file arrived in the browser as
        # "JSON.parse: unexpected non-whitespace character after JSON data".
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response({"saved": len(written), "path": str(path)})


def _shot_column(table: shotlist.ShotTable) -> str:
    """The header cell that addresses a row, however the author capitalised it."""
    for name in table.fieldnames:
        if (name or "").strip().lower() == "shot":
            return name
    return "shot"


def _media(folder: Path) -> list[dict]:
    """Every file a shot may name, with the headroom it has for a move.

    `max_zoom` below 1.0 means the source cannot fill a 1080-wide frame even
    before any movement — the resolution guard will enlarge it. Showing that
    here is the point: the guard warns at render time, by which point the image
    has already been chosen (`GAPS.md`).
    """
    out = []
    for d in MEDIA_DIRS:
        directory = folder / d
        if not directory.is_dir():
            continue
        for p in sorted(directory.iterdir()):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                size = probe(p).size if is_video(p) else _still_size(p)
            except Exception:                                      # noqa: BLE001
                continue
            w0, _ = base_window(*size)
            lo, hi = focus_limits(*size)
            out.append({"name": p.name, "dir": d, "width": size[0],
                        "height": size[1], "video": is_video(p),
                        "max_zoom": round(w0 / 1080, 2),
                        # What a focus rectangle may be, as fractions of the
                        # source width. The picker clamps to these rather than
                        # letting someone draw a window the guard then widens.
                        "focus_min_w": round(lo, 4),
                        "focus_max_w": round(hi, 4)})
    return out


def _still_size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


@_ROUTES.get("/memoacts/thumb")
async def thumb(request: web.Request) -> web.Response:
    """One media file as a small JPEG. A video gives up its first frame.

    `px` asks for a bigger one. The shelf wants twenty small pictures at once
    and the picker wants one it can place a rectangle on precisely: a page 4096
    px wide shown at 480 puts its tightest legal window at 92 px on screen, and
    a 92-pixel rectangle is not something anybody can aim. Same route, same
    file, different question.
    """
    folder = _project(request)
    name = request.query.get("file", "")
    try:
        px = min(max(int(request.query.get("px") or THUMB_PX), 128), 1600)
    except ValueError:
        px = THUMB_PX
    found = next((folder / d / name for d in MEDIA_DIRS
                  if (folder / d / name).is_file()), None)
    if found is None:
        raise web.HTTPNotFound(reason=f"no media named {name}")

    from PIL import Image
    if is_video(found):
        from .memoacts_core.video import frames
        image = next(iter(frames(found, 1)))
    else:
        from .memoacts_core.render import load_source
        image = load_source(found)
    image.thumbnail((px, px), Image.Resampling.LANCZOS)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=82)
    return web.Response(body=buf.getvalue(), content_type="image/jpeg",
                        headers={"Cache-Control": "no-cache"})


@_ROUTES.get("/memoacts/sfx")
async def sound_design(request: web.Request) -> web.Response:
    """`sfx.csv` as text, for the box on the Sound Design node.

    A project with no sound design yet gets the starter table rather than an
    empty string — one commented row per shot, carrying what the shot says, so
    the first thing a person sees is the format and their own script rather
    than a blank field. `rows` tells the caller which of the two it received;
    the two read identically and mean very different things.
    """
    folder = _project(request)
    path = folder / "sfx.csv"
    table = sfxlib.read_table(path)
    rows = len(table.rows)
    if not rows:
        try:
            read = read_project(folder)
        except ProjectError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        # The template needs shot ids and their text, which is what the script
        # already carries — no alignment, so this stays instant.
        table = sfxlib.template({"shots": [
            {"id": i, "text": s.text}
            for i, s in enumerate(read.script_shots, 1)]})
    return web.json_response({"cues": sfxlib.to_text(table), "rows": rows,
                              "path": str(path)})


@_ROUTES.get("/memoacts/script")
async def script(request: web.Request) -> web.Response:
    folder = _project(request)
    path = folder / "script.md"
    return web.json_response(
        {"script": path.read_text(encoding="utf-8") if path.exists() else ""})


@_ROUTES.post("/memoacts/script")
async def save_script(request: web.Request) -> web.Response:
    """Write `script.md`. The words are ground truth, so this is the one place
    the interface writes them, and it writes exactly what it was given."""
    folder = _project(request)
    body = await request.json()
    path = folder / "script.md"
    path.write_text(body.get("script", ""), encoding="utf-8")
    return web.json_response({"saved": str(path)})


@_ROUTES.post("/memoacts/scene")
async def move_boundary(request: web.Request) -> web.Response:
    """Merge a scene into the one before it, or cut one in two.

    A scene boundary lives in `script.md`, because a scene is a unit of what is
    said — so this is the one editing action in the panel that changes the
    script rather than the shot list. It carries `shots.csv` with it, since
    every scene after the boundary shifts by one and a row addressing a number
    would otherwise quietly name a different line.

    Alignment runs again afterwards, and should: the words are unchanged but
    which of them belong to which shot is not.
    """
    folder = _project(request)
    body = await request.json()
    action = body.get("action")
    index = int(body.get("id") or 0)
    try:
        if action == "merge":
            res = merge_scene(folder, index)
        elif action == "split":
            res = split_scene(folder, index, int(body.get("at") or 1))
        else:
            raise web.HTTPBadRequest(reason=f"unknown action {action!r}")
        return web.json_response({
            "scenes": res.scenes, "moved": res.moved_rows,
            "note": res.note, "warnings": res.warnings})
    except ProjectError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except shotlist.TableLocked as exc:
        return web.json_response({"error": str(exc)}, status=400)


@_ROUTES.post("/memoacts/project")
async def new_project(request: web.Request) -> web.Response:
    """Make an empty project: four folders and the two files a person fills in.

    The folders and the two files are `pipeline.create_project`, which the Set
    Narration node calls as well. This route used to spell them out itself, and
    a second list of what a project is would have started disagreeing with the
    first the day either grew a folder.

    Unlike the node, this refuses a name that already exists. A route called
    "new" that quietly hands back somebody else's project is how a student
    overwrites a neighbour's work on a shared machine.
    """
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise web.HTTPBadRequest(reason="a project name, without a path")
    folder = PROJECTS_DIR / name
    if folder.exists():
        raise web.HTTPBadRequest(reason=f"{name} already exists")
    create_project(folder)
    return web.json_response({"project": name, "path": str(folder)})
