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

**Blocker (still open, and it needs a human):** Comfy Cloud MCP
(`https://cloud.comfy.org/mcp`, HTTP transport) is in the local config but
**not authenticated**. OAuth cannot be completed from a non-interactive
session — it must be done from an interactive `claude` terminal: `/mcp` → pick
`comfy-cloud` → browser OAuth; a session restart may be needed before the
`mcp__comfy-cloud__*` tools appear. Fallback if MCP stays flaky: build the
graph by hand in the Cloud UI per `docs/PARTICIPANT_GRAPH_RECIPE.md` (all
inputs for that are already exported — see `--export-all` above).

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
