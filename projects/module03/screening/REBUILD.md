# Rebuilding the screening page's media

`index.html` is in git. `media/` is not, for the reason the repository's
`.gitignore` already gives about the stills: the film is Museum
Berlin-Karlshorst's, and this repository is public. GPL-3.0 covers the code; it
does not licence somebody else's archive.

Eight files, re-encoded from the originals in `../out/` and
`../../legends_of_surrender/out/`. Run from `projects/`:

```
mkdir -p module03/screening/media

# The reel keeps its native 1080x1920 -- it opens the session and a 720-wide
# copy is visibly softer on a beamer.
ffmpeg -y -i legends_of_surrender/out/reel_with_hook.mp4 \
       -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p \
       -movflags +faststart -c:a aac -b:a 160k \
       module03/screening/media/reel.mp4

# Levels 1-3. The A/B zoom keeps its full 2000x800: the argument of that level
# is how many pixels there are, so shrinking the comparison would quietly win
# it for the wrong side. The split frame is the one safe reduction -- it is a
# like-for-like comparison and both halves shrink together.
for spec in \
  "module03/out/L1_quotes.mp4|L1_quotes.mp4|scale=1068:800" \
  "module03/out/L2_sound.mp4|L2_sound.mp4|scale=1068:800" \
  "module03/out/L3_ab_zoom_30s.mp4|L3_ab_zoom.mp4|scale=2000:800" \
  "module03/out/L3_split_30s.mp4|L3_split.mp4|scale=1602:1200" ; do
  IFS='|' read -r src dst vf <<< "$spec"
  ffmpeg -y -i "$src" -vf "$vf" -c:v libx264 -crf 24 -preset slow \
         -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 128k \
         "module03/screening/media/$dst"
done

# Level 4 as three separate clips, native size, no audio.
for spec in \
  "L4_native_slow|L4_1_original" \
  "L4_colour|L4_2_colour_over_original" \
  "L4_raw_redraw|L4_3_reinvented" ; do
  IFS='|' read -r src dst <<< "$spec"
  ffmpeg -y -i "module03/out/$src.mp4" -c:v libx264 -crf 22 -preset slow \
         -pix_fmt yuv420p -movflags +faststart -an \
         "module03/screening/media/$dst.mp4"
done
```

About 80 MB in total, of which the reel is 42.

`-movflags +faststart` matters if this is ever served over HTTP — without it the
browser downloads the whole file before the first frame appears.

`out/L4_ab.mp4`, the three-panel version, is no longer on the page: the page
shows the same three states as three separate clips instead, which is easier to
look at one at a time. The file stays in `out/` like everything else there.

## If it goes on a website

The folder is self-contained and every path inside it is relative, so it can be
dropped in as-is. Before doing that, read the paragraph at the top of this file
again: the same reasoning that keeps `projects/module03/stills/` out of a public
repository applies to putting the footage on a public site. That is a
conversation with the museum, not a build step.
