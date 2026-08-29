# Image sources and rights — Legends of Surrender

The media itself is not versioned (`.gitignore`), so this is the only record of
where each file came from and on what terms. The project is grant-funded
(Auswärtiges Amt), which makes provenance a deliverable rather than a courtesy.

One row per file whose rights have been checked. A file absent from this table
has **not** been checked — that is a gap, not a clearance.

| File | Source | Rights | Depicts |
|---|---|---|---|
| `Truman_Churchill_Potsdam.jpg` | Wikimedia Commons, from Imperial War Museums **BU 8944**. Photographer Capt. W. T. Lockeyear, No. 5 Army Film & Photographic Unit | **Public domain** (`PD-UKGov`) | Churchill and Truman shaking hands on the steps of Truman's residence, Kaiser Strasse, Babelsberg, **16 July 1945**, during the Potsdam conference |
| `Loznitca_VDay_Treptov.jpg` | Frame from **Sergei Loznitsa, *Victory Day*, 2018** | **Not public domain — unresolved.** See below | 9 May commemoration at Treptower Park, Berlin: Night Wolves colours, a Donetsk People's Republic flag, St George ribbons, Immortal Regiment portraits |
| `map_france_reims.png`, `map_baltics.mp4`, `map_poland_ukraine.mp4` | Drawn by `tools/render_map.py` from Natural Earth 1:50m Admin 0 Countries (`assets/geo/`, see `assets/geo/SOURCE.md`) | **Public domain** (Natural Earth). Authored graphics, not generated imagery | Europe: France with a Reims pin; the Baltic states; Poland and Ukraine |
| `New_York_May-8_1945.jpg` | **Museum Berlin-Karlshorst**, from the page *The German surrender in May 1945*, https://www.museum-karlshorst.de/english-the-german-surrender-in-may-1945/ . Credited there: **"unknown, akg images, Berlin"** | **Agency-licensed, cleared by the commissioning museum** — see below | VE Day on Wall Street, New York, 8 May 1945 |

## The one shot that is not ours or public domain

`Loznitca_VDay_Treptov.jpg` is a frame from a copyrighted documentary still in
distribution, and it is the only shot in the reel with **no route to clearance
yet identified**. The rest is public domain, project-drawn, footage the project
holds, or — in the New York picture's case — carried on the commissioning
museum's own agency licence.

Two things follow, and neither is settled by this file:

1. **Clearance or quotation.** Either permission from the rights holder, or a
   deliberate decision that the use is quotation — which in German law
   (§51 UrhG) turns on the quotation serving an argument about the work quoted,
   and requires the source to be named. The reel currently carries **no on-screen
   credit**, so on the quotation route that is a missing piece, not an optional
   one.
2. **The people in it.** Identifiable private individuals at a political rally,
   filmed by someone else, reused in a different film about the politics of that
   commemoration. That is a separate question from copyright and it does not go
   away by clearing the copyright.

Not a reason to drop the shot — it is the strongest image in the reel for the
line it sits under, and Loznitsa's film is *about* this exact phenomenon. It is
a reason not to let it reach a public screening unresolved.

## The New York picture, and why it is recorded rather than cleared

`New_York_May-8_1945.jpg` was taken from Museum Berlin-Karlshorst's own English
page on the surrender, where it appears credited *"unknown, akg images,
Berlin"*. Resolved 2026-08-29 on the project owner's judgement: **the reel is
made for MBK, the picture is already published by MBK, and it travels back into
the museum on the museum's own licence.**

That is a defensible position and it is the one this project takes. What it is
not is a licence held by us: akg-images is a rights-managed agency, and a
licence for a web page is not automatically a licence for a film. The single
action that closes this properly costs one email — **ask MBK to confirm the akg
licence covers the reel**, and, if the film is ever screened outside the museum,
ask again for that use. Until then the entry above says "cleared by the
commissioning museum", which is precisely as far as it goes.

The photographer is recorded as unknown, so the on-screen credit, if one is
given, is the agency: *akg-images, Berlin*.

## Where a picture and its line disagree

`Truman_Churchill_Potsdam.jpg` sits on the shot at **1:10**, whose line is about
the two of them announcing the surrender before ratification — **8 May 1945**.
The photograph is from **16 July**, ten weeks later, at a different conference.

Both men are correct; the moment is not. Showing the people a line is about is
ordinary documentary practice, and no caption in the reel claims this is the
announcement. But this film is specifically about how the memory of the war's
end gets bent, so the compromise is written down here rather than left to be
noticed later: **if a May 1945 photograph of the two turns up, it is the better
picture**, and not for legal reasons.

## The map plates and their base data

Recorded here because the maps are the only material in the reel the project
draws itself, and a drawn map makes a claim about borders whether or not it
means to.

| Field | Value |
|---|---|
| Files | `sources/maps/map_france_reims.png`, `map_baltics.mp4`, `map_poland_ukraine.mp4` |
| Source | Natural Earth 1:50m Admin 0 Countries, via `nvkelso/natural-earth-vector` (`geojson/`) |
| Upstream | https://www.naturalearthdata.com/ |
| Dataset version | Not stamped in the file. Pinned instead by content hash of the committed copy: `sha256:3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb` |
| Download date | 2026-08-10 (`assets/geo/SOURCE.md`) |
| Licence | Public domain. No permission, fee or attribution required |
| Verification status | **Corrected and verified 2026-08-22.** The shipped geometry assigned Crimea and Sevastopol to Russia; `correct_crimea()` in `tools/render_map.py` reassigns the peninsula to Ukraine and re-tests seven towns across it on every render, refusing to draw if the check fails. Plates above rendered with `moved Russia part #100 -> Ukraine` |

### Why the correction is in the build script and not in the data file

The committed geojson is left byte-for-byte as downloaded, so its hash still
matches upstream and the provenance line above stays checkable. The border
correction lives in the tool, where it is visible, commented, re-verified on
every run, and cannot be silently lost by re-downloading the dataset.

Germany, the EU and UN General Assembly Resolution 68/262 do not recognise the
2014 annexation. For a film funded by the Auswärtiges Amt this is a compliance
requirement rather than an editorial preference, which is why the check raises
instead of warning.
