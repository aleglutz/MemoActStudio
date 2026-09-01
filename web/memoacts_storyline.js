/**
 * The storyline — "I decide what is seen", as a panel rather than a table.
 *
 * The edit used to be a `<table>` inside the Shot Table node, and on a 34-scene
 * reel it stopped working for two reasons. It had no time in it: every row was
 * the same height whether the scene ran 1.4 s or 8 s, so the rhythm of the film
 * — most of what an edit *is* — was invisible. And pictures were chosen from a
 * dropdown of filenames, which means already knowing what each filename looks
 * like. This inverts that: the pictures are on a shelf, and you put one on a
 * scene.
 *
 *     pick a scene  →  click a picture  →  it is that scene's picture
 *
 * It writes the same `shots.csv` the author edits by hand, through the same
 * route, so there is still one artefact and now only one editing surface. The
 * node keeps its real job — compiling the table and reporting it — and has no
 * widget any more.
 *
 * Two facts about sidebar tabs that shape the code, both read out of the
 * frontend rather than assumed: `render(el)` runs *every time the tab is
 * toggled on*, so the panel is a singleton that gets re-attached rather than
 * rebuilt; and nothing sizes the container for you, so the height is set from
 * the parent and kept in step with a resize listener.
 */
import { app } from "../../scripts/app.js";
import {
  el, injectCSS, fitFocus, FocusPicker, ShotsModel, projectFromGraph,
} from "./memoacts_shots.js";

/** Fields that are not the picture. The picture is the shelf's job. */
const FIELDS = [
  { key: "motion", label: "motion", kind: "motion" },
  { key: "rate", label: "rate", kind: "text", hint: "0.04–0.08 drifts" },
  { key: "anchor", label: "anchor", kind: "anchor" },
  { key: "label", label: "corner tag", kind: "text" },
  { key: "credit", label: "credit", kind: "text" },
  { key: "effects", label: "look", kind: "effects" },
  { key: "in", label: "in-point", kind: "text", hint: "footage only" },
  { key: "speed", label: "speed", kind: "text", hint: "footage only" },
  { key: "notes", label: "notes", kind: "text" },
];

const CSS = `
.ma-story { display:flex; flex-direction:column; min-height:0; gap:0;
  font-family:system-ui, sans-serif; font-size:12px;
  color:var(--fg-color,#ddd); background:var(--comfy-menu-bg,#202020); }
.ma-story * { box-sizing:border-box; }
.ma-bar { display:flex; gap:6px; align-items:center; padding:6px 8px; flex:0 0 auto;
  border-bottom:1px solid var(--border-color,#444); flex-wrap:wrap; }
.ma-bar select, .ma-bar button { font:inherit; padding:3px 8px; border-radius:4px;
  border:1px solid var(--border-color,#555); background:var(--comfy-input-bg,#333);
  color:inherit; cursor:pointer; }
.ma-bar button:hover { border-color:#8ab4f8; }
.ma-story .grow { flex:1 1 auto; }
.ma-status { opacity:.75; font-size:11px; width:100%; }
.ma-status.bad { color:#ff8a80; opacity:1; }

.ma-shelf-wrap { flex:0 0 auto; border-bottom:1px solid var(--border-color,#444); }
.ma-shelf-head { display:flex; align-items:center; gap:6px; padding:4px 8px;
  cursor:pointer; user-select:none; opacity:.85; font-size:11px; }
.ma-shelf { display:grid; grid-template-columns:repeat(auto-fill,minmax(78px,1fr));
  gap:5px; padding:0 8px 8px; max-height:34vh; overflow:auto; }
.ma-shelf-wrap.shut .ma-shelf { display:none; }
.ma-tile { cursor:pointer; border:1px solid transparent; border-radius:4px;
  overflow:hidden; background:#111; }
.ma-tile img { width:100%; aspect-ratio:1; object-fit:cover; display:block; }
.ma-tile .cap { font-size:9px; line-height:1.25; padding:2px 3px; opacity:.75;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ma-tile:hover { border-color:#8ab4f8; }
.ma-tile.small .cap { color:#ffcc80; }
.ma-tile.used { outline:1px solid #4a4a4a; }

.ma-scenes { flex:1 1 auto; min-height:0; overflow:auto; padding:6px; }
.ma-scene { display:block; width:100%; text-align:left; border:1px solid transparent;
  border-left:3px solid transparent; border-radius:4px; padding:4px 5px;
  margin-bottom:3px; background:none; color:inherit; font:inherit; cursor:pointer; }
.ma-scene:hover { background:rgba(255,255,255,.04); }
.ma-scene.sel { background:rgba(138,180,248,.13); border-color:#8ab4f8; }
.ma-scene.edited { border-left-color:#ffcc80; }
.ma-scene-head { display:flex; align-items:center; gap:6px; }
.ma-scene-head .n { font-variant-numeric:tabular-nums; opacity:.8; min-width:26px; }
.ma-bar-time { flex:1 1 auto; height:4px; border-radius:2px; background:#3a3a3a; }
.ma-bar-time i { display:block; height:100%; border-radius:2px; background:#8ab4f8; }
.ma-scene-head .secs { font-variant-numeric:tabular-nums; opacity:.6; font-size:10px; }
.ma-scene-body { display:flex; gap:6px; margin-top:3px; align-items:flex-start; }
.ma-scene-body img { width:46px; height:46px; object-fit:cover; border-radius:3px;
  flex:0 0 auto; background:#111; }
.ma-scene-body .line { font-size:11px; line-height:1.3; opacity:.9; }
.ma-flags { display:flex; gap:5px; margin-top:2px; font-size:9px; }
.ma-flag { padding:0 4px; border-radius:2px; background:#3a3a3a; opacity:.85; }
.ma-flag.auto { background:#4a4030; color:#ffcc80; }
.ma-flag.dup { background:#4a3030; color:#ff9e80; }
.ma-flag.gone { background:#5a2020; color:#ff8a80; }

.ma-detail { flex:0 0 auto; border-top:1px solid var(--border-color,#444);
  padding:6px 8px; max-height:46vh; overflow:auto; }
.ma-frame { position:relative; display:inline-block; max-width:100%; line-height:0; }
.ma-frame img { max-width:100%; max-height:190px; border-radius:3px; }
.ma-frame.locked { opacity:.45; }
.ma-rect { position:absolute; border:1px solid #8ab4f8; background:rgba(138,180,248,.14);
  pointer-events:none; display:none; }
.ma-rect.bad { border-color:#ff8a80; background:rgba(255,138,128,.14); }
.ma-fields { display:grid; grid-template-columns:auto 1fr; gap:3px 6px;
  align-items:center; margin-top:6px; }
.ma-fields label { font-size:10px; opacity:.7; }
.ma-fields input, .ma-fields select { font:inherit; font-size:11px; width:100%;
  padding:2px 4px; border-radius:3px; border:1px solid var(--border-color,#555);
  background:var(--comfy-input-bg,#333); color:inherit; }
.ma-note { font-size:10px; opacity:.7; margin-top:4px; }
.ma-note.warn { color:#ffcc80; opacity:1; }
.ma-note.bad { color:#ff8a80; opacity:1; }
.ma-stops { margin-top:6px; display:flex; flex-direction:column; gap:2px; }
.ma-stop { display:flex; align-items:center; gap:5px; font-size:10px;
  padding:2px 4px; border-radius:3px; border:1px solid transparent;
  cursor:pointer; }
.ma-stop:hover { background:rgba(255,255,255,.05); }
.ma-stop.sel { border-color:#8ab4f8; background:rgba(138,180,248,.12); }
.ma-stop.bad { color:#ffcc80; }
.ma-stop .n { opacity:.6; min-width:12px; }
.ma-stop input { width:58px; font:inherit; font-size:10px; padding:1px 3px;
  border-radius:3px; border:1px solid var(--border-color,#555);
  background:var(--comfy-input-bg,#333); color:inherit; }
.ma-bounds { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;
  padding-top:5px; border-top:1px dashed var(--border-color,#444); }
.ma-link { border:none; background:none; color:#8ab4f8; cursor:pointer;
  text-decoration:underline; font:inherit; font-size:10px; padding:0; }

.ma-overlay { position:fixed; inset:0; z-index:1300; background:rgba(0,0,0,.72);
  display:flex; padding:24px; }
.ma-overlay > .ma-story { flex:1 1 auto; border-radius:8px; overflow:hidden;
  border:1px solid var(--border-color,#555); }
.ma-story.wide { display:grid; grid-template-rows:auto auto 1fr;
  grid-template-columns:1fr 360px;
  grid-template-areas:"bar bar" "shelf shelf" "scenes detail"; }
.ma-story.wide .ma-bar { grid-area:bar; }
.ma-story.wide .ma-shelf-wrap { grid-area:shelf; }
.ma-story.wide .ma-scenes { grid-area:scenes; }
.ma-story.wide .ma-detail { grid-area:detail; border-top:none; max-height:none;
  border-left:1px solid var(--border-color,#444); }
.ma-story.wide .ma-shelf { grid-template-columns:repeat(auto-fill,minmax(96px,1fr));
  max-height:26vh; }
.ma-story.wide .ma-frame img { max-height:300px; }
`;

class StorylinePanel {
  constructor() {
    this.model = new ShotsModel();
    this.model.onStatus = (t, bad) => {
      this.status.textContent = t;
      this.status.classList.toggle("bad", !!bad);
    };
    this.model.onData = () => this.draw();
    this.selectedId = null;
    this.host = null;
    this.overlay = null;

    this.stopIndex = 0;
    this.picker = new FocusPicker({
      onCommit: (fit) => {
        const shot = this.selected();
        if (!shot) return;
        // A rectangle means the selected stop when the scene has a move, and
        // the focus when it does not. One gesture, and what it edits is
        // whatever is on screen under it.
        const stops = this.model.pathOf(shot);
        if (stops.length) {
          const i = Math.min(this.stopIndex, stops.length - 1);
          stops[i] = { ...stops[i], cx: fit.cx, cy: fit.cy, w: fit.w };
          this.setPath(shot, stops);
        } else {
          this.model.setCell(shot, "focus",
            `${fit.cx.toFixed(3)} ${fit.cy.toFixed(3)} ${fit.w.toFixed(3)}`);
        }
        this.drawScenes();
        this.drawDetail();
      },
      onLive: (fit) => this.sayFocus(fit, true),
    });

    this.picks = el("select", { onchange: () => this.load(this.picks.value) });
    this.status = el("div", { className: "ma-status", textContent: "not loaded" });
    this.expandBtn = el("button", {
      textContent: "Expand", title: "Lay the media out full screen",
      onclick: () => (this.overlay ? this.collapse() : this.expand()),
    });
    this.shelf = el("div", { className: "ma-shelf" });
    this.shelfWrap = el("div", { className: "ma-shelf-wrap" }, [
      el("div", {
        className: "ma-shelf-head",
        textContent: "▾ pictures",
        onclick: (e) => {
          this.shelfWrap.classList.toggle("shut");
          e.currentTarget.textContent =
            (this.shelfWrap.classList.contains("shut") ? "▸" : "▾") + " pictures";
        },
      }),
      this.shelf,
    ]);
    this.scenes = el("div", { className: "ma-scenes" });
    this.detail = el("div", { className: "ma-detail" });

    this.root = el("div", { className: "ma-story" }, [
      el("div", { className: "ma-bar" }, [
        this.picks,
        el("button", { textContent: "Reload", onclick: () => this.load() }),
        el("button", { textContent: "Save", onclick: () => this.model.persist() }),
        el("span", { className: "grow" }),
        this.expandBtn,
        this.status,
      ]),
      this.shelfWrap, this.scenes, this.detail,
    ]);
  }

  // ── mounting ──────────────────────────────────────────────────────────────
  // `render(el)` fires on every toggle of the tab, so this moves one root
  // around rather than building a second one. Moving a DOM node keeps its
  // listeners and its unsaved edits.

  async mount(host) {
    this.host = host;
    if (!this.overlay) host.replaceChildren(this.root);
    if (host.parentNode) host.parentNode.style.overflowY = "clip";
    this.fit();
    if (!this.onResize) {
      this.onResize = () => this.fit();
      window.addEventListener("resize", this.onResize);
    }
    if (!this.data) await this.first();
  }

  fit() {
    if (this.overlay) { this.root.style.height = ""; return; }
    const box = this.host?.parentNode;
    if (box?.offsetHeight) this.root.style.height = `${box.offsetHeight}px`;
  }

  /** The first load: fill the picker, and open whatever the graph is about. */
  async first() {
    let names = [];
    try { names = await this.model.projects(); } catch { /* server not ready */ }
    const wanted = projectFromGraph()
      || localStorage.getItem("memoacts.storyline.project");
    this.picks.replaceChildren(
      el("option", { value: "", textContent: "(project)" }),
      ...names.map((n) => el("option", { value: n, textContent: n })));
    if (wanted && names.includes(wanted)) {
      this.picks.value = wanted;
      await this.load(wanted);
    } else {
      this.model.say(names.length ? "choose a project" : "no projects yet", true);
    }
  }

  async load(project) {
    const name = project ?? this.model.project;
    if (!name) return;
    localStorage.setItem("memoacts.storyline.project", name);
    this.picks.value = name;
    await this.model.load(name);
  }

  expand() {
    this.overlay = el("div", { className: "ma-overlay" });
    this.overlay.addEventListener("pointerdown", (e) => {
      if (e.target === this.overlay) this.collapse();
    });
    this.root.classList.add("wide");
    this.root.style.height = "";
    this.overlay.append(this.root);
    document.body.append(this.overlay);
    this.expandBtn.textContent = "Close";
    this.onKey = (e) => { if (e.key === "Escape") this.collapse(); };
    window.addEventListener("keydown", this.onKey);
    this.picker.draw();
  }

  collapse() {
    if (!this.overlay) return;
    window.removeEventListener("keydown", this.onKey);
    this.overlay.remove();
    this.overlay = null;
    this.root.classList.remove("wide");
    this.expandBtn.textContent = "Expand";
    // Back into the tab if it is still mounted; otherwise the root simply
    // waits, detached, and the next render() re-attaches it with its state.
    if (this.host?.isConnected) this.host.replaceChildren(this.root);
    this.fit();
    this.picker.draw();
  }

  // ── drawing ───────────────────────────────────────────────────────────────

  get data() { return this.model.data; }

  selected() {
    return this.data?.shots.find((s) => s.id === this.selectedId) || null;
  }

  draw() {
    this.drawShelf();
    this.drawScenes();
    if (!this.selected() && this.data?.shots.length) {
      this.selectedId = this.data.shots[0].id;
    }
    this.drawDetail();
  }

  drawShelf() {
    if (!this.data) { this.shelf.replaceChildren(); return; }
    const shown = new Set(this.data.shots.map((s) => this.model.shownName(s)));
    this.shelf.replaceChildren(...this.data.media.map((m) => {
      const tile = el("div", {
        className: "ma-tile" + (m.max_zoom < 0.995 ? " small" : "")
          + (shown.has(m.name) ? " used" : ""),
        title: `${m.name}\n${m.width}×${m.height}`
          + (m.video ? " · footage" : "")
          + `\nheadroom ${m.max_zoom.toFixed(2)}×`
          + (m.max_zoom < 0.995 ? " — this one is already being enlarged" : ""),
        onclick: () => this.assign(m.name),
      }, [
        el("img", { src: this.model.thumbURL(m.name), alt: "", loading: "lazy" }),
        el("div", { className: "cap", textContent: m.name }),
      ]);
      return tile;
    }));
  }

  assign(name) {
    const shot = this.selected();
    if (!shot) { this.model.say("pick a scene first", true); return; }
    this.model.setCell(shot, "media", name);
    this.drawShelf();
    this.drawScenes();
    this.drawDetail();
  }

  drawScenes() {
    if (!this.data) { this.scenes.replaceChildren(); return; }
    const frames = this.data.shots.map((s) => s.timing?.n_frames || 0);
    const longest = Math.max(1, ...frames);

    this.scenes.replaceChildren(...this.data.shots.map((shot, i) => {
      const shown = this.model.shownName(shot);
      const prev = i > 0 ? this.model.shownName(this.data.shots[i - 1]) : null;
      const flags = [];
      if (!shot.row.media) {
        flags.push(el("span", {
          className: "ma-flag auto", textContent: "auto",
          title: "nobody chose this picture — it is the cycled default",
        }));
      }
      if (shown && shown === prev) {
        flags.push(el("span", {
          className: "ma-flag dup", textContent: "same as previous",
          title: "two scenes in a row on one picture: the cut will not read as a cut",
        }));
      }
      if (!shot.exists) {
        flags.push(el("span", { className: "ma-flag gone", textContent: "missing" }));
      }

      const head = [
        el("span", { className: "n", textContent: shot.label_in_script || `S${String(shot.id).padStart(2, "0")}` }),
      ];
      if (shot.timing) {
        head.push(
          el("span", { className: "ma-bar-time" }, [
            el("i", { style: `width:${Math.max(2, 100 * (shot.timing.n_frames || 0) / longest)}%` }),
          ]),
          el("span", {
            className: "secs",
            textContent: `${(shot.timing.t_end - shot.timing.t_start).toFixed(1)}s`,
          }),
        );
      } else {
        head.push(el("span", { className: "grow" }));
      }

      const card = el("button", {
        className: "ma-scene"
          + (shot.id === this.selectedId ? " sel" : "")
          + (this.model.dirty.has(shot.id) ? " edited" : ""),
        onclick: () => {
          this.selectedId = shot.id;
          this.stopIndex = 0;
          this.drawScenes();
          this.drawDetail();
        },
      }, [
        el("div", { className: "ma-scene-head" }, head),
        el("div", { className: "ma-scene-body" }, [
          el("img", { src: this.model.thumbURL(shown), alt: "", loading: "lazy" }),
          el("div", { className: "line", textContent: shot.text || "(silent — it holds screen time without a line)" }),
        ]),
        ...(flags.length ? [el("div", { className: "ma-flags" }, flags)] : []),
      ]);
      return card;
    }));
  }

  drawDetail() {
    const shot = this.selected();
    if (!shot) { this.detail.replaceChildren(); return; }
    const media = this.model.mediaFor(shot);
    const stops = this.model.pathOf(shot);
    // The rectangle on screen is the selected stop when there is a move, so
    // dragging always edits the thing being looked at.
    const shown = stops.length
      ? (() => { const k = stops[Math.min(this.stopIndex, stops.length - 1)];
                 return [k.cx, k.cy, k.w]; })()
      : this.model.focusOf(shot);
    const focus = shown;
    this.picker.show(this.model.thumbURL(this.model.shownName(shot)), media, shown);

    const rows = [];
    for (const f of FIELDS) {
      const options = this.model.optionsFor(f.kind);
      let input;
      if (options) {
        input = el("select");
        for (const o of options) {
          input.append(el("option", { value: o.value, textContent: o.text }));
        }
        // A value the folder no longer offers stays visible rather than
        // silently becoming the first option — that would be an edit nobody made.
        const v = shot.row[f.key] ?? "";
        if (v && ![...input.options].some((o) => o.value === v)) {
          input.append(el("option", { value: v, textContent: `${v} (missing)` }));
        }
        input.value = v;
      } else {
        input = el("input", { type: "text", value: shot.row[f.key] ?? "",
                              placeholder: f.hint || "" });
      }
      input.onchange = () => {
        this.model.setCell(shot, f.key, input.value);
        this.drawScenes();
        if (f.key === "motion" || f.key === "effects") this.drawDetail();
      };
      rows.push(el("label", { textContent: f.label }), input);
    }

    this.focusLine = el("div", { className: "ma-note" });
    const notes = [this.focusLine];
    if (media) {
      if (focus) {
        this.sayFocus(fitFocus(media, focus[0], focus[1], focus[2]));
      } else if (media.focus_max_w > media.focus_min_w + 1e-6) {
        this.focusLine.textContent =
          "drag on the picture to say what the shot is about; click to move it";
      } else {
        this.focusLine.className = "ma-note warn";
        this.focusLine.textContent = media.max_zoom < 0.995
          ? "no focus to choose — the whole frame is already being enlarged"
          : "no focus to choose — this source fills the frame and no more";
      }
      if (focus) {
        notes.push(el("button", {
          className: "ma-link", textContent: "clear focus",
          onclick: () => { this.model.setCell(shot, "focus", ""); this.drawDetail(); },
        }));
      }
    }
    if (shot.row.media) {
      notes.push(el("button", {
        className: "ma-link",
        textContent: `unpick ${shot.row.media} (back to the cycled default)`,
        onclick: () => {
          this.model.setCell(shot, "media", "");
          this.drawShelf(); this.drawScenes(); this.drawDetail();
        },
      }));
    }
    const look = shot.row.effects;
    if (look) {
      const cost = this.model.costOf(look);
      notes.push(el("div", {
        className: cost >= 3 ? "ma-note warn" : "ma-note",
        textContent: `${look} — this scene renders ${cost.toFixed(1)}× as slowly as a plain one`,
      }));
    }
    if (shot.row.focus && shot.row.motion
        && !this.data.focusable.includes(shot.row.motion)) {
      notes.push(el("div", { className: "ma-note warn",
        textContent: `focus is set but ${shot.row.motion} traverses rather than `
          + `arrives, so it is ignored — use ${this.data.focusable.join(", ")}` }));
    }
    if (!shot.timing && this.data.timing_note) {
      notes.push(el("div", { className: "ma-note", textContent: this.data.timing_note }));
    }

    this.detail.replaceChildren(
      el("div", { className: "ma-note", textContent: shot.text || "(silent)" }),
      this.picker.root,
      this.stops(shot),
      this.boundaries(shot),
      el("div", { className: "ma-fields" }, rows),
      ...notes);
    // After attaching, not before: the rectangle is positioned from the
    // image's box, and a detached image has none. Redrawing a scene whose
    // thumbnail is already cached fires no `load` event to do it later.
    this.picker.draw();
  }

  /**
   * The stops of a move, when a scene wants more than one.
   *
   * A focus is one destination, which is one gesture. A path is several, which
   * is a shot that *reads* something. The rectangle on the picture is the
   * scale, where it sits is the stop, and the times between stops are the
   * speed — two stops sharing a time hold still between them.
   *
   * The renderer crops inside the picture and cannot leave it, so a stop too
   * near an edge is approached rather than centred. That is said here, per
   * stop, because it is the one way a path quietly does something other than
   * what it says. A corner genuinely in the middle of the frame needs a surface
   * behind the paper, which is a composite.
   */
  stops(shot) {
    const media = this.model.mediaFor(shot);
    const list = this.model.pathOf(shot);
    const box = el("div", { className: "ma-stops" });

    if (!list.length) {
      box.append(el("button", {
        className: "ma-link",
        textContent: media ? "make a move with stops" : "",
        onclick: () => {
          const f = this.model.focusOf(shot);
          const w = f ? f[2] : Math.min(0.5, media.focus_max_w);
          const start = f ? [f[0], f[1]] : [0.5, 0.35];
          this.setPath(shot, [
            { t: 0, cx: start[0], cy: start[1], w },
            { t: 1, cx: 0.5, cy: 0.65, w },
          ]);
          this.stopIndex = 0;
          this.drawDetail();
        },
      }));
      return box;
    }

    box.append(el("div", { className: "ma-note",
      textContent: "click a stop, then drag on the picture to place it" }));
    list.forEach((k, i) => {
      const unreachable = media && this.unreachable(media, k);
      const time = el("input", {
        type: "number", step: "0.01", min: "0", max: "1", value: String(k.t),
        onchange: () => {
          const next = this.model.pathOf(shot);
          next[i].t = Math.min(Math.max(Number(time.value) || 0, 0), 1);
          this.setPath(shot, next);
          this.drawDetail();
        },
      });
      box.append(el("div", {
        className: "ma-stop" + (i === this.stopIndex ? " sel" : "")
          + (unreachable ? " bad" : ""),
        onclick: (e) => {
          if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
          this.stopIndex = i;
          this.drawDetail();
        },
      }, [
        el("span", { className: "n", textContent: `${i + 1}` }),
        time,
        el("span", { className: "grow",
          textContent: `${k.cx.toFixed(3)}, ${k.cy.toFixed(3)} · ${k.w.toFixed(3)} wide`
            + (unreachable ? " — too near the edge" : "") }),
        el("button", {
          className: "ma-link", textContent: "+",
          title: "another stop just after this one, in the same place — a hold",
          onclick: () => {
            const next = this.model.pathOf(shot);
            next.splice(i + 1, 0, { ...k, t: Math.min(1, k.t + 0.1) });
            this.setPath(shot, next);
            this.stopIndex = i + 1;
            this.drawDetail();
          },
        }),
        el("button", {
          className: "ma-link", textContent: "×",
          onclick: () => {
            const next = this.model.pathOf(shot);
            next.splice(i, 1);
            // Below two stops it is not a path any more; the cell empties and
            // the scene goes back to its preset rather than to a broken value.
            this.setPath(shot, next.length >= 2 ? next : []);
            this.stopIndex = 0;
            this.drawDetail();
          },
        }),
      ]));
    });
    box.append(el("button", {
      className: "ma-link", textContent: "clear the move",
      onclick: () => { this.setPath(shot, []); this.drawDetail(); },
    }));
    return box;
  }

  /** Whether a crop this wide can actually centre on this point. */
  unreachable(media, k) {
    const w = Math.min(Math.max(k.w, media.focus_min_w), media.focus_max_w);
    const halfX = w / 2;
    const halfY = (w * media.width * 16 / 9) / 2 / media.height;
    return k.cx < halfX - 1e-6 || k.cx > 1 - halfX + 1e-6
        || k.cy < halfY - 1e-6 || k.cy > 1 - halfY + 1e-6;
  }

  setPath(shot, stops) {
    this.model.setCell(shot, "path",
      stops.length >= 2 ? this.model.writePath(stops) : "");
    this.drawScenes();
  }

  /**
   * Where this scene begins and ends — the one control here that edits the
   * script rather than the shot list.
   *
   * A scene is a unit of what is said, so two lines held on one picture with
   * one continuous move are one scene, not two that agree. Merging them in
   * `script.md` is what makes that true for the renderer too: two shots on one
   * image get two motion schedules, and the default preset cycles by shot
   * number, so they do not merely restart — they travel in different
   * directions.
   */
  boundaries(shot) {
    const bar = el("div", { className: "ma-bounds" });
    if (shot.id > 1) {
      bar.append(el("button", {
        className: "ma-link", textContent: `⇡ merge into S${String(shot.id - 1).padStart(2, "0")}`,
        title: "One scene, one picture, one move. Alignment runs again.",
        onclick: () => this.boundary("merge", shot.id, 1,
          `Merge scene ${shot.id} into ${shot.id - 1}?\n\n`
          + `They become one scene on one picture. script.md is rewritten and `
          + `alignment will run again — the words do not change, but which `
          + `shot they belong to does.`),
      }));
    }
    const parts = shot.sentences || [];
    for (let i = 1; i < parts.length; i++) {
      bar.append(el("button", {
        className: "ma-link", textContent: `✂ split before “${parts[i].slice(0, 24)}…”`,
        title: "The new scene starts on the same picture; give it its own framing.",
        onclick: () => this.boundary("split", shot.id, i,
          `Split scene ${shot.id} before “${parts[i]}”?\n\n`
          + `Both halves start on the same picture. script.md is rewritten and `
          + `alignment will run again.`),
      }));
    }
    if (!bar.children.length) {
      bar.append(el("span", { className: "ma-note",
        textContent: "one sentence, and the first scene — no boundary to move" }));
    }
    return bar;
  }

  async boundary(action, id, at, question) {
    if (this.model.dirty.size) {
      this.model.say("save your edits first — this rewrites shots.csv", true);
      return;
    }
    const ok = await (app.extensionManager?.dialog?.confirm?.({
      title: "Move a scene boundary", message: question,
    }) ?? Promise.resolve(window.confirm(question)));
    if (!ok) return;
    this.model.say("rewriting the script…");
    try {
      const res = await fetch(
        `/memoacts/scene?project=${encodeURIComponent(this.model.project)}`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, id, at }) });
      const body = await ShotsModel.body(res);
      if (!res.ok || body.error) throw new Error(body.error || res.statusText);
      this.selectedId = action === "merge" ? id - 1 : id;
      await this.model.load();
      for (const w of body.warnings || []) console.warn(`[MemoActs] ${w}`);
      this.model.say(body.note, false);
    } catch (err) {
      this.model.say(String(err.message || err), true);
    }
  }

  sayFocus(fit, live) {
    const line = this.focusLine;
    if (!line || !fit || fit.w === undefined) return;
    line.className = "ma-note" + (fit.wide ? " bad" : "");
    line.textContent = fit.wide
      ? `focus ${fit.w.toFixed(3)} — as narrow as this source allows; anything `
        + `tighter is enlargement`
      : `focus ${fit.w.toFixed(3)} · ${fit.zoom.toFixed(2)}× push-in`
        + (live ? " — release to keep" : "");
  }
}

let panel = null;

app.registerExtension({
  name: "memoacts.storyline",
  async setup() {
    injectCSS("memoacts-storyline-css", CSS);
    const tab = {
      id: "memoacts-storyline",
      icon: "pi pi-images",
      title: "Storyline",
      tooltip: "MemoActs: what each scene is seen over",
      type: "custom",
      render: (host) => {
        panel ??= new StorylinePanel();
        panel.mount(host);
      },
    };
    // Both shapes: `extensionManager.registerSidebarTab` still works and is
    // what every pack on disk calls, but it is marked deprecated in favour of
    // the `sidebarTab` store. Writing both costs nothing and survives the
    // frontend moving in either direction.
    const mgr = app.extensionManager;
    if (mgr?.sidebarTab?.registerSidebarTab) {
      mgr.sidebarTab.registerSidebarTab(tab);
    } else {
      mgr?.registerSidebarTab?.(tab);
    }
  },
});
