/**
 * The shot list, without a layout — everything two surfaces would otherwise
 * each have to know.
 *
 * The storyline panel draws it as scenes and a shelf of pictures; the Sound
 * Design node only needs to know which project a node belongs to. Both used to
 * live in `memoacts.js` beside a `<table>`; the table is gone and this is what
 * was underneath it, unchanged.
 *
 * Nothing here touches the DOM tree of any particular view. `ShotsModel` is the
 * file and the rules for editing it, `FocusPicker` is the one piece of geometry
 * that is genuinely reusable, and `el` / `injectCSS` / `findProject` are the
 * three helpers that had no better home.
 *
 * No top-level side effects: ComfyUI imports every `.js` under `WEB_DIRECTORY`
 * in parallel, at any depth, so a module that did something on import would do
 * it at an unpredictable moment.
 */
import { app } from "../../scripts/app.js";

export function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) node.append(child);
  return node;
}

/** Add a stylesheet once, however many times the module is asked to. */
export function injectCSS(id, css) {
  if (document.getElementById(id)) return;
  document.head.append(el("style", { id, textContent: css }));
}

/**
 * Walk back along the wires until something knows which project this is.
 *
 * Still needed by the Sound Design node, whose project arrives through the
 * graph. The storyline panel does not use it — a sidebar tab has no node to
 * start from, so it asks the server for the list and lets a person choose.
 */
export function findProject(node) {
  const graph = app.rootGraph ?? app.graph;
  const seen = new Set();
  const walk = (n, depth) => {
    if (!n || depth > 8 || seen.has(n.id)) return null;
    seen.add(n.id);
    const dir = n.widgets?.find((w) => w.name === "project_dir")?.value;
    if (dir && String(dir).trim()) return String(dir).trim();
    const pick = n.widgets?.find((w) => w.name === "project")?.value;
    if (pick && (n.comfyClass === "MemoActsProject"
                 || n.comfyClass === "MemoActsSetNarration")) return String(pick);
    for (const input of n.inputs ?? []) {
      const link = input.link != null ? graph.links[input.link] : null;
      const found = link ? walk(graph.getNodeById(link.origin_id), depth + 1) : null;
      if (found) return found;
    }
    return null;
  };
  return walk(node, 0);
}

/** Whichever project the open graph is about, or null. */
export function projectFromGraph() {
  const graph = app.rootGraph ?? app.graph;
  if (!graph) return null;
  for (const type of ["MemoActsShotTable", "MemoActsProject",
                      "MemoActsSetNarration"]) {
    for (const node of graph.findNodesByType?.(type) ?? []) {
      const found = findProject(node);
      if (found) return found;
    }
  }
  return null;
}

/**
 * `shots.csv` as the server hands it over, plus the rules for editing it.
 *
 * The edits live on `data.shots[i].row` — the same cells the file spells —
 * because the server writes back exactly what it is given and keeps everything
 * it was not told about: the header as the author wrote it, unknown columns,
 * and the `#` comment rows. A round trip with no edits leaves `git diff` clean,
 * and that is a property worth not breaking.
 */
export class ShotsModel {
  constructor() {
    this.project = null;
    this.data = null;
    this.dirty = new Set();          // ids edited since the last save
    this.onStatus = () => {};
    this.onData = () => {};
  }

  say(text, bad = false) { this.onStatus(text, bad); }

  async projects() {
    const res = await fetch("/memoacts/projects");
    return (await res.json()).projects ?? [];
  }

  async load(project) {
    this.project = project ?? this.project;
    if (!this.project) { this.say("choose a project", true); return; }
    this.say("loading…");
    try {
      const res = await fetch(
        `/memoacts/shots?project=${encodeURIComponent(this.project)}`);
      const body = await res.json();
      if (!res.ok || body.error) throw new Error(body.error || res.statusText);
      this.data = body;
      this.dirty.clear();
      this.onData();
      this.say(`${body.shots.length} scenes · ${body.project}`);
    } catch (err) {
      this.data = null;
      this.onData();
      this.say(String(err.message || err), true);
    }
  }

  async persist() {
    if (!this.data) return;
    this.say("saving…");
    try {
      const res = await fetch(
        `/memoacts/shots?project=${encodeURIComponent(this.project)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            shots: this.data.shots.map((s) => ({ id: s.id, row: s.row })),
          }),
        },
      );
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || res.statusText);
      // Re-read rather than trust the local copy: the file decides what a row
      // says now, and a shot whose decisions were all cleared has lost its row.
      await this.load();
      this.say(`saved ${body.saved} rows to shots.csv`);
    } catch (err) {
      this.say(String(err.message || err), true);
    }
  }

  setCell(shot, key, value) {
    if ((shot.row[key] ?? "") === value) return false;
    shot.row[key] = value;
    this.dirty.add(shot.id);
    this.say(`${this.dirty.size} scene(s) edited — not saved`);
    return true;
  }

  costOf(name) { return this.data?.effect_cost?.[name] ?? 1; }

  /** The media record for whatever this shot will actually show. */
  mediaFor(shot) {
    const name = shot.row.media || shot.resolved;
    return this.data?.media.find((m) => m.name === name) || null;
  }

  /** What this shot shows, whether it was chosen or cycled to. */
  shownName(shot) { return shot.row.media || shot.resolved || ""; }

  thumbURL(name) {
    return name
      ? `/memoacts/thumb?project=${encodeURIComponent(this.project)}`
        + `&file=${encodeURIComponent(name)}`
      : "";
  }

  /** `[cx, cy, w]` from the cell, or null. The same three numbers shots.csv holds. */
  focusOf(shot) {
    const parts = (shot.row.focus || "").trim().split(/[,\s/]+/).filter(Boolean);
    if (parts.length !== 3) return null;
    const nums = parts.map(Number);
    return nums.some(Number.isNaN) ? null : nums;
  }

  optionsFor(kind) {
    if (!this.data) return null;
    if (kind === "motion") {
      return [{ value: "", text: "(default)" },
        ...this.data.motions.map((m) => ({ value: m, text: m }))];
    }
    if (kind === "anchor") {
      return this.data.anchors.map((a) => ({ value: a, text: a || "(default)" }));
    }
    if (kind === "effects") {
      return this.data.effects.map((e) => ({
        value: e,
        text: e ? `${e} — ${this.costOf(e).toFixed(1)}× render` : "(none)",
      }));
    }
    return null;
  }
}

/**
 * Fit a drawn rectangle to what the renderer will actually use.
 *
 * The same two ceilings `memoacts_core.schedule.focus_window` enforces, applied
 * before the fact instead of after it: never narrower than the output frame,
 * never wider than the base 9:16 window, and the centre pulled in so the window
 * sits inside the source. `wide` reports the first of those biting, which is
 * the render-time warning arriving while it is still a choice.
 */
export function fitFocus(media, cx, cy, w) {
  const wide = w < media.focus_min_w - 1e-6;
  w = Math.min(Math.max(w, media.focus_min_w), media.focus_max_w);
  let wpx = w * media.width;
  let hpx = wpx * 16 / 9;                         // the frame is 9:16
  if (hpx > media.height) {
    hpx = media.height;
    wpx = hpx * 9 / 16;
    w = wpx / media.width;
  }
  const halfX = wpx / 2 / media.width;
  const halfY = hpx / 2 / media.height;
  return {
    cx: Math.min(Math.max(cx, halfX), 1 - halfX),
    cy: Math.min(Math.max(cy, halfY), 1 - halfY),
    w, wpx, hpx, wide,
    zoom: (media.max_zoom * 1080) / wpx,
  };
}

/**
 * The thumbnail with the focus rectangle drawn on it.
 *
 * Drag to say how tight the shot is; click to move the window without resizing
 * it, because the framing is usually right and the subject is not. It reports
 * through two callbacks and owns no state beyond the drag in progress, so the
 * view above it decides what a finished rectangle means.
 */
export class FocusPicker {
  constructor({ onCommit, onLive }) {
    this.onCommit = onCommit;
    this.onLive = onLive;
    this.media = null;
    this.focus = null;
    this.drag = null;

    this.img = el("img", { alt: "" });
    this.rect = el("div", { className: "ma-rect" });
    this.root = el("div", { className: "ma-frame" }, [this.img, this.rect]);
    this.root.addEventListener("pointerdown", (e) => this.start(e));
    this.root.addEventListener("pointermove", (e) => this.move(e));
    this.root.addEventListener("pointerup", (e) => this.end(e));
    this.root.addEventListener("pointercancel", () => { this.drag = null; this.draw(); });
    this.img.addEventListener("load", () => this.draw());
  }

  show(src, media, focus) {
    this.media = media;
    this.focus = focus;
    // Only reassign when it changes: setting .src to the same URL still clears
    // the image for a frame, and the rectangle would flicker with it.
    if (this.img.getAttribute("src") !== src) this.img.src = src;
    this.root.classList.toggle("locked", !media);
    this.draw();
  }

  draw(live) {
    const f = live || this.focus;
    const box = this.img.getBoundingClientRect();
    if (!f || !this.media || !box.width) { this.rect.style.display = "none"; return; }
    const fit = live || fitFocus(this.media, f[0], f[1], f[2]);
    this.rect.style.display = "block";
    this.rect.classList.toggle("bad", fit.wide);
    this.rect.style.left = `${(fit.cx - fit.wpx / 2 / this.media.width) * box.width}px`;
    this.rect.style.top = `${(fit.cy - fit.hpx / 2 / this.media.height) * box.height}px`;
    this.rect.style.width = `${(fit.wpx / this.media.width) * box.width}px`;
    this.rect.style.height = `${(fit.hpx / this.media.height) * box.height}px`;
  }

  at(e) {
    const box = this.img.getBoundingClientRect();
    return [(e.clientX - box.left) / box.width, (e.clientY - box.top) / box.height];
  }

  start(e) {
    if (!this.media || !this.img.src) return;
    this.root.setPointerCapture(e.pointerId);
    this.drag = { from: this.at(e), moved: false };
  }

  move(e) {
    if (!this.drag) return;
    const [x, y] = this.at(e);
    const [x0, y0] = this.drag.from;
    if (Math.abs(x - x0) > 0.02 || Math.abs(y - y0) > 0.02) this.drag.moved = true;
    if (!this.drag.moved) return;
    // The width is what is being drawn; the height follows from 9:16, because
    // that is the frame the window will be resized into.
    const fit = fitFocus(this.media, (x + x0) / 2, (y + y0) / 2, Math.abs(x - x0));
    this.drag.fit = fit;
    this.draw(fit);
    this.onLive?.(fit, true);
  }

  end(e) {
    if (!this.drag) return;
    let fit = this.drag.fit;
    if (!this.drag.moved) {
      const [x, y] = this.at(e);
      fit = fitFocus(this.media, x, y,
        this.focus ? this.focus[2] : this.media.focus_max_w * 0.6);
    }
    this.drag = null;
    if (!fit) return;
    this.focus = [fit.cx, fit.cy, fit.w];
    this.draw();
    this.onCommit?.(fit);
  }
}
