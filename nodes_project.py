"""The project folder: the door in, and the first thing that can go wrong.

Two nodes, and between them they are the start of the pipeline.

`MemoActs — Set Narration` is where a project begins. It names one into
existence and puts the finished voice inside it, which is the seam the voice
workflow used to end short of: a graph produced an `AUDIO`, and a person then
carried a file out of ComfyUI's output folder into `projects/` by hand. That is
a terminal's job done with a mouse, and `docs/INTERFACE_BRIEF.md` exists to
forbid exactly it.

`MemoActs — Project` is where the reel begins. Every later step needs a folder
holding a script, a recording and some images; naming that folder is trivial,
and *finding out whether the tool can see what you put in it* is not. Getting
that wrong silently is how a student loses a session, so this node reads the
folder and reports it: which recording it found and how long, how many images,
how many shots the script has, which shot got which media, and every warning
the shot list raised.

Neither is slow. `read_project` touches the disk and no model; `set_narration`
writes one wav, and skips even that when the samples have not changed.
"""
from __future__ import annotations

from pathlib import Path

from comfy_api.latest import io, ui

from .memoacts_core.pipeline import (ProjectError, read_project,
                                     set_narration)
from .memoacts_core.project import MEDIA_DIRS
from .nodes_audio import audio_at_own_rate
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


#: Characters a project name may not contain, because a name is a folder name
#: and nothing else. A path separator would let a graph write outside
#: `projects/`, and a leading dot hides the folder from the picker that is
#: supposed to list it.
_BAD_NAME = ("/", "\\", ":", "*", "?", '"', "<", ">", "|")


def _clean_name(name: str) -> str:
    """A project name, or a refusal that says which character was the problem."""
    name = (name or "").strip().strip(".")
    if not name:
        raise ValueError("give the project a name — it becomes the folder your "
                         "script, your recording and your pictures live in")
    bad = [c for c in _BAD_NAME if c in name]
    if bad:
        raise ValueError(f"{''.join(bad)!r} cannot be in a project name: it is "
                         f"a folder name, not a path")
    return name


class MemoActsSetNarration(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="MemoActsSetNarration",
            display_name="MemoActs — Set Narration",
            category="memoacts",
            description=(
                "Puts the finished voice into a project, and makes the project "
                "if it is not there yet. Wire the end of the voice workflow "
                "into it, type a name, and press Run — that folder is then what "
                "every other node means by 'my project'. Always writes WAV, "
                "because a stray narration.mp3 beats a narration.wav silently."
            ),
            is_output_node=True,
            inputs=[
                io.Audio.Input(
                    "audio",
                    tooltip="The voice as you want it heard — the output of the "
                            "voice workflow, or a plain Load Audio if there is "
                            "nothing to fix.",
                ),
                io.String.Input(
                    "project", default="",
                    tooltip="A folder name under projects/. A name nobody has "
                            "used yet is made into an empty project; an "
                            "existing one is used as it stands.",
                ),
                io.Boolean.Input(
                    "create_if_missing", default=True,
                    tooltip="Off refuses an unknown name instead of making it — "
                            "which is what you want once the project exists and "
                            "a typo should not quietly start a second one.",
                ),
            ],
            outputs=[Project.Output("PROJECT")],
        )

    @classmethod
    def fingerprint_inputs(cls, audio, project, create_if_missing):
        """Re-run when the file this node owns is not the one it left.

        A changed `audio` already re-runs the node, because a wired input is
        part of the cache key on its own. What that misses is the folder being
        emptied, renamed or restored underneath a graph whose widgets never
        moved — and then a Run that looks like it worked writes nothing.

        Deliberately *not* `float("nan")`. Always-run is the obvious answer and
        the wrong one: this node's output feeds Align, and a node that always
        re-runs makes everything downstream of it re-run too — ninety seconds of
        Whisper, on every queue, for a wav that did not change.
        """
        try:
            folder = PROJECTS_DIR / _clean_name(project)
        except ValueError:
            return "unnamed"
        try:
            st = (folder / "sources" / "narration.wav").stat()
            return f"{folder}|{st.st_mtime_ns}|{st.st_size}"
        except OSError:
            return f"{folder}|absent"

    @classmethod
    def execute(cls, audio, project, create_if_missing):
        name = _clean_name(project)
        folder = PROJECTS_DIR / name
        data, rate = audio_at_own_rate(audio)
        try:
            res = set_narration(folder, data, rate, create=create_if_missing)
        except ProjectError as exc:
            raise ValueError(str(exc)) from exc

        lines = [str(folder), ""]
        lines.append("project created" if res.created
                     else "project already there")
        lines.append(
            f"narration.wav {'written' if res.changed else 'unchanged'} — "
            f"{res.seconds:.2f}s, {res.channels} ch, {res.sample_rate} Hz")
        if not res.changed:
            lines.append("          the samples are identical to what was "
                         "already there, so the file was left alone and the "
                         "alignment stays cached")
        for p in res.superseded:
            lines.append(f"moved aside: {p.name} — it would have beaten "
                         f"narration.wav alphabetically")

        # What is still missing, in the order it has to arrive. This is the
        # only place that knows the project is brand new, so it is the only
        # place that can say what to do next without guessing.
        todo = []
        shots = _script_shots(folder)
        if shots:
            lines.append(f"script.md: {len(shots)} scene(s), "
                         f"{res.seconds / len(shots):.1f}s each on average")
        else:
            todo.append("write your scenes into script.md — one '## S01' "
                        "heading per scene, and the words under it")
        images = _count_images(folder)
        if images:
            lines.append(f"{MEDIA_DIRS[0]}/: {images} image(s)")
        else:
            todo.append(f"put your pictures in {MEDIA_DIRS[0]}/")
        if todo:
            lines += ["", "Before MemoActs — Project will run:"]
            lines += [f"  {i}. {t}" for i, t in enumerate(todo, 1)]
        else:
            lines += ["", "Ready — run MemoActs — Project next."]
        if res.warnings:
            lines.append("")
            lines += [f"warning: {w}" for w in res.warnings]

        return io.NodeOutput({"project_dir": str(folder)},
                             ui=ui.PreviewText("\n".join(lines)))


def _script_shots(folder: Path):
    """The scenes in `script.md`, or none — a brand-new project has an empty one."""
    from .memoacts_core.project import parse_script_shots
    try:
        return parse_script_shots(folder / "script.md")
    except OSError:
        return []


def _count_images(folder: Path) -> int:
    from .memoacts_core.project import list_images
    try:
        return len(list_images(folder / MEDIA_DIRS[0]))
    except OSError:
        return 0
