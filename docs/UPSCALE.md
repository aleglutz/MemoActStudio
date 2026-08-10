# Upscaling archival stills

Workflow: `docs/workflows/upscale_archival_api.json`. Five 4× ESRGAN models are
installed; this records which one and, more importantly, **when not to use any
of them**.

## The rule this sits under

Upscaling an archival photograph is restoration, and SPEC §9.7 puts restoration
in Branch B: *"governed by the ethics module; never in a published reel without
a disclosed intervention statement."* An upscaler does not enlarge a photograph,
it **invents plausible texture that no camera recorded**. In a film about how
memory of the war gets distorted, that is the case the rule was written for.

It does not conflict with the project's "never silently upscale" line — the word
there is *silently*. A deliberate, recorded processing step is not what that
forbids. The requirement is disclosure, not abstinence.

## Which model

Compared on the reel's worst source, `Wehrmacht-at-Tempelhof-Shagin-MBK.jpg`
(768×514, needing 3.72× to fill a vertical frame). High-frequency energy is a
rough proxy for how much texture each model adds — plain lanczos invents
nothing, so it is the floor:

| | added detail |
|---|---|
| lanczos (floor — nothing invented) | 1.32 |
| **4x_foolhardy_Remacri** | **1.44** |
| 4xlsdirplus_v1 | 1.85 |
| 4x-UltraSharp / 4x-UltraSharp-V10 | 2.78 |
| 4x_NMKD-Siax_200k | 2.85 |

**Use Remacri.** It sits closest to the honest floor while still recovering
buttons, belt buckles and coat edges. **UltraSharp and NMKD are disqualified for
archival material**: at 1:1 they harden edges into plastic and rework faces into
waxy invented features. They look impressive on a thumbnail and indefensible in
a museum.

The model is 4×; `ImageScaleBy` reduces to the size actually wanted, so the
network runs at its trained factor and the reduction is a clean lanczos.

## When not to upscale at all

**Most of this reel's "problem" images do not need it.** Berlin, Moscow, London,
Wehrmacht_in_Karlshorst and Karlshorst-Prepared need only 1.04–1.18× to fill the
frame. Inventing texture to gain four to eighteen percent is a bad trade — the
visible gain is small and the fabrication is real. Stack them into bands instead
(`docs/THREEBAND_TOOL.md`); in a 636 px band the same sources land at 0.42–0.68
and need no enlargement whatsoever.

**And the one image that most needs upscaling is the one that should least get
it.** The Tempelhof arrival is 768×514, so the faces of the German delegation
are about twenty pixels tall. No upscaler recovers them — it can only invent
them. Those are identifiable people in a historical record, and Remacri visibly
reconstructs their features. In a 636 px band the same frame sits at 0.84× and
needs no enlargement at all, which is both the cheaper and the honest answer.

Upscale when the source is genuinely short and nothing identifiable is being
reconstructed. Band it when the geometry can be solved instead.
