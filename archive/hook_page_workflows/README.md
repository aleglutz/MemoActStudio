# hook_page, the versions before

Ten saved graphs that piled up in `user/default/workflows/` and
`example_workflows/` while the sheet was being built on 2026-08-28, where
ComfyUI's workflow browser listed every one of them. They are here rather than
deleted, per `archive/README.md`.

`user_*` came from `user/default/workflows/hook_page.json` — the graph actually
opened in the browser. `example_*` from the copy that ships with the pack. Each
pair was taken at the same moment, so they differ only in node positions and in
whatever had been dragged around by hand.

Read in order, they are the history of one argument — how to put a pencilled
number on a sheet without it reading as a brush:

| | what it was taken before |
|---|---|
| `*_bak` | the plate was wired into Page File; before that the page directives lived in the markdown and went stale against whichever scan was loaded |
| `*_bak2` | before the act's own pencil was lifted instead of generated |
| `*_realpencil` | **the Qwen branch removed entirely** — the number lifted straight off the act by subtracting the erased plate from the scan. It is the only version here whose pencil is photographed rather than drawn, and it works; it was set aside because it can only ever carry the number the act carries, which is 10, and the sheet wanted 67 |
| `*_pregraft` | before Pencil Graft — the model's medium still reached the page |
| `*_pretitle` | before the node titles were shortened |

The live graph is `example_workflows/hook_page.json`. Nothing here is
maintained, and none of it is expected to load against a later version of the
node pack: `_bak` and `_bak2` predate `top`, `tone`, `fit` and Pencil Graft,
and ComfyUI will fill those widgets from defaults rather than from the file.

`*_realpencil` is the one worth reopening. If the number in the corner ever
stops needing to be 67, that branch is shorter, has no model in it at all, and
its pigment is the archivist's own.
