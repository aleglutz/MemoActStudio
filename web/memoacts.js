/**
 * The shot table, inside the Shot Table node.
 *
 * The pipeline is not uniformly graph-shaped. Compiling and rendering are each
 * one button; the edit in between is twenty rows of media, motion, focus,
 * labels and credits, and that is a table. A node graph is poor at tables, so
 * the table is drawn here, on the node where the step lives.
 *
 * It edits `shots.csv` through /memoacts/shots — the same file the author edits
 * by hand, so there is one artefact with two doors. The server keeps the
 * header, the unknown columns and the `#` comment rows on the way back out.
 *
 * The project is not a widget on this node: it arrives through the wire, from
 * Project via Align. So the widget walks back up the links to find it, which is
 * also what makes the node work unchanged if a graph puts something in between.
 */
import { app } from "../../scripts/app.js";

/** Column order for the editor. The server sends the same set, unordered. */
const COLUMNS = [
  { key: "media", label: "media", kind: "media", width: 200 },
  { key: "motion", label: "motion", kind: "motion", width: 110 },
  { key: "rate", label: "rate", kind: "text", width: 56 },
  { key: "focus", label: "focus (cx cy w)", kind: "text", width: 120 },
  { key: "anchor", label: "anchor", kind: "anchor", width: 84 },
  { key: "label", label: "label", kind: "text", width: 130 },
  { key: "credit", label: "credit", kind: "text", width: 140 },
  { key: "effects", label: "effects", kind: "effects", width: 120 },
  { key: "in", label: "in", kind: "text", width: 64 },
  { key: "speed", label: "speed", kind: "text", width: 60 },
  { key: "notes", label: "notes", kind: "text", width: 260 },
];

/** The size the node opens at. A starting point, not a floor.
 *
 * There is no floor to be had from outside the frontend, and it was worth the
 * hour to establish rather than leave as a maybe. A DOM widget reports
 * `{minWidth: 0}` for itself; `computeLayoutSize` cannot be overridden — not on
 * what `addDOMWidget` returns, not on the widget looked up from `node.widgets`,
 * not later from a timeout — and `node.computeSize` is reassigned back over any
 * override. Each was read back off the live node and each had reverted.
 *
 * So a relayout can still shrink the node to a sliver, and the cure is to drag
 * it wide again. The table scrolls inside whatever it is given, which is the
 * right behaviour for a table anyway. */
const MIN_WIDTH = 860;
const MIN_HEIGHT = 520;

const CSS = `
.memoacts-table { display:flex; flex-direction:column; height:100%; min-height:0;
  font-family: system-ui, sans-serif; font-size:11px; color:var(--fg-color,#ddd);
  background:var(--comfy-menu-bg,#202020); border-radius:6px; overflow:hidden; }
.memoacts-bar { display:flex; gap:6px; align-items:center; padding:6px 8px;
  border-bottom:1px solid var(--border-color,#444); flex:0 0 auto; }
.memoacts-bar .grow { flex:1 1 auto; }
.memoacts-bar button { font:inherit; padding:3px 10px; border-radius:4px; cursor:pointer;
  border:1px solid var(--border-color,#555); background:var(--comfy-input-bg,#333);
  color:inherit; }
.memoacts-bar button:hover { border-color:#8ab4f8; }
.memoacts-bar .status { opacity:.7; }
.memoacts-bar .status.bad { color:#ff9b9b; opacity:1; }
.memoacts-scroll { flex:1 1 auto; overflow:auto; min-height:0; }
.memoacts-table table { border-collapse:collapse; width:max-content; min-width:100%; }
.memoacts-table th { position:sticky; top:0; z-index:1; text-align:left;
  padding:4px 6px; font-weight:600; background:var(--comfy-menu-bg,#202020);
  border-bottom:1px solid var(--border-color,#444); white-space:nowrap; }
.memoacts-table td { padding:2px 4px; border-bottom:1px solid rgba(255,255,255,.06);
  vertical-align:top; }
.memoacts-table tr.sel td { background:rgba(138,180,248,.12); }
.memoacts-table .num { white-space:nowrap; opacity:.75; cursor:pointer; padding-right:8px; }
.memoacts-table .line { max-width:280px; opacity:.75; cursor:pointer;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.memoacts-table input, .memoacts-table select { font:inherit; width:100%;
  box-sizing:border-box; padding:2px 3px; border-radius:3px; color:inherit;
  border:1px solid transparent; background:var(--comfy-input-bg,#2b2b2b); }
.memoacts-table input:focus, .memoacts-table select:focus {
  outline:none; border-color:#8ab4f8; }
.memoacts-table .dirty input, .memoacts-table .dirty select { border-color:#e0b341; }
.memoacts-detail { flex:0 0 auto; display:flex; gap:10px; padding:8px;
  border-top:1px solid var(--border-color,#444); max-height:190px; }
.memoacts-frame { position:relative; flex:0 0 auto; align-self:flex-start;
  line-height:0; cursor:crosshair; touch-action:none; }
.memoacts-frame img { display:block; max-height:170px; max-width:220px;
  border-radius:4px; background:#111; }
.memoacts-frame .rect { position:absolute; box-sizing:border-box;
  border:1.5px solid #8ab4f8; background:rgba(138,180,248,.14);
  box-shadow:0 0 0 9999px rgba(0,0,0,.35); pointer-events:none; display:none; }
.memoacts-frame .rect.bad { border-color:#ff9b9b; background:rgba(255,155,155,.14); }
.memoacts-frame.locked { cursor:not-allowed; }
.memoacts-detail .meta { flex:1 1 auto; overflow:auto; line-height:1.45; }
.memoacts-detail .warn { color:#ffcf8b; }
.memoacts-detail .bad { color:#ff9b9b; }
.memoacts-detail .hint { opacity:.6; }
.memoacts-detail button.link { font:inherit; padding:0; margin-top:2px;
  border:none; background:none; color:#8ab4f8; cursor:pointer;
  text-decoration:underline; }
`;

/** Walk back along the wires until something knows which project this is. */
export function findProject(node) {
  const seen = new Set();
  const walk = (n, depth) => {
    if (!n || depth > 8 || seen.has(n.id)) return null;
    seen.add(n.id);
    const dir = n.widgets?.find((w) => w.name === "project_dir")?.value;
    if (dir && String(dir).trim()) return String(dir).trim();
    const pick = n.widgets?.find((w) => w.name === "project")?.value;
    if (pick && n.comfyClass === "MemoActsProject") return String(pick);
    for (const input of n.inputs ?? []) {
      const link = input.link != null ? app.graph.links[input.link] : null;
      const found = link ? walk(app.graph.getNodeById(link.origin_id), depth + 1) : null;
      if (found) return found;
    }
    return null;
  };
  return walk(node, 0);
}

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) node.append(child);
  return node;
}

class ShotTableWidget {
  constructor(node) {
    this.node = node;
    this.data = null;
    this.dirty = false;
    this.selected = null;

    this.status = el("span", { className: "status", textContent: "not loaded" });
    this.reload = el("button", { textContent: "Reload", onclick: () => this.load() });
    this.save = el("button", { textContent: "Save", onclick: () => this.persist() });
    this.head = el("thead");
    this.body = el("tbody");
    this.thumb = el("img", { alt: "" });
    this.rect = el("div", { className: "rect" });
    this.frame = el("div", { className: "memoacts-frame" }, [this.thumb, this.rect]);
    this.frame.addEventListener("pointerdown", (e) => this.pickStart(e));
    this.frame.addEventListener("pointermove", (e) => this.pickMove(e));
    this.frame.addEventListener("pointerup", (e) => this.pickEnd(e));
    this.frame.addEventListener("pointercancel", () => this.pickCancel());
    this.thumb.addEventListener("load", () => this.drawFocus());
    this.meta = el("div", { className: "meta" });

    this.root = el("div", { className: "memoacts-table" }, [
      el("div", { className: "memoacts-bar" }, [
        el("strong", { textContent: "shots.csv" }),
        this.status,
        el("span", { className: "grow" }),
        this.reload,
        this.save,
      ]),
      el("div", { className: "memoacts-scroll" }, [
        el("table", {}, [this.head, this.body]),
      ]),
      el("div", { className: "memoacts-detail" }, [this.frame, this.meta]),
    ]);
  }

  say(text, bad = false) {
    this.status.textContent = text;
    this.status.classList.toggle("bad", bad);
  }

  async load() {
    const project = findProject(this.node);
    if (!project) {
      this.say("wire a Project node in to see its shots", true);
      return;
    }
    this.project = project;
    this.say("loading…");
    try {
      const res = await fetch(`/memoacts/shots?project=${encodeURIComponent(project)}`);
      const body = await res.json();
      if (!res.ok || body.error) throw new Error(body.error || res.statusText);
      this.data = body;
      this.dirty = false;
      this.render();
      this.say(`${body.shots.length} shots · ${body.project}`);
    } catch (err) {
      this.data = null;
      this.body.replaceChildren();
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
      this.dirty = false;
      for (const tr of this.body.children) tr.classList.remove("dirty");
      // Re-read rather than trust the local copy: the file decides what a row
      // says now, and a shot whose decisions were all cleared has lost its row.
      await this.load();
      this.say(`saved ${body.saved} rows to shots.csv`);
    } catch (err) {
      this.say(String(err.message || err), true);
    }
  }

  render() {
    this.head.replaceChildren(
      el("tr", {}, [
        el("th", { textContent: "#" }),
        el("th", { textContent: "line" }),
        ...COLUMNS.map((c) => el("th", { textContent: c.label })),
      ]),
    );
    this.body.replaceChildren(...this.data.shots.map((shot) => this.row(shot)));
    this.select(this.data.shots[0]);
  }

  row(shot) {
    const tr = el("tr");
    const pick = () => this.select(shot, tr);
    tr.append(
      el("td", {
        className: "num",
        textContent: shot.cue || String(shot.id),
        title: `shot ${shot.id}`,
        onclick: pick,
      }),
      el("td", {
        className: "line",
        textContent: shot.text || "(silent)",
        title: shot.text,
        onclick: pick,
      }),
    );
    for (const col of COLUMNS) {
      const cell = el("td");
      cell.style.minWidth = `${col.width}px`;
      const input = this.field(col, shot, tr);
      input.addEventListener("focus", pick);
      cell.append(input);
      tr.append(cell);
    }
    return tr;
  }

  field(col, shot, tr) {
    const value = shot.row[col.key] ?? "";
    const options = this.optionsFor(col.kind);
    let input;
    if (options) {
      input = el("select");
      for (const opt of options) {
        input.append(
          opt.group
            ? el("optgroup", { label: opt.group }, opt.items.map(
                (i) => el("option", { value: i.value, textContent: i.text })))
            : el("option", { value: opt.value, textContent: opt.text }),
        );
      }
      // A value the folder no longer offers must stay visible rather than
      // silently becoming the first option — that would be an edit nobody made.
      if (value && ![...input.querySelectorAll("option")].some((o) => o.value === value)) {
        input.append(el("option", { value, textContent: `${value} (missing)` }));
      }
      input.value = value;
    } else {
      input = el("input", { type: "text", value });
    }
    (shot._els ||= {})[col.key] = input;
    input.onchange = () => {
      shot.row[col.key] = input.value;
      tr.classList.add("dirty");
      this.dirty = true;
      this.say("edited — not saved");
      if (col.kind === "media" || col.kind === "motion") this.select(shot, tr);
    };
    return input;
  }

  optionsFor(kind) {
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
    if (kind === "media") {
      const dirs = new Map();
      for (const m of this.data.media) {
        if (!dirs.has(m.dir)) dirs.set(m.dir, []);
        dirs.get(m.dir).push({
          value: m.name,
          // The headroom, next to the name, at the moment of choosing. The
          // resolution guard warns at render time, by which point the image has
          // already been assigned to the shot (GAPS.md).
          text: `${m.name} — ${m.max_zoom.toFixed(2)}×${m.video ? " · video" : ""}`,
        });
      }
      return [{ value: "", text: "(from the script, or cycled)" },
        ...[...dirs].map(([group, items]) => ({ group, items }))];
    }
    return null;
  }

  /** What a look costs, as a multiple of a clean render. 1 for no look. */
  costOf(name) {
    return this.data.effect_cost?.[name] ?? 1;
  }

  /** The media record for whatever this shot will actually show. */
  mediaFor(shot) {
    const name = shot.row.media || shot.resolved;
    return this.data.media.find((m) => m.name === name) || null;
  }

  /** `[cx, cy, w]` from the cell, or null. Same three numbers shots.csv holds. */
  focusOf(shot) {
    const parts = (shot.row.focus || "").trim().split(/[,\s/]+/).filter(Boolean);
    if (parts.length !== 3) return null;
    const nums = parts.map(Number);
    return nums.some(Number.isNaN) ? null : nums;
  }

  /**
   * Fit a drawn rectangle to what the renderer will actually use.
   *
   * The same two ceilings memoacts_core.schedule.focus_window enforces, applied
   * before the fact instead of after it: never narrower than the output frame,
   * never wider than the base 9:16 window, and the centre pulled in so the
   * window sits inside the source. `wide` reports the first of those biting,
   * which is the render-time warning arriving while it is still a choice.
   */
  fitFocus(media, cx, cy, w) {
    const wide = w < media.focus_min_w - 1e-6;
    w = Math.min(Math.max(w, media.focus_min_w), media.focus_max_w);
    let wpx = w * media.width;
    let hpx = wpx * 16 / 9;                       // the frame is 9:16
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

  drawFocus(live) {
    const shot = this.selected;
    const media = shot && this.mediaFor(shot);
    const f = live || (shot && this.focusOf(shot));
    const box = this.thumb.getBoundingClientRect();
    if (!f || !media || !box.width) {
      this.rect.style.display = "none";
      return;
    }
    const fit = live || this.fitFocus(media, f[0], f[1], f[2]);
    this.rect.style.display = "block";
    this.rect.classList.toggle("bad", fit.wide);
    this.rect.style.left = `${(fit.cx - fit.wpx / 2 / media.width) * box.width}px`;
    this.rect.style.top = `${(fit.cy - fit.hpx / 2 / media.height) * box.height}px`;
    this.rect.style.width = `${(fit.wpx / media.width) * box.width}px`;
    this.rect.style.height = `${(fit.hpx / media.height) * box.height}px`;
  }

  atPointer(e) {
    const box = this.thumb.getBoundingClientRect();
    return [(e.clientX - box.left) / box.width, (e.clientY - box.top) / box.height];
  }

  pickStart(e) {
    if (!this.selected || !this.mediaFor(this.selected) || !this.thumb.src) return;
    this.frame.setPointerCapture(e.pointerId);
    this.drag = { from: this.atPointer(e), moved: false };
  }

  pickMove(e) {
    if (!this.drag) return;
    const [x, y] = this.atPointer(e);
    const [x0, y0] = this.drag.from;
    if (Math.abs(x - x0) > 0.02 || Math.abs(y - y0) > 0.02) this.drag.moved = true;
    if (!this.drag.moved) return;
    const media = this.mediaFor(this.selected);
    // The width is what is being drawn; the height follows from 9:16, because
    // that is the frame the window will be resized into.
    const fit = this.fitFocus(media, (x + x0) / 2, (y + y0) / 2, Math.abs(x - x0));
    this.drag.fit = fit;
    this.drawFocus(fit);
    this.sayFocus(fit, media, true);
  }

  pickEnd(e) {
    if (!this.drag) return;
    const media = this.mediaFor(this.selected);
    let fit = this.drag.fit;
    if (!this.drag.moved) {
      // A click moves the window rather than drawing one: the framing is
      // usually right and the subject is not.
      const current = this.focusOf(this.selected);
      const [x, y] = this.atPointer(e);
      fit = this.fitFocus(media, x, y,
        current ? current[2] : media.focus_max_w * 0.6);
    }
    this.drag = null;
    if (!fit) return;
    this.setCell(this.selected, "focus",
      `${fit.cx.toFixed(3)} ${fit.cy.toFixed(3)} ${fit.w.toFixed(3)}`);
    this.drawFocus();
    this.select(this.selected, this.body.children[this.selected.id - 1]);
  }

  pickCancel() {
    this.drag = null;
    this.drawFocus();
  }

  /** Write a cell from somewhere other than its own input, and show it there. */
  setCell(shot, key, value) {
    shot.row[key] = value;
    const input = shot._els?.[key];
    if (input) input.value = value;
    this.body.children[shot.id - 1]?.classList.add("dirty");
    this.dirty = true;
    this.say("edited — not saved");
  }

  sayFocus(fit, media, live) {
    const line = this.focusLine;
    if (!line) return;
    line.className = fit.wide ? "bad" : "";
    line.textContent = fit.wide
      ? `focus ${fit.w.toFixed(3)} — as narrow as this source allows; `
        + `anything tighter is enlargement`
      : `focus ${fit.w.toFixed(3)} · ${fit.zoom.toFixed(2)}× push-in`
        + (live ? " — release to keep" : "");
  }

  select(shot, tr) {
    if (!shot) return;
    this.selected = shot;
    for (const row of this.body.children) row.classList.remove("sel");
    if (tr) tr.classList.add("sel");

    const named = shot.row.media || "";
    const shown = named || shot.resolved;
    const media = this.data.media.find((m) => m.name === shown);
    const lines = [
      el("div", {}, [el("strong", { textContent: `shot ${shot.id}` }),
        document.createTextNode(shot.cue ? `  ·  cue ${shot.cue}` : "")]),
      el("div", { textContent: shot.text || "(silent — it holds screen time without a line)" }),
      el("div", { style: "height:6px" }),
    ];
    if (!named) {
      lines.push(el("div", { className: "warn",
        textContent: `no media named; falling back to ${shot.resolved}` }));
    }
    if (media) {
      lines.push(el("div", {
        textContent: `${media.name} · ${media.width}×${media.height} · ${media.dir}`,
      }));
      const zoom = media.max_zoom;
      // Three cases, not two: exactly 1.00 fills the frame and has no room to
      // move, which is neither the enlargement warning nor an invitation.
      const exact = Math.abs(zoom - 1) < 0.005;
      lines.push(el("div", {
        className: zoom < 1 && !exact ? "bad" : zoom < 1.15 ? "warn" : "",
        textContent: exact
          ? `max_zoom 1.00× — fills the frame exactly, with nothing spare to `
            + `move into`
          : zoom < 1
            ? `max_zoom ${zoom.toFixed(2)}× — too small for the frame; it will be `
              + `enlarged ${(1 / zoom).toFixed(2)}× before any move`
            : `max_zoom ${zoom.toFixed(2)}× — headroom for a push in`,
      }));
    } else if (shown) {
      lines.push(el("div", { className: "bad", textContent: `${shown} is in none of the media folders` }));
    }
    const motion = shot.row.motion;
    const focus = this.focusOf(shot);
    this.focusLine = el("div", {});
    if (media) {
      if (focus) {
        this.sayFocus(this.fitFocus(media, focus[0], focus[1], focus[2]), media);
      } else if (media.focus_max_w > media.focus_min_w + 1e-6) {
        this.focusLine.className = "hint";
        this.focusLine.textContent =
          "drag on the thumbnail to say what the shot is about; click to move it";
      } else {
        // No room to choose: every window is the widest one, so a rectangle
        // here cannot mean anything. Saying which of the two reasons it is
        // matters — one is a source that is exactly enough, the other a source
        // the guard is already stretching.
        this.focusLine.className = "warn";
        this.focusLine.textContent = media.max_zoom < 0.995
          ? "no focus to choose — the whole frame is already being enlarged"
          : "no focus to choose — this source fills the frame and no more";
      }
    }
    lines.push(this.focusLine);
    if (focus) {
      lines.push(el("div", {}, [el("button", {
        className: "link", textContent: "clear focus",
        onclick: () => {
          this.setCell(shot, "focus", "");
          this.select(shot, this.body.children[shot.id - 1]);
        },
      })]));
    }
    const look = shot.row.effects;
    if (look) {
      const cost = this.costOf(look);
      lines.push(el("div", {
        className: cost >= 3 ? "warn" : "",
        textContent: `${look} — this shot renders ${cost.toFixed(1)}× as slowly `
          + `as a plain one`,
      }));
    }
    if (shot.row.focus && motion && !this.data.focusable.includes(motion)) {
      lines.push(el("div", { className: "warn",
        textContent: `focus is set but ${motion} traverses rather than arrives, `
          + `so it is ignored — use ${this.data.focusable.join(", ")}` }));
    }
    this.meta.replaceChildren(...lines);
    const src = shown
      ? `/memoacts/thumb?project=${encodeURIComponent(this.project)}`
        + `&file=${encodeURIComponent(shown)}`
      : "";
    // Only reassign when it changes: setting .src to the same URL still clears
    // the image for a frame, and the focus rectangle would flicker with it.
    if (this.thumb.getAttribute("src") !== src) this.thumb.src = src;
    this.frame.classList.toggle("locked", !media);
    this.drawFocus();
  }
}

app.registerExtension({
  name: "memoacts.shottable",
  async setup() {
    document.head.append(el("style", { textContent: CSS }));
  },
  async nodeCreated(node) {
    if (node.comfyClass !== "MemoActsShotTable") return;
    const widget = new ShotTableWidget(node);
    node.addDOMWidget("shots_csv", "memoacts_table", widget.root, {
      serialize: false,          // the file is the state; the graph holds none
      hideOnZoom: false,
    });
    node.setSize([Math.max(node.size[0], MIN_WIDTH),
                  Math.max(node.size[1], MIN_HEIGHT + 120)]);
    // Wait for the graph to finish loading, so walking back to the Project node
    // finds links that a freshly-deserialised workflow has not wired yet.
    setTimeout(() => widget.load(), 250);
  },
});
