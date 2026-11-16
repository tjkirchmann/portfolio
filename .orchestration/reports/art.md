# Report: art

- **Design:** `.orchestration/designs/art.md`
- **Branch:** `ai-feat/art`
- **Head commit:** see the commit that adds this file (`git log -1 ai-feat/art`)
- **Pushed to origin:** yes
- **Round:** 1

## Summary of changes

A Blender pipeline that renders seamless looping isometric wireframe animations, plus three
finished subjects and a project skill.

- `art/cli.py` runs Blender headless (`-b --factory-startup`) and renders a subject
  (`art/subjects/<slug>.py`) to `public/art/<slug>/{loop.webm, loop.mp4, poster.png,
  meta.json}`, or a 600 px preview to `art/.cache/<slug>/preview/`, or stills, or runs
  `--check` (measured evidence for most criteria; exit 1 on any failure).
- `art/framework/` owns everything that is not the subject: the one true isometric
  orthographic camera, framing (the subject's root is scaled and centred from its animated
  bounds; the camera never changes), the line renderer, the frame pipeline, the loop check,
  encoding with Blender's own FFmpeg, MP4 faststart, file probing and the checks.
- **Line technique.** The spike's idea (edges become geometry with emission) is kept, but
  instead of bevelled curve tubes each edge becomes a screen-facing ribbon with round join
  discs at vertices, built each frame with numpy. Under the orthographic camera this gives
  exactly constant width (1.25 px at delivery) and clean round joins at every corner, which
  bevelled 2-point tubes do not (their flat ends notch the outside of corners). Every ribbon
  is pushed along the view axis by its brightness (invisible under orthographic
  projection), so where lines cross the brighter one wins: a max composite, so dim lines
  never cut notches into bright ones and overlapping joins never double up.
- **Depth read.** Brightness = depth fade along the view axis (near 1.0, far 0.3 of near,
  over the whole loop's depth range) x a facing factor: edges of back faces 0.28, front-facing
  edges hidden behind nearer surfaces 0.45 (from a per-frame depth pass of the real meshes),
  visible front edges 1.0. All edges stay visible, as in the reference.
- **Anti-aliasing.** EEVEE at 2x (2400 px), 64 samples, then separable Lanczos-3 down to
  1200 px in linear light; the master is RGBA PNG with one neutral colour (#ebebeb) and
  alpha = coverage x brightness.
- `art/builders/`: involute gear + meshing train (`gear.py`), lathe/revolve and torus
  (`lathe.py`), extrude-along-path and torus knots (`sweep.py`), box and beam lattice
  (`lattice.py`), shared quad helpers incl. clean 2:1 and 3:1 reduction bands (`mesh.py`).
- Subjects: `gears` (8 spur gears, two depth layers via a compound gear), `gyroscope`
  (lathe-turned rotor spinning inside two nodding gimbal rings on a stand), `knot` (tube on
  a trefoil whose surface flows along itself). All quads, no triangles, no n-gons.
- `.claude/skills/wireframe-art/SKILL.md`: how a later session turns "make art of X" into
  a subject, previews, looks, checks and renders.
- Format bake-off for `gears`: `.orchestration/reports/art-formats.md`.

## Acceptance criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC-1 | met | `python3 art/cli.py gears` (and gyroscope, knot) wrote all four files: see Tests run. `--preview` wrote `art/.cache/gears/preview/out/{loop.mp4,poster.png,meta.json}` (600 px, 16 samples). `ls -la public/art/*` below. |
| AC-2 | met | `public/art/gears/meta.json` keys exactly `slug, subject, width, height, fps, frames, duration, blurDataUrl`; blurDataUrl is a 32x32 greyscale PNG, 779 bytes, data URL 1062 characters (check line `[AC-2]`). Gyroscope 678 B / 926 chars, knot 694 B / 950 chars. |
| AC-3 | met | Master RGBA sequence in `art/.cache/<slug>/frames/` (ignored by git). `magick identify` of `frames/f_0150.png`: `1200x1200 srgba GrayscaleAlpha`, RGB constant 235/255 (stddev 0), alpha mean 20/255. Fraction of pixels with alpha 0 per frame: gears 0.713-0.714, gyroscope 0.824-0.829, knot 0.83. Videos are the master over #000 (`art/.cache/<slug>/black/`). |
| AC-4 | met | Ribbons have a constant world width under the orthographic camera. Measured effective width (integrated linear light across the edge, minus the local floor, / expected luminance) of isolated edges at 1200 px, by `--check`: gears 1.228-1.364 px (back far/near, front far/near), gyroscope 1.215-1.348 px, knot 1.299-1.395 px, across near/mid/far front, hidden and back edges. Far edges are dimmer (e.g. knot front_near peak 174/255, front_far 70/255), not thinner. |
| AC-5 | met | Rendered at 2400 px, 64 TAA samples, Lanczos-3 to 1200 (`art/framework/post.py`). Max vertex displacement per frame over the whole loop, delivery px: gears 1.423, gyroscope 1.813, knot 1.322. Crops: `art-shots/<slug>-consecutive-400pct.png` (frames 150-152 at 400%). |
| AC-6 | met | Render-time check renders frame N+1 (t = 1.0, not wrapped) and compares with frame 1: gears MAD 0.0024/255, gyroscope 0.0183/255, knot 0.0000/255 (limit 0.5). `pipeline.py` returns exit 1 and writes no outputs if it fails. `--check` repeats it. |
| AC-7 | met | `--check`: every object 0 triangles, 0 n-gons (gears 8 gears, 1806-3432 quads each; gyroscope rotor 1674 quads, rings 512 each, stand 762; knot 2880). Stills: `art-shots/gears-still.png`, `gyroscope-still.png`, `knot-still.png`. Teeth are one quad column following the flank; the rim band meets both fillets; webs reduce 6 -> 3 -> 1 columns per tooth with 2:1 and 3:1 bands. |
| AC-8 | met | 1200x1200, 30 fps, 300 frames, 10.0 s. Sizes (limit 1.5 MB = 1,572,864 B): gears mp4 1,390,593 / webm 1.228-1.364 px (back far/near, front far/near)EBM; gyroscope 1,374,938 / 1,501,881; knot 1,384,899 / 1,462,299. MP4 probe: `avc1`, High profile, chroma 4:2:0 (yuv420p), boxes `ftyp free moov mdat` (faststart). WebM: `V_VP9`. Not played in Safari itself (see Not verified). |
| AC-9 | met | `.orchestration/reports/art-formats.md`, crops `art-shots/gears-formats-200pct.png` and `gears-video-frame150-200pct.png`. Default delivery stays WebM + MP4. |
| AC-10 | met | `art/subjects/gears.py` 25 lines, `gyroscope.py` 60, `knot.py` 22. Each declares only `TITLE`, `LOOP_SECONDS`, `AZIMUTH`, optional `FILL`, `build()`, `animate(t)`. No camera, light, material, check or encode code. `gyroscope.py` also has two 3-line local helpers (`ring`, `pin`) that `build()` uses. |
| AC-11 | met | Gears: ratios from tooth counts, loop = smallest driver turn after which every gear shows an identical image (see Gear ratio maths). Gyroscope: rotor spins a quarter turn per loop (its mesh is 4-fold symmetric), gimbals nod +-6 deg on sines with a phase offset. Knot: surface slides 12 rings along the knot and rolls 2 sides around the tube per loop. All close: AC-6 values. |
| AC-12 | met | `.claude/skills/wireframe-art/SKILL.md`. Dry run: the knot was made after the skill was written, following it step by step (form/motion, builder table, subject template, stills, `--check`, final). The dry run's `--check` caught a real fault (sweep frames jumped at the seam: 26.9 px/frame), fixed in `builders/sweep.py`, now 1.322 px/frame. |
| AC-13 | met | Command line (printed by the CLI): `/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python art/framework/main.py -- ...`; `TMPDIR` set to `art/.cache/_blender_tmp`; all outputs under `art/.cache/` and `public/art/`. |
| AC-14 | met | Back-face edges drawn at 0.28 of front at equal depth, re-evaluated every frame from face normals. Measured drawn brightness / depth fade on isolated edges, all three subjects: back 0.276-0.298, hidden front 0.459-0.464, visible front 1.001-1.039. With/without: `art-shots/gears-dimming-off-on.png`. |
| AC-15 | met (with interpretation) | Spacing measured in the surface (distance between midpoints of opposite edges of every quad, world -> delivery px), not on screen: on screen, any curved surface's lines converge at its silhouette, so a screen-space minimum cannot hold for cylinders. Gears min 5.2, max 32.2 px; gyroscope 5.2 / 40.6; knot 18.5 / 32.8. Polar surfaces reduce columns with clean 2:1 (and 3:1 on gear webs) quad bands, no triangles: `art-shots/gears-hub-300pct.png`. |
| AC-16 | met | Involute flanks (4 segments) from the base circle, circular root fillets (2 segments, rho 0.35 M), 20 deg pressure angle, 0.1 M backlash (0.16 M on the 24-tooth gear). 16-phase check: 0 vertices of any gear inside its partner for all 6 meshing pairs, min clearance 0.018-0.108 M. Crop: `art-shots/gears-mesh-point-300pct.png`. |
| AC-17 | not met | `art-shots/gears-vs-reference.png`. Better on topology, line quality and depth read; composition slightly worse (see Comparison with the reference). The design says worse on any of the four fails, so this criterion fails. |
| AC-18 | met | Root scale and offset computed from 72 sampled phases of the animated bounds (`scene.py`), never by hand. Rendered bbox fill of the shorter side, every frame: gears 0.833-0.835, gyroscope 0.785, knot 0.784-0.785; no frame touches the edge. First/middle/last: `art-shots/<slug>-first-middle-last.png`. Depth overlap: gears compound pinion and its partner in a second layer pass in front of the main train; gyroscope rings and rotor pass in front of each other; knot crosses itself three times. |
| AC-19 | met | One camera made in `framework/camera.py`: ORTHO, ortho_scale 10, elevation 35.2644 deg, azimuth from {45, 135, 225, 315} only (anything else raises). Printed by `--check` for all three subjects (all use azimuth 45, so the matrices are identical): see Tests run. The camera is created once and never animated. |

## Gear ratio maths (AC-11)

Each gear's mesh is symmetric under a two-tooth turn (the web's 2:1 band repeats every 2/3
tooth), so a gear shows an identical image after turning by any multiple of 2/N turns.
Meshing gears pass the same number of teeth; gears on one shaft share a turn. The train
helper finds the smallest driver turn after which every body has turned a multiple of its
gears' symmetry, and the loop uses exactly that.

| Gear | N | Meshes | Ratio to driver | Turns per loop | Teeth passed |
| --- | --- | --- | --- | --- | --- |
| b (driver) | 24 | - | 1 | 1/4 | 6 |
| b_pinion (same shaft, layer +3.2 M) | 16 | - | 1 | 1/4 | 4 |
| a | 14 | b | -12/7 | -3/7 | 6 |
| g | 18 | a | 4/3 | 1/3 | 6 |
| c (front layer) | 14 | b_pinion | -8/7 | -2/7 | 4 |
| d | 16 | b | -3/2 | -3/8 | 6 |
| e | 18 | b | -4/3 | -1/3 | 6 |
| f | 20 | d | 6/5 | 3/10 | 6 |

Every teeth-passed count is a multiple of 2, so every gear returns to an identical image;
the loop check confirms it (AC-6). Phases are set so each meshing pair has a tooth centred
in its partner's gap on the line of centres.

## Comparison with the reference (AC-17)

`art-shots/gears-vs-reference.png`: reference left, frame 1 right, both 884 px tall.

- **Topology: better.** Ours: involute teeth with root fillets, quads that follow the flank,
  a rim band that meets the fillets, webs that reduce cleanly to the hub, real step walls
  for rim, web and hub. The reference has blocky trapezoid teeth, radial spokes bunching
  toward the hubs and uneven cells.
- **Line quality: better.** Constant 1.25 px lines, round joins, clean crossings, no glow;
  the reference's lines are soft, haloed and vary in weight.
- **Depth read: better.** Back faces at 0.28 and hidden lines at 0.45 make each gear read as
  a solid in front of or behind its neighbours; the reference draws every line equally and
  relies on perspective and colour.
- **Composition: slightly worse.** Both are a cluster of about eight gears in two depth
  layers filling most of the frame. The reference has more variety in gear size (two large
  gears dominate) and a denser, more interlocked silhouette; ours has similar-sized gears
  (14-24 teeth, kept in that range so the finest quads stay above 5 px) and empty top-left
  and bottom-right corners. Isometric projection also shows a lot of every gear's back face
  and walls, which makes the interior busier than the reference's near-frontal view.

## Tests run

```
$ python3 art/cli.py gears
$ /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 --python .../art/framework/main.py -- render .../art/subjects/gears.py --slug gears --quality final
FRAME 1/300 ... FRAME 271/300
LOOP CHECK frame 301 vs frame 1: MAD 0.0024/255 (limit 0.5) PASS
WROTE .../public/art/gears/loop.mp4 1390593 bytes (1119 kbps)
WROTE .../public/art/gears/loop.webm 1462635 bytes (865 kbps)
WROTE .../public/art/gears/poster.png, meta.json (blurDataUrl 1062 chars)

$ python3 art/cli.py gyroscope
LOOP CHECK frame 301 vs frame 1: MAD 0.0183/255 (limit 0.5) PASS
WROTE .../public/art/gyroscope/loop.mp4 1374938 bytes (1119 kbps)
WROTE .../public/art/gyroscope/loop.webm 1501881 bytes (984 kbps)
WROTE .../public/art/gyroscope/poster.png, meta.json (blurDataUrl 926 chars)

$ python3 art/cli.py knot
LOOP CHECK frame 301 vs frame 1: MAD 0.0000/255 (limit 0.5) PASS
WROTE .../public/art/knot/loop.mp4 1384899 bytes (1119 kbps)
WROTE .../public/art/knot/loop.webm 1462299 bytes (984 kbps)
WROTE .../public/art/knot/poster.png, meta.json (blurDataUrl 950 chars)

$ python3 art/cli.py gears --preview
FRAME 1/300 ... LOOP CHECK frame 301 vs frame 1: MAD 0.0021/255 (limit 0.5) PASS
(preview loop.mp4, poster.png, meta.json in art/.cache/gears/preview/out/)
```

`python3 art/cli.py --check <slug>` (full logs trimmed to the measured lines):

```
gears:
[AC-18] framing: root scale 0.16519, fill target 0.83, depth range -5.975..6.209
[AC-7] b: 3432 quads, 0 triangles, 0 n-gons, 6864 edges PASS
[AC-7] b_pinion: 2096 quads, 0 triangles, 0 n-gons, 4192 edges PASS
[AC-7] a: 1806 quads, 0 triangles, 0 n-gons, 3612 edges PASS
[AC-7] g: 2466 quads, 0 triangles, 0 n-gons, 4932 edges PASS
[AC-7] c: 1806 quads, 0 triangles, 0 n-gons, 3612 edges PASS
[AC-7] d: 2096 quads, 0 triangles, 0 n-gons, 4192 edges PASS
[AC-7] e: 2466 quads, 0 triangles, 0 n-gons, 4932 edges PASS
[AC-7] f: 2740 quads, 0 triangles, 0 n-gons, 5480 edges PASS
[AC-15] b: quad spacing min 5.3px (1st pct 5.3) max 32.1px PASS
[AC-15] b_pinion: quad spacing min 5.2px (1st pct 5.2) max 30.9px PASS
[AC-15] a: quad spacing min 5.2px (1st pct 5.2) max 30.1px PASS
[AC-15] g: quad spacing min 5.2px (1st pct 5.2) max 31.6px PASS
[AC-15] c: quad spacing min 5.2px (1st pct 5.2) max 30.1px PASS
[AC-15] d: quad spacing min 5.2px (1st pct 5.2) max 30.9px PASS
[AC-15] e: quad spacing min 5.2px (1st pct 5.2) max 31.6px PASS
[AC-15] f: quad spacing min 5.2px (1st pct 5.2) max 32.2px PASS
[AC-5] max vertex displacement 1.423px/frame (frame 227) PASS
[AC-18] geometry bounds fill 0.829-0.830 of frame, clips edge: False PASS
[AC-11] driver turns per loop 1/4
[AC-11]   b: N=24 mesh symmetry 12 ratio 1 turns/loop 1/4 teeth passed 6.000 meshes None layer 0.0 PASS
[AC-11]   b_pinion: N=16 mesh symmetry 8 ratio 1 turns/loop 1/4 teeth passed 4.000 meshes None layer 3.2 PASS
[AC-11]   a: N=14 mesh symmetry 7 ratio -12/7 turns/loop -3/7 teeth passed 6.000 meshes b layer 0.0 PASS
[AC-11]   g: N=18 mesh symmetry 9 ratio 4/3 turns/loop 1/3 teeth passed 6.000 meshes a layer 0.0 PASS
[AC-11]   c: N=14 mesh symmetry 7 ratio -8/7 turns/loop -2/7 teeth passed 4.000 meshes b_pinion layer 3.2 PASS
[AC-11]   d: N=16 mesh symmetry 8 ratio -3/2 turns/loop -3/8 teeth passed 6.000 meshes b layer 0.0 PASS
[AC-11]   e: N=18 mesh symmetry 9 ratio -4/3 turns/loop -1/3 teeth passed 6.000 meshes b layer 0.0 PASS
[AC-11]   f: N=20 mesh symmetry 10 ratio 6/5 turns/loop 3/10 teeth passed 6.000 meshes d layer 0.0 PASS
[AC-16] a x b: 16 phases, vertices inside partner: 0, min clearance 0.0734 module PASS
[AC-16] g x a: 16 phases, vertices inside partner: 0, min clearance 0.0933 module PASS
[AC-16] c x b_pinion: 16 phases, vertices inside partner: 0, min clearance 0.0999 module PASS
[AC-16] d x b: 16 phases, vertices inside partner: 0, min clearance 0.1076 module PASS
[AC-16] e x b: 16 phases, vertices inside partner: 0, min clearance 0.0239 module PASS
[AC-16] f x d: 16 phases, vertices inside partner: 0, min clearance 0.0950 module PASS
[AC-16] b: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 11.276 rf 10.750 ra 13.000
[AC-16] b_pinion: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 7.518 rf 6.750 ra 9.000
[AC-16] a: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 6.578 rf 5.750 ra 8.000
[AC-16] g: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 8.457 rf 7.750 ra 10.000
[AC-16] c: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 6.578 rf 5.750 ra 8.000
[AC-16] d: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 7.518 rf 6.750 ra 9.000
[AC-16] e: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 8.457 rf 7.750 ra 10.000
[AC-16] f: involute flank 4 segs + fillet 2 segs (rho 0.353 M), rb 9.397 rf 8.750 ra 11.000
[AC-6] frame 301 (t=1) vs frame 1 (t=0): MAD 0.0024/255, limit 0.5 PASS
[AC-4] back_far: width 1.228px brightness 0.1 depth 0.08 at [243.3, 860.4] peak 19.6/255 PASS
[AC-14] back_far: drawn brightness / depth fade = 0.277 (front visible 1.0, front hidden 0.45, back 0.28)
[AC-4] back_near: width 1.364px brightness 0.214 depth 0.66 at [851.3, 711.4] peak 42.6/255 PASS
[AC-14] back_near: drawn brightness / depth fade = 0.293 (front visible 1.0, front hidden 0.45, back 0.28)
[AC-4] front_far: width 1.28px brightness 0.409 depth 0.16 at [271.9, 829.5] peak 87.2/255 PASS
[AC-14] front_far: drawn brightness / depth fade = 1.012 (front visible 1.0, front hidden 0.45, back 0.28)
[AC-4] front_near: width 1.279px brightness 0.811 depth 0.73 at [874.9, 686.5] peak 173.9/255 PASS
[AC-14] front_near: drawn brightness / depth fade = 1.01 (front visible 1.0, front hidden 0.45, back 0.28)
[AC-18] rendered bbox fill per frame 0.833-0.835; first [101, 111, 1100, 1088], middle [101, 111, 1100, 1088], last [100, 111, 1100, 1088]; touches edge: False PASS
[AC-6] render-time loop MAD 0.0024/255 PASS
[AC-1] /Users/ty/repos/portfolio/.claude/worktrees/art/public/art/gears: all four files present PASS
[AC-2] meta keys ['slug', 'subject', 'width', 'height', 'fps', 'frames', 'duration', 'blurDataUrl'] PASS
[AC-2] blurDataUrl 32x32 PNG, 779 bytes, data URL 1062 chars PASS
[AC-8] meta 1200x1200 30fps 300 frames 10.0s PASS
[AC-8] loop.mp4: 1390593 bytes (1.33 MB) {"top_level": ["ftyp", "free", "moov", "mdat"], "faststart": true, "duration": 10.0, "width": 1200, "height": 1200, "frames": 300, "fps": 30.0, "codec": "avc1", "profile_idc": 100, "level_idc": 50...
[AC-8] loop.webm: 1462635 bytes (1.39 MB) {"codec": "V_VP9", "width": 1200, "height": 1200, "frames": 300, "duration": 10.0} PASS
CHECK gears: all checks passed

[AC-19] camera azimuth 45
  type=ORTHO ortho_scale=10.0 elevation=35.2644
  [-0.707107, -0.408248,  0.577350,  28.867514]
  [ 0.707107, -0.408248,  0.577350,  28.867514]
  [ 0.000000,  0.816497,  0.577350,  28.867514]
  [ 0.000000,  0.000000,  0.000000,  1.000000]
(identical for gears, gyroscope and knot)

gyroscope:
[AC-15] stand 5.6-40.6, outer_gimbal 15.9-36.3, inner_gimbal 15.2-29.8, rotor 8.5-24.9,
        pins 17.3-17.6, knobs 5.2-20.7 px  PASS
[AC-5] max vertex displacement 1.813px/frame (frame 294) PASS
[AC-6] frame 301 (t=1) vs frame 1 (t=0): MAD 0.0183/255, limit 0.5 PASS
[AC-4] widths 1.215-1.348 px (back far/mid/near, front far/mid/near, front hidden mid) PASS
[AC-14] back 0.276-0.290, front hidden 0.464, front 1.001-1.035
[AC-18] rendered bbox fill per frame 0.785-0.785; touches edge: False PASS
[AC-8] loop.mp4: 1374938 bytes ... "faststart": true, "codec": "avc1", "profile": "High", "chroma": "4:2:0 (yuv420p)" PASS
[AC-8] loop.webm: 1501881 bytes {"codec": "V_VP9", "width": 1200, "height": 1200, "frames": 300, "duration": 10.0} PASS
CHECK gyroscope: all checks passed

knot:
[AC-7] knot: 2880 quads, 0 triangles, 0 n-gons, 5760 edges PASS
[AC-15] knot: quad spacing min 18.5px max 32.8px PASS
[AC-5] max vertex displacement 1.322px/frame (frame 137) PASS
[AC-6] frame 301 (t=1) vs frame 1 (t=0): MAD 0.0000/255, limit 0.5 PASS
[AC-4] widths 1.299-1.395 px (8 edges: back, front, front hidden; near/mid/far) PASS
[AC-14] back 0.287-0.298, front hidden 0.459-0.462, front 1.020-1.039
[AC-18] rendered bbox fill per frame 0.784-0.785; touches edge: False PASS
[AC-8] loop.mp4 1384899 bytes, loop.webm 1462299 bytes PASS
CHECK knot: all checks passed
```

```
$ ls -la public/art/*
public/art/gears:
total 8304
drwxr-xr-x@ 6 ty  staff      192 Nov 16 18:36 .
drwxr-xr-x@ 5 ty  staff      160 Nov 16 18:13 ..
-rw-r--r--@ 1 ty  staff  1390593 Nov 16 18:30 loop.mp4
-rw-r--r--@ 1 ty  staff  1462635 Nov 16 18:36 loop.webm
-rw-r--r--@ 1 ty  staff     1217 Nov 16 18:36 meta.json
-rw-r--r--@ 1 ty  staff   494968 Nov 16 18:36 poster.png

public/art/gyroscope:
total 7944
drwxr-xr-x@ 6 ty  staff      192 Nov 16 18:05 .
drwxr-xr-x@ 5 ty  staff      160 Nov 16 18:13 ..
-rw-r--r--@ 1 ty  staff  1374938 Nov 16 18:01 loop.mp4
-rw-r--r--@ 1 ty  staff  1501881 Nov 16 18:05 loop.webm
-rw-r--r--@ 1 ty  staff     1084 Nov 16 18:05 meta.json
-rw-r--r--@ 1 ty  staff   326113 Nov 16 18:05 poster.png

public/art/knot:
total 7968
drwxr-xr-x@ 6 ty  staff      192 Nov 16 18:17 .
drwxr-xr-x@ 5 ty  staff      160 Nov 16 18:13 ..
-rw-r--r--@ 1 ty  staff  1384899 Nov 16 18:13 loop.mp4
-rw-r--r--@ 1 ty  staff  1462299 Nov 16 18:17 loop.webm
-rw-r--r--@ 1 ty  staff     1106 Nov 16 18:17 meta.json
-rw-r--r--@ 1 ty  staff   325234 Nov 16 18:17 poster.png
```

## Files changed

| Path | Change |
| --- | --- |
| `art/cli.py` | added: entry point (render, `--preview`, `--still`, `--check`, `--encode-only`) |
| `art/framework/camera.py` | added: the one isometric orthographic camera |
| `art/framework/scene.py` | added: scene reset, subject loading, framing from animated bounds |
| `art/framework/lines.py` | added: ribbon + round-join line renderer, facing/hidden/depth brightness, max composite |
| `art/framework/render.py` | added: per-frame depth pass and 2x EEVEE render |
| `art/framework/post.py` | added: Lanczos-3 downscale, master RGBA, over-black frames, blur PNG |
| `art/framework/pipeline.py` | added: frame loop, loop check, capped encodes, poster, meta.json |
| `art/framework/encode.py` | added: Blender FFmpeg encodes (H.264, VP9, AV1) |
| `art/framework/mp4.py` | added: MP4 faststart rewrite, MP4 and WebM probes |
| `art/framework/checks.py` | added: `--check` measurements |
| `art/framework/main.py` | added: Blender-side entry |
| `art/builders/*.py` | added: mesh helpers, gear/train, lathe/torus, sweep/knot, box/lattice |
| `art/subjects/gears.py`, `gyroscope.py`, `knot.py` | added: the three subjects |
| `art/tools/bakeoff.py`, `bakeoff_blender.py` | added: format bake-off (AC-9) |
| `art/tools/shots.py` | added: report shots (ImageMagick, viewing aid only) |
| `public/art/gears/`, `gyroscope/`, `knot/` | added: rendered loops, posters, meta.json |
| `.claude/skills/wireframe-art/SKILL.md` | added: project skill |
| `.orchestration/reports/art.md`, `art-formats.md`, `art-shots/` | added: this report, bake-off, evidence images |

## System report (as built)

### Packages

| Package | Original or third-party | Purpose |
| --- | --- | --- |
| Blender 5.2 LTS (`/Applications/Blender.app`) | third-party | Modelling, EEVEE render, numpy, video encode (bundled FFmpeg) |
| `art/framework` | original | Camera, framing, lines, pipeline, encode, probes, checks |
| `art/builders` | original | Procedural quad-mesh builders |
| `art/cli.py` | original | Entry point (system `python3`, standard library only) |
| ImageMagick 7.1.2 `magick`, libwebp 1.6.0 `img2webp`, libheif 1.21.2 `heif-enc` (Homebrew, already installed) | third-party | Bake-off only (GIF, animated WebP, animated AVIF) and report crops. Not used by the render pipeline. Nothing was downloaded. |

### Primitives

- **Subject:** `art/subjects/<slug>.py` with `TITLE`, `LOOP_SECONDS`, optional `AZIMUTH`
  (45/135/225/315) and `FILL`, `build()` returning objects, `animate(t)` periodic on [0, 1).
  `mesh_source` is a reserved seam: a subject that sets it is rejected.
- **Builder:** a function or class returning a clean quad mesh object (`gear.Train`,
  `lathe.revolve`, `lathe.torus`, `sweep.Sweep`, `lattice.box`, `lattice.lattice`).
- **Master:** RGBA PNG sequence, `art/.cache/<slug>/frames/f_####.png`, constant #ebebeb,
  alpha = coverage x brightness.
- **Loop:** `public/art/<slug>/{loop.webm, loop.mp4, poster.png, meta.json}`.

### High-level workflows

- Render: cli -> Blender headless -> build -> frame to animated bounds -> per frame: animate
  -> depth pass -> line mesh -> EEVEE 2x -> Lanczos -> master + over-black -> loop check
  (frame N+1 vs 1) -> H.264 + VP9 (constant quality, falling back to an average bitrate
  that fits 1.45 MiB) -> faststart -> poster (frame 1 over black) -> blur -> meta.json.
- New subject: prompt -> skill -> subject file -> stills -> look -> `--check` -> final ->
  `--check` -> commit.

### Data and endpoints

- Writes `public/art/<slug>/{loop.webm, loop.mp4, poster.png, meta.json}` (committed).
  `poster.png` is frame 1 over black, matching the videos (so it can be screen-blended the
  same way).
- Writes `art/.cache/` (ignored): masters, over-black frames, previews, stills, render
  stats, bake-off encodes, Blender temp.

## Deviations from the design

- **Line technique:** screen-facing ribbons with round join discs instead of bevelled curve
  tubes. Allowed by the design only if it beats the spike on AC-4 and AC-5: width is exactly
  constant (as with tubes under ortho) and joins are round and clean at every corner
  (tubes leave notches at corners and double-bright overlaps); AA and motion are identical
  (same 2x/64-sample render and downscale). No side-by-side render of the tube technique
  was made to prove "beats" numerically.
- **Hidden-line dimming added** (front-facing edges behind nearer surfaces at 0.45). Not
  asked for; added because without it the isometric view (which shows much of each gear's
  back face and walls) read as a tangle. AC-14's back-face dimming is unchanged.
- **AC-15 interpretation:** spacing is measured in the surface, not on screen (see AC-15).
- **Bitrate fallback:** H.264/VP9 at constant quality (CRF 23 / 32) exceeded 1.5 MB for all
  three subjects (an earlier gears layout: 9.2 MB at CRF 26; the final gears VP9 at CRF 32: 23.6 MB), so the pipeline re-encodes at an average bitrate
  (H.264 1119 kbps, VP9 865-984 kbps) to stay under the limit. Visible cost at 200%+: H.264
  softens and adds faint noise to dim interior lines between keyframes
  (`art-shots/gears-video-frame150-200pct.png`); VP9 is cleaner.
- **Gear proportions:** teeth are one quad column wide (two columns made the bottom row
  of each tooth a sliver under 5 px); 0.1 M backlash (0.16 M on the 24-tooth gear) to leave
  room for fillets and a root land wide enough for AC-15.
- **AC-17 not met:** composition is slightly worse than the reference (fewer size contrasts, emptier corners).

## Not done or not verified

- **`lattice.box`, `lattice.lattice` and `lathe.torus` are only smoke-tested** (built in
  Blender: 160, 945 and 256 faces, 0 triangles, 0 n-gons); no subject uses them yet.
- **Safari playback not tested** in a browser. Evidence is the probe: H.264 High profile,
  4:2:0, faststart, even dimensions.
- **Browser support** in the bake-off table is from general knowledge, not tested here.
- **AV1/animated AVIF settings not tuned.** heif-enc defaults gave a 43.6 MB AVIF; an
  inter-frame-tuned AVIF would be much smaller. GIF and WebP used simple settings.
- **The camera is not locked against a subject that edits it** in `animate`; the framework
  owns and never moves it, and the skill forbids touching it, but Python cannot stop a
  subject from doing so.
- **AC-19 "identical apart from azimuth"**: all three subjects use azimuth 45, so the
  printed matrices are identical; the other three azimuths were not rendered.
- **Width measurement** needs edges with no other line within 3 px of the profile; in the
  dense gears only 4 such edges were found (back far/near, front far/near), none mid-depth
  or hidden. The measurement subtracts the local floor (tails of neighbouring lines) at the
  profile ends; without that, a very dim far back edge read 1.63 px.
- What a critical eye would still pick at:
  - Gears: the 6-columns-per-tooth rim and its ring rows read as a fine mesh texture at
    full frame; the 3:1 kites on small gears' webs are visible; gears are similar in size.
  - Gears: dim hidden lines inside the cluster still form busy moire-like patterns where
    two gears overlap in depth.
  - Encoded video softness on dim lines at the 1.5 MB cap (H.264 more than VP9).
  - Gyroscope: the knobs and pins are small, simple cylinders; the stand top boss is plain.
  - Knot: wide, short composition (fill measured on the longer side, 0.78), so it reads
    smaller than the other two.
