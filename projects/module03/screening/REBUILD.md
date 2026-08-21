# Rebuilding the screening page's media

`index.html` is in git. `media/` is not, for the reason the repository's
`.gitignore` already gives about the stills: the film is Museum
Berlin-Karlshorst's, and this repository is public. GPL-3.0 covers the code; it
does not licence somebody else's archive.

Six files, re-encoded from the originals in `../out/` and
`../../legends_of_surrender/out/`. Run from `projects/`:

```
mkdir -p module03/screening/media

ffmpeg -y -i legends_of_surrender/out/reel_with_hook.mp4 \
       -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p \
       -movflags +faststart -c:a aac -b:a 160k \
       module03/screening/media/reel.mp4

for spec in \
  "module03/out/L1_quotes.mp4|L1_quotes.mp4|scale=1068:800" \
  "module03/out/L2_sound.mp4|L2_sound.mp4|scale=1068:800" \
  "module03/out/L3_ab_zoom_30s.mp4|L3_ab_zoom.mp4|scale=2000:800" \
  "module03/out/L3_split_30s.mp4|L3_split.mp4|scale=1602:1200" \
  "module03/out/L4_ab.mp4|L4_ab.mp4|scale=-2:720" ; do
  IFS='|' read -r src dst vf <<< "$spec"
  ffmpeg -y -i "$src" -vf "$vf" -c:v libx264 -crf 24 -preset slow \
         -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 128k \
         "module03/screening/media/$dst"
done
```

About 77 MB in total, of which the reel is 42.

**The reel keeps its native 1080×1920** — it opens the session and a 720-wide
copy is visibly softer on a beamer. **Level 3 keeps its full frame**, because
the whole argument of that level is how many pixels there are; shrinking the
comparison for the web would quietly win the argument for the wrong side. The
split frame goes 2136×1600 → 1602×1200, which is the one place a reduction is
harmless: it is a like-for-like comparison, and both halves shrink together.

`-movflags +faststart` matters if this is ever served over HTTP — without it the
browser downloads the whole file before the first frame appears.

## If it goes on a website

The folder is self-contained and every path inside it is relative, so it can be
dropped in as-is. Before doing that, read the paragraph at the top of this file
again: the same reasoning that keeps `projects/module03/stills/` out of a public
repository applies to putting the footage on a public site. That is a
conversation with the museum, not a build step.
