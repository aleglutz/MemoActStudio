# Hand-assembling a reel in an NLE

The pack renders reels end to end, but a deadline sometimes wants the edit made
by hand. This is how the two fit together without fighting.

## Where the editor's workspace lives

Anywhere **outside the repo** — on the author's machine, a
`freecut-workspace` folder beside the ComfyUI install.

**Outside the repo, deliberately.** FreeCut unpacks a whole workspace wherever
it is pointed — media copies, thumbnails, waveform caches, its own `README.md`
and a nested `projects/` tree. Pointed at a MemoActs project it collided by
name (`projects/legends_of_surrender/projects/`) and dropped its README exactly
where the project's own would go.

If FreeCut ever asks for a workspace folder again, give it a path outside
the repository. The
`.gitignore` still carries guard rules in case it does not.

The workspace is self-contained: media is referenced by UUID and no file in it
holds an absolute path, so it can be moved again with a plain `mv` as long as
the app is closed.

## What the pipeline hands to the editor

Rather than keyframing motion by hand once per shot, render the moving stills
and import them as footage:

    python tools/render_reel.py --project projects/<name>     # whole reel
    # or one clip per still — see the clips recipe below

Each clip arrives at 1080×1920, 30 fps, with eased motion already baked in.
Trim from either end; a slow move reads fine cut short.

Motion is chosen from each source's own headroom, which matters more than it
sounds. A wide archival photograph usually has to be *enlarged* to fill a
vertical frame, and zooming into it compounds that. A pan translates a
fixed-size window instead, so it costs nothing extra — which is why wide
sources get pans and only tall ones get zooms. `MemoActs — Shot Report` prints
the headroom per shot as `max_zoom`; below 1.00 means the frame is already
being enlarged and should not be zoomed at all.

## What stays out of the clips

- **Audio.** Narration is a separate track; the pipeline never re-encodes it.
- **Subtitles.** The pipeline can burn them via libass for free, but burnt text
  fights an edit that is still moving. Set them in the NLE, or burn them on a
  final pass once the timing is settled.

## What is not versioned

The edit itself lives in the FreeCut workspace and is **not** in git. Tracking
it in place would turn every preview regeneration into a diff. If a cut is
worth keeping, export it from the app and store the export.
