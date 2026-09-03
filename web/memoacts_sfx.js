/**
 * Two buttons on the Sound Design node, and nothing else.
 *
 * The sound design is a table, but a much smaller one than the shot table — a
 * handful of rows, each mostly one sentence of English — so it lives in a plain
 * multiline widget rather than in a grid. What a text box cannot do on its own
 * is meet the file halfway: the node reads `sfx.csv` when the box is empty and
 * writes it when it is not, which leaves no way to pull an edit made outside
 * ComfyUI back into the box, and no way to empty the box without also deciding
 * what that means.
 *
 * Hence: "Load sfx.csv" fills the box from the file, and "Clear" empties it,
 * which hands authority back to the file. Both are one fetch and one
 * assignment; the format, the merging and every rule about what wins live on
 * the server, in `memoacts_core.sfx`, where the CLI can reach them too.
 */
import { app } from "../../scripts/app.js";
import { el, findProject } from "./memoacts_shots.js";

const CSS = `
.memoacts-sfx-bar { display:flex; gap:6px; align-items:center;
  padding:2px 4px; font:11px/1.6 var(--font-family, system-ui); }
.memoacts-sfx-bar button { font:inherit; padding:2px 8px; cursor:pointer;
  background:#333; color:#ddd; border:1px solid #555; border-radius:3px; }
.memoacts-sfx-bar button:hover { background:#3d3d3d; }
.memoacts-sfx-bar .status { color:#888; margin-left:auto; }
`;

class SfxBar {
  constructor(node) {
    this.node = node;
    this.status = el("span", { className: "status", textContent: "" });
    this.root = el("div", { className: "memoacts-sfx-bar" }, [
      el("button", { textContent: "Load sfx.csv", onclick: () => this.load() }),
      el("button", { textContent: "Clear", onclick: () => this.clear() }),
      this.status,
    ]);
  }

  /** The `cues` widget of this node, whatever else has been added to it. */
  get widget() {
    return this.node.widgets?.find((w) => w.name === "cues");
  }

  async load() {
    const project = findProject(this.node);
    if (!project) {
      this.status.textContent = "no project wired in yet";
      return;
    }
    try {
      const res = await fetch(
        `/memoacts/sfx?project=${encodeURIComponent(project)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || res.statusText);
      const widget = this.widget;
      if (widget) widget.value = body.cues;
      // A template is not an edit: saying so is the difference between "your
      // file is empty" and "the tool did nothing".
      this.status.textContent = body.rows
        ? `${body.rows} row(s) from sfx.csv`
        : "no sfx.csv yet — this is a starter table";
      this.node.setDirtyCanvas(true, true);
    } catch (err) {
      this.status.textContent = String(err.message || err);
    }
  }

  clear() {
    const widget = this.widget;
    if (widget) widget.value = "";
    this.status.textContent = "cleared — the node will read sfx.csv";
    this.node.setDirtyCanvas(true, true);
  }
}

app.registerExtension({
  name: "memoacts.sounddesign",
  async setup() {
    document.head.append(el("style", { textContent: CSS }));
  },
  async nodeCreated(node) {
    if (node.comfyClass !== "MemoActsSoundDesign") return;
    const bar = new SfxBar(node);
    node.addDOMWidget("sfx_bar", "memoacts_sfx_bar", bar.root, {
      serialize: false,        // buttons, not state
      hideOnZoom: false,
      getMinHeight: () => 24,
    });
  },
});
