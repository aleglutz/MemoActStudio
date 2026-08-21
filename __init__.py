"""comfyui-memoacts — ComfyUI node pack for the MemoActs reel workflow.

The nodes are widgets and reporting; the work is `memoacts_core.pipeline`,
which `tools/` calls in the same order with the same arguments (SPEC §3). That
is deliberate and load-bearing: the two used to be separate implementations of
the same sequence, and they drifted.

The workflow is five nodes, left to right, and each is one sentence:

    Project ─→ Align ─→ Shot Table ─→ Subtitles ─→ Render Reel
    "my material"  "my words   "I decide   "the words   "the reel
                    become      what is     become       is made"
                    timings"    seen"       captions"

                        Shot Table ─→ Preview Shot     one shot, seconds
    Effect Preset ─→ Grade ─→ Grain ─→ … ─→ Apply Effects ─┘
"""
from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .nodes_align import MemoActsAlign
from .nodes_encode import MemoActsPreviewShot, MemoActsRenderReel
from .nodes_layers import (MemoActsApplyEffects, MemoActsEffectPreset,
                           MemoActsFrameOverlay, MemoActsGrade,
                           MemoActsGrain, MemoActsShake, MemoActsSharpen,
                           MemoActsTexture)
from .nodes_project import MemoActsProject
from .nodes_shot import MemoActsSetImage, MemoActsSetMotion, MemoActsShotTable
from .nodes_subs import MemoActsSubtitles


class MemoActsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MemoActsProject,
            MemoActsAlign,
            MemoActsShotTable,
            MemoActsSubtitles,
            MemoActsRenderReel,
            MemoActsPreviewShot,
            MemoActsSetMotion,
            MemoActsSetImage,
            MemoActsEffectPreset,
            MemoActsGrade,
            MemoActsGrain,
            MemoActsTexture,
            MemoActsFrameOverlay,
            MemoActsShake,
            MemoActsSharpen,
            MemoActsApplyEffects,
        ]


async def comfy_entrypoint() -> MemoActsExtension:
    return MemoActsExtension()
