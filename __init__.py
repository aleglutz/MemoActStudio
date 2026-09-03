"""comfyui-memoacts — ComfyUI node pack for the MemoActs reel workflow.

The nodes are widgets and reporting; the work is `memoacts_core.pipeline`,
which `tools/` calls in the same order with the same arguments (SPEC §3). That
is deliberate and load-bearing: the two used to be separate implementations of
the same sequence, and they drifted.

The reel is five nodes, left to right, and each is one sentence. The voice
arrives from a workflow of its own, through the node that names a project into
existence and puts the recording inside it:

    Load Audio ─→ Pitch / Time ─→ De-esser ─→ Compressor ─→ Normalize ─┐
    "as I want it heard"                                               │
      ┌──────────── Set Narration ←─────────────────────────────────────┘
      │             "into my project"
      ↓
    Project ─→ Align ─→ Shot Table ─→ Subtitles ─→ Render Reel
    "my material"  "my words   "I decide   "the words   "the reel
                    become      what is     become       is made"
                    timings"    seen"       captions"

                        Shot Table ─→ Preview Shot     one shot, seconds
    Effect Preset ─→ Grade ─→ Grain ─→ … ─→ Apply Effects ─┘

    Load Image ─→ Paper Mask ─→ (LaMa, upscale) ─→ Type Page ─→ Save Image
    "the act"     "what on it   "the act's paper    "a document
                   is not        without the act     of our own"
                   paper"        on it"

                        Shot Table ─→ Sound Design ─→ SFX Bed ─┐
                        "this scene needs a sound"             ↓
                                                        Render Reel (sfx)
"""
from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .nodes_align import MemoActsAlign
from .nodes_audio import (MemoActsSaveSfx, MemoActsSfxBed, MemoActsSfxPrompt,
                          MemoActsSoundDesign)
from .nodes_encode import MemoActsPreviewShot, MemoActsRenderReel
from .nodes_layers import (MemoActsApplyEffects, MemoActsEffectPreset,
                           MemoActsFrameOverlay, MemoActsGrade,
                           MemoActsGrain, MemoActsShake, MemoActsSharpen,
                           MemoActsTexture)
from .nodes_page import (MemoActsPageFile, MemoActsPaperMask,
                         MemoActsPencilCrop, MemoActsPencilGraft,
                         MemoActsPencilLift, MemoActsPencilPrompt,
                         MemoActsTypePage)
from .nodes_project import MemoActsProject, MemoActsSetNarration
from .nodes_shot import MemoActsSetImage, MemoActsSetMotion, MemoActsShotTable
from .nodes_subs import MemoActsSubtitles
from .nodes_voice import (MemoActsAudioAutoTune, MemoActsAudioDeEsser,
                          MemoActsAudioLoudnessMeter, MemoActsAudioNormalize,
                          MemoActsAudioPitchTime, MemoActsAudioSpeechDenoise,
                          MemoActsAudioVocalCompressor)

# Importing this registers the /memoacts/... routes the shot-table widget calls.
# It has to happen at load time, before ComfyUI hands its aiohttp app the route
# table it collected.
from . import nodes_web  # noqa: F401,E402

#: The shot-table widget, served from web/ (SPEC §5.2 — the edit is a table,
#: and a node graph is poor at tables).
WEB_DIRECTORY = "web"


class MemoActsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MemoActsAudioPitchTime,
            MemoActsAudioDeEsser,
            MemoActsAudioVocalCompressor,
            MemoActsAudioNormalize,
            MemoActsAudioSpeechDenoise,
            MemoActsAudioAutoTune,
            MemoActsAudioLoudnessMeter,
            MemoActsSetNarration,
            MemoActsProject,
            MemoActsAlign,
            MemoActsShotTable,
            MemoActsSubtitles,
            MemoActsRenderReel,
            MemoActsPreviewShot,
            MemoActsSetMotion,
            MemoActsSetImage,
            MemoActsSoundDesign,
            MemoActsSfxPrompt,
            MemoActsSaveSfx,
            MemoActsSfxBed,
            MemoActsEffectPreset,
            MemoActsGrade,
            MemoActsGrain,
            MemoActsTexture,
            MemoActsFrameOverlay,
            MemoActsShake,
            MemoActsSharpen,
            MemoActsApplyEffects,
            MemoActsPaperMask,
            MemoActsPencilCrop,
            MemoActsPencilPrompt,
            MemoActsPencilLift,
            MemoActsPencilGraft,
            MemoActsPageFile,
            MemoActsTypePage,
        ]


async def comfy_entrypoint() -> MemoActsExtension:
    return MemoActsExtension()
