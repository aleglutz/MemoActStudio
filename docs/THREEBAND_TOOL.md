# Stacked 9:16 frames — tool and verification report

Answers `HANDOFF_comfy_threeband.md`. Built and run on the local ComfyUI
2026-08-10; every claim below is from an executed graph, not from reading docs.

## Install

1. `ComfyUI-KJNodes` — already present.
2. `ComfyUI-Olm-DragCrop` — clone into `ComfyUI/custom_nodes/`, restart. Needs
   only torch, numpy and Pillow, which ComfyUI already ships.
   **Read the licence before you rely on it — see the warning at the end.**

## Use

Load `docs/workflows/threeband_9x16_api.json` (three bands) or
`twoband_9x16_api.json` (two). Each band is a chain of three nodes:

    Load Image → Olm DragCrop → Image Scale ─┐
                                             ├→ Image Concat Multi → Save Image
    Empty Image (1080×6, black) ─────────────┘

- **Move the frame** by dragging it on the DragCrop node's preview; the
  Left/Top/Width/Height fields follow, and vice versa.
- **The seam** is the Empty Image node: 6 px tall, `color 0`. Change its height
  to change every seam at once.
- **Band heights** are fixed by the geometry and set on the Image Scale nodes:
  636 for three bands, 957 for two. `636·3 + 6·2 = 1920`; `957·2 + 6 = 1920`.
- **Swap an image** by changing its Load Image node, then re-drag that band's
  frame. See the trap below first.

## Packaging as one node

Select the seven (or five) nodes → right-click → **Convert to Group Node**, name
it `MemoActs 3-Band 9:16`. Newer builds call this **Subgraph**. This is a UI
action and cannot be scripted, so it is left for whoever runs the workshop; the
graph is otherwise ready.

---

## Verification report — the five points of §4

**1. `match_image_size` — the concern does not apply here.** The task expected
`TRUE` to stretch the 1080×6 seam to 1080×636 and wreck the frame. It does not:
`TRUE` and `FALSE` produced **byte-identical** output. The flag matches the
*width*, which every input already shares at 1080. Left at `FALSE` in both
workflows anyway, since that is the safe value if a band ever arrives at a
different width — but a student cannot break the frame with this switch.

**2. Crop axis on differently-shaped sources — both work.** The S14 set uses
vertical cropping on all three bands, the S01/S02 set horizontal on both, and
each came out at the right geometry. DragCrop takes an absolute rectangle rather
than an aspect-locked frame, so orientation is not a special case for it.

**⚠ The real trap is elsewhere, and it is silent.** DragCrop compares the image
size against its `last_width`/`last_height` fields and, on any mismatch, **resets
the crop to the whole image** — no error, just a wrong frame. It fires whenever
you point a Load Image node at a differently-sized file. Re-drag the frame after
swapping an image, and if you drive the graph over the API set `last_width` and
`last_height` to the true source size.

**3. Batch / video — structurally fine.** The crop is `image[:, top:bottom,
left:right, :]`, which spans the batch dimension, so one rectangle applies to
every frame of a clip loaded through VHS_LoadVideo. Verified by reading the
implementation, **not** by running a clip through it.

**4. Seams on video — still open.** `EmptyImage` emits a fixed `batch_size`
while footage arrives as N frames, and the concat needs them to agree. Not
exercised; `batch_size` driven from the clip's frame count is the obvious first
attempt.

**5. Against the ffmpeg reference — geometry exact, content one row off.**
Compared with `composites/S14_three-band.png`:

| | |
|---|---|
| Canvas, seams, band heights | **identical** — seams at rows 636 and 1278, 6 px, bands 636/636/636 |
| Mean pixel difference | 3.67 (of 255) |
| After shifting our frame down 1 row | **2.10** |

The residual after that shift is interpolation — a different resampler, which
§4.5 accepts. The one row is the `c`-to-pixel rounding, not a structural error,
and it is 1 row in 636. It also stops mattering the moment an operator sets the
crop by eye, which is the point of the tool.

**Two-band geometry: the workflow is right and the reference is wrong.**
`twoband_9x16_api.json` produces 957 + 6 + 957 as the task specifies.
`composites/S01-02_two-band.png` is 956 + 6 + 956 **with a 2 px black bar at the
bottom** — row 1917 still carries image, rows 1918–1919 are pure black. That is
a rounding slip in `stitch.sh`. Do not treat that file as the reference for the
two-band geometry.

---

## ⚠ Licence

`ComfyUI-Olm-DragCrop` is **source-available, not open source**. The author:
*"not open-source under a standard open-source license, and not freeware"*, and
*"redistribution … is strictly prohibited without explicit written permission"*.

Using it is unrestricted and the frames you make are yours. But **shipping it
inside `comfyui-memoacts`, or inside a cloned image for the workshop machines,
is redistribution and is not permitted as things stand.** Recorded in
`SURVEY.md §3`; `HARDENING.md` blocks machine imaging on the decision. The
cheapest resolution is to ask the author, who explicitly invites gray-area
questions.
