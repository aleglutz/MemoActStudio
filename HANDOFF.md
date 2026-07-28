# HANDOFF — session state as of 2026-07-28 (updated end of day)

Read CLAUDE.md and SPEC.md first as always. This file is the delta: exactly
where the last session stopped and what the next session does first. Delete or
update this file once its contents are stale.

## Where we are

P1 (Cloud PoC) is **done locally, end to end** and committed at `9310ccd`:

- `tools/generate_shots.py` → shots.json (frozen schema 1.0, `docs/SHOTS_SCHEMA.md`)
  + crop CSVs + per-shot report, stable-ts alignment, digit normalisation,
  resolution guard.
- `tools/run_p1_local.py` builds/submits the verified stock-node chain
  (LoadImage → StringSplitDataList/CastToInt ×4 → ImageCrop+ (list) →
  ImageResize+ 1080×1920 → DrawText+ in **list domain** → ImageListToBatch+ →
  VHS_VideoCombine, ≤60-frame chunks).
- `tools/assemble_reel.py` concats segments + muxes narration outside the graph
  (no `-shortest` — it drops the last frame).
- Proven on `projects/demo_en`: 415 frames / 13.833 s vs narration 13.831 s.
- All compromises recorded: `GAPS.md` #1 (DrawText+ is Latin-only → RU/HY via
  PNG strips), #2 (~11.5 GiB RAM per 240-frame shot → chunking), #3 (DrawText+
  collapses batches → list domain, ~2.6× render cost).
- Facilitator hand-build recipe for the Cloud UI: `docs/PARTICIPANT_GRAPH_RECIPE.md`
  (companion: `docs/example_shot_chunk_api.json`, the exact exported graph).

Added 2026-07-28 (Cloud prep, done without Cloud access):

- **Cloud node-availability pre-flight passed** — all 8 node classes of the
  frozen chain are in the Cloud per-pack *subsets*, checked node by node
  (`SURVEY.md §2.1`). No substitution needed; the fallbacks in P1_GRAPH.md stay
  live only for execution semantics, not availability.
- `run_p1_local.py --export-all <dir>` writes every chunk graph + a
  `manifest.json` (images, per-chunk text, frame counts) **with no server
  running** — so the Cloud run needs no local ComfyUI. Verified on demo_en:
  9 chunks, 415 frames (matches the local render), and `shot_01_c0.json` is
  byte-identical to the frozen `docs/example_shot_chunk_api.json`.

## Next task (the only open P1 item)

**Cloud validation run + credit measurement** (P1_GRAPH.md verification steps 4–5):

1. Submit ONE `demo_en` shot-chunk on Comfy Cloud — confirms the list-map
   mechanism transfers (availability is already confirmed, `SURVEY.md §2.1`).
   Use `shot_01_c1` (36 frames): cheapest chunk that still exercises
   list-map + crop + resize + text + encode.
2. Then the full 9-segment demo_en set, once. Record GPU-seconds from the
   dashboard → budget ×cohort vs Sachkosten (SPEC §6.1.4).
3. Then the Sidur 18-shot facilitator run (needs real Sidur narration for the
   RU alignment validation — no RU TTS voice on this machine).

First moves in the fresh session, so nothing is re-derived:

- Graphs are already built and byte-verified — do **not** rebuild them.
  `projects/demo_en/cloud_graphs/` (gitignored): 9 chunk graphs +
  `manifest.json` listing the 4 images to upload and per-chunk text/frames.
- Upload the 4 images so `LoadImage` resolves them by the exact filenames in
  the manifest (`01_big.png`, `02_wide.png`, `03_small.png`, `04_tall.png`);
  the graphs reference bare filenames.
- Submit `shot_01_c1.json` alone (36 frames). Check: 36 frames out, not 1
  (a 1-frame result = the GAPS #3 batch-collapse, i.e. Cloud runs DrawText+
  outside list domain) and motion is present (a static segment = list-map
  broadcast did not transfer → P1_GRAPH fallback 1, coarse-step motion).
- Record GPU-seconds and peak RAM for that chunk before submitting the rest.

**Blocker RESOLVED 2026-07-28:** Comfy Cloud MCP
(`https://cloud.comfy.org/mcp`, HTTP) is authenticated —
`claude mcp get comfy-cloud` reports **✔ Connected**. Scope is *local*, private
to the MemoActStudio project (the worktree inherits it); it is a CLI-added
server, so it appears in Claude Code's `/mcp` panel, **not** in claude.ai
connector settings — that is where it "goes missing".

The session that authenticated it still had no `mcp__comfy-cloud__*` tools: the
tool registry is built at startup. **Start a fresh session to get the tools.**
If `mcp__comfy-cloud__*` still does not appear, fall back to the Cloud UI per
`docs/PARTICIPANT_GRAPH_RECIPE.md` — every input for that is already exported
(`projects/demo_en/cloud_graphs/`, see `--export-all` above).

## Local environment notes

- The local ComfyUI server is **down** (background process exited, code 58).
  Restart before any local runs, from
  `C:\Users\Aleg\beehAIve\ComfyUI-Easy-Install\ComfyUI-Easy-Install`:
  `.\python_embeded\python.exe -I ComfyUI\main.py --windows-standalone-build`
  → serves on 127.0.0.1:8188; check with GET /system_stats.
- Hand-added locally (not in a lockfile anywhere): `ComfyUI_essentials` cloned
  into custom_nodes (heavy requirements deliberately NOT installed);
  `stable-ts` + `num2words` in the **embedded** python.

## Deferred validations (documented, not tasks)

- RU alignment quality on real Sidur narration (ALIGNERS.md bake-off protocol).
- Armenian rendering via the PNG-strip path (GAPS.md #1).
- HARDENING.md holds all offline/portability items for September (P3).
