"""Project node — "this is my material", and the first thing that can go wrong.

Every later step needs a folder that holds a script, a recording and some
images. Naming that folder is trivial; *finding out whether the tool can see
what you put in it* is not, and getting it wrong silently is how a student
loses a session. So this node reads the folder and reports it: which recording
it found and how long, how many images, how many shots the script has, which
shot got which media, and every warning the shot list raised.

Nothing here is slow. `read_project` touches the disk and no model.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.pipeline import ProjectError, read_project
from .memoacts_core.project import MEDIA_DIRS
from .nodes_types import Project

#: Where projects live: `projects/` beside this file. A student's own project
#: is a folder here, which is also how `tools/` and every document refer to it.
PROJECTS_DIR = Path(__file__).resolve().parent / "projects"


def _projects() -> list[str]:
    """Folder names under `projects/`, for the picker.

    Read when ComfyUI builds the node list, so a project created afterwards
    appears once the node definitions are refreshed (R in the browser). The
    `project_dir` override below exists for the moment before that.
    """
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


class MemoActsProject(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsProject",
            display_name="MemoActs — Project",
            category="memoacts",
            description=(
                "Names the project folder and reports what it found there: the "
                "recording and its length, the images, the shots the script "
                "holds, and which media each shot ended up with. Run it first — "
                "everything it warns about is cheaper to fix here than after a "
                "render."
            ),
            is_output_node=True,
            inputs=[
                io.Combo.Input(
                    "project", options=_projects() or [""],
                    tooltip="A folder under projects/. Each holds script.md, "
                            "shots.csv and sources/.",
                ),
                io.String.Input(
                    "project_dir", default="", optional=True,
                    tooltip="A path to a project anywhere else, which wins over "
                            "the picker. Use it for a folder the picker has not "
                            "seen yet.",
                ),
            ],
            outputs=[Project.Output("PROJECT")],
        )

    @classmethod
    def fingerprint_inputs(cls, project, project_dir=""):
        """Re-read whenever the folder's own files change.

        The script, the shot list and the images are all editable outside
        ComfyUI — that is the point of them being files — so caching on the
        widgets alone would keep showing a student the state before their edit.
        """
        folder = _resolve(project, project_dir)
        stamps = []
        for p in [folder / "script.md", folder / "shots.csv",
                  folder / "sources", folder / MEDIA_DIRS[0]]:
            try:
                stamps.append(p.stat().st_mtime_ns)
            except OSError:
                stamps.append(0)
        return f"{folder}|{stamps}"

    @classmethod
    def execute(cls, project, project_dir=""):
        folder = _resolve(project, project_dir)
        if not folder.is_dir():
            raise ValueError(f"no such project folder: {folder}")
        try:
            read = read_project(folder)
        except ProjectError as exc:
            # The three things that make a project unusable rather than merely
            # incomplete. Said plainly, with the path, because the fix is
            # always "put the file where it says".
            raise ValueError(str(exc)) from exc

        lines = [f"{folder}", ""]
        lines += read.notes
        lines.append(f"narration: {read.narration.relative_to(folder).as_posix()}")
        lines.append(f"images: {len(read.images)} in {MEDIA_DIRS[0]}/")
        lines.append("")
        for i, (shot, media) in enumerate(zip(read.script_shots, read.media), 1):
            head = (shot.text[:64] + "…") if len(shot.text) > 64 else shot.text
            lines.append(f"shot {i:02d}  {media.name}")
            lines.append(f"          {head or '(silent)'}")
        if read.warnings:
            lines.append("")
            lines += [f"warning: {w}" for w in read.warnings]

        return io.NodeOutput({"project_dir": str(folder)},
                             ui=ui.PreviewText("\n".join(lines)))


def _resolve(project: str, project_dir: str) -> Path:
    """The picker, unless an explicit path overrides it."""
    if project_dir.strip():
        return Path(project_dir.strip())
    return PROJECTS_DIR / project
