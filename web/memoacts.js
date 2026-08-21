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
.memoacts-detail img { max-height:170px; max-width:220px; border-radius:4px;
  background:#111; object-fit:contain; }
.memoacts-detail .meta { flex:1 1 auto; overflow:auto; line-height:1.45; }
.memoacts-detail .warn { color:#ffcf8b; }
.memoacts-detail .bad { color:#ff9b9b; }
`;

/** Walk back along the wires until something knows which project this is. */
function findProject(node) {
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
      el("div", { className: "memoacts-detail" }, [this.thumb, this.meta]),
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
      return this.data.effects.map((e) => ({ value: e, text: e || "(none)" }));
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
      lines.push(el("div", {
        className: zoom < 1 ? "bad" : zoom < 1.15 ? "warn" : "",
        textContent: zoom < 1
          ? `max_zoom ${zoom.toFixed(2)}× — too small for the frame; it will be `
            + `enlarged ${(1 / zoom).toFixed(2)}× before any move`
          : `max_zoom ${zoom.toFixed(2)}× — headroom for a push in`,
      }));
    } else if (shown) {
      lines.push(el("div", { className: "bad", textContent: `${shown} is in none of the media folders` }));
    }
    const motion = shot.row.motion;
    if (shot.row.focus && motion && !this.data.focusable.includes(motion)) {
      lines.push(el("div", { className: "warn",
        textContent: `focus is set but ${motion} traverses rather than arrives, `
          + `so it is ignored — use ${this.data.focusable.join(", ")}` }));
    }
    this.meta.replaceChildren(...lines);
    this.thumb.src = shown
      ? `/memoacts/thumb?project=${encodeURIComponent(this.project)}`
        + `&file=${encodeURIComponent(shown)}`
      : "";
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
    node.size = [Math.max(node.size[0], 900), Math.max(node.size[1], 620)];
    // Wait for the graph to finish loading, so walking back to the Project node
    // finds links that a freshly-deserialised workflow has not wired yet.
    setTimeout(() => widget.load(), 250);
  },
});
