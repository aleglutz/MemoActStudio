"""comfyui-memoacts — ComfyUI node pack for the MemoActs reel workflow.

The nodes are thin wrappers; the logic lives in `memoacts_core`, which stays
importable and testable without ComfyUI (SPEC §3) and is exercised headlessly by
`tools/render_reel.py`.

Typical graph:

    Align Shots ─→ Set Motion ─→ Subtitles ─→ Render Reel
                        ↑
    Effect Preset ─→ Grade ─→ Grain ─→ … ─→ Apply Effects
                        └──────→ Shot Report
"""
from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .nodes_align import MemoActsAlignShots
from .nodes_encode import MemoActsRenderReel
from .nodes_layers import (MemoActsApplyEffects, MemoActsEffectPreset,
                           MemoActsFrameOverlay, MemoActsGrade,
                           MemoActsGrain, MemoActsShake, MemoActsSharpen,
                           MemoActsTexture)
from .nodes_shot import MemoActsSetImage, MemoActsSetMotion, MemoActsShotReport
from .nodes_subs import MemoActsSubtitles


class MemoActsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MemoActsAlignShots,
            MemoActsSetMotion,
            MemoActsSetImage,
            MemoActsShotReport,
            MemoActsSubtitles,
            MemoActsRenderReel,
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
