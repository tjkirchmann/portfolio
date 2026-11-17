# Design: art

- **Branch:** `ai-feat/art`
- **Status:** implementing
- **Approved by user:** 2026-11-16

## Goal

A framework that turns a subject into a seamless looping wireframe animation for the site.
A subject is one small Python file that builds and animates a mesh procedurally in Blender;
the framework owns camera, line rendering, looping, encoding and output. The bar is that a
VFX artist would not find a fault in the line quality or the loop.

## Scope

**In:**

- `art/cli.py`: render a subject by slug, with preview and final quality.
- `art/framework/`: scene setup, line rendering, loop helpers, encoders, checks.
- A small library of reusable procedural builders (gear, torus, lattice, lathe/revolve,
  extrude-along-path) so new subjects are short.
- Three finished subjects as proof: `gears` (meshing gear train, like the reference image),
  and two more of different character chosen by the agent (for example a lathe-built form
  and a lattice or knot).
- A project skill at `.claude/skills/wireframe-art/SKILL.md` so that "make art of X" in a
  later Claude session produces a new `art/subjects/<slug>.py` and renders it.
- A format bake-off on one subject (see AC-9).

**Out:**

- Organic subjects from text-to-3D or imported meshes. Leave a clear seam
  (`mesh_source` in the subject API) but build nothing for it.
- Anything under `src/`. The site design consumes the output files.
- Colour in the wireframe.

## Acceptance criteria

- **AC-1:** `python3 art/cli.py <slug>` runs Blender headless and writes
  `public/art/<slug>/loop.webm`, `loop.mp4`, `poster.png`, `meta.json`. `--preview` renders
  a fast low-res version to `art/.cache/` instead. Evidence: command output and `ls -la`.
- **AC-2:** `meta.json` is `{ slug, subject, width, height, fps, frames, duration,
  blurDataUrl }`, where `blurDataUrl` is a base64 PNG no wider than 32px and under 2 KB.
  Evidence: the file for `gears`.
- **AC-3:** Lines are a single light neutral colour on a transparent master (RGBA PNG
  sequence in `art/.cache/<slug>/frames/`). No fills, no colour, no background. Delivered
  videos are that master over pure black (`#000`), so the site can screen-blend them.
  Evidence: a master frame and the alpha histogram (most pixels alpha 0).
- **AC-4:** Line width is constant in screen space, 1.0-1.5px at delivery size, regardless
  of depth. Far edges are dimmer than near edges (depth fade), not thinner. Evidence: zoomed
  crop of near and far edges, measured widths.
- **AC-5:** No aliasing crawl: rendered at 2x delivery size with at least 64 samples and
  downscaled with a Lanczos or better filter, and
  motion is slow enough that no edge moves more than 2px per frame at delivery size.
  Evidence: three consecutive frames cropped at 400% and the measured max displacement.
- **AC-6:** The loop is seamless: the frame after the last equals the first. Checked
  automatically by rendering frame `N+1` and comparing with frame `1` (mean absolute
  difference under 0.5/255); the CLI fails if not. Evidence: the check output per subject.
- **AC-7:** Topology is clean: quads flowing with the form, even density, no stray diagonals,
  no n-gon fans except where the form needs them. Evidence: a still of each subject in the
  report.
- **AC-8:** Delivery is 1200x1200 at 30fps, loop length 6-12s, each of `loop.webm` and
  `loop.mp4` under 1.5 MB, `loop.mp4` plays in Safari (H.264, yuv420p, faststart).
  Evidence: probe output and file sizes.
- **AC-9:** Format bake-off for `gears`: the same master encoded as real GIF, animated WebP,
  animated AVIF, VP9 WebM, AV1 WebM (or MP4) and H.264 MP4, with a table of size, visual
  notes at 200% zoom and browser support, saved as
  `.orchestration/reports/art-formats.md` with crops in `.orchestration/reports/art-shots/`.
  The owner picks the delivery format from this; the default stays WebM + MP4 until then.
  Evidence: the table and crops.
- **AC-10:** A subject file is at most about 80 lines and declares only: `build()` returning
  objects, `animate(t)` for `t` in `[0,1)` periodic, and optional camera/framing hints.
  Camera, lines, loop check and encode are never repeated in a subject. Evidence: the three
  subject files.
- **AC-11:** Motion is designed, not just a turntable: `gears` teeth mesh with correct ratios
  and the whole loop closes; the other two each have a motion suited to the form. Evidence:
  ratio maths in the report and the loop check.
- **AC-12:** `SKILL.md` explains, for a future session: how to read a subject prompt, pick
  builders, write the subject file, preview, check the stills by eye, then render final.
  Evidence: the file, and a dry run where the agent follows it to make the third subject.
- **AC-14:** Edges that belong only to faces pointing away from the camera are drawn at
  25-40% of front-edge brightness, re-evaluated every frame, so the form reads as a solid
  and not as a tangle. Evidence: a still with and without the dimming.
- **AC-15:** Even density: at delivery size no two parallel neighbouring edges of the same
  surface are closer than 5px, and none farther apart than 60px. Polar surfaces reduce their
  radial edge count toward the centre (a clean 2:1 quad reduction loop, no triangles) rather
  than letting spokes bunch at the hub. Evidence: measured min and max spacing per subject,
  and a 300% crop of a hub.
- **AC-16:** Gear teeth are involute profiles with root fillets, at least 4 segments per
  flank, and mesh without interpenetration at every frame (checked at 16 phases).
  Evidence: the check output and a 300% crop of a mesh point.
- **AC-17:** Side-by-side against the reference: one image with
  `.orchestration/designs/ref/gears-reference.webp` on the left and a `gears` frame on the
  right at the same size, plus an honest list of where the render is better, equal or worse
  on topology, line quality, depth read and composition. "Worse" on any of the four is a
  failed criterion. Evidence: `.orchestration/reports/art-shots/gears-vs-reference.png`.
- **AC-18:** Composition: the subject fills 70-85% of the frame's shorter side through the
  whole loop, never clips the frame edge, and overlaps in depth (parts pass in front of
  parts) rather than lying flat. Framing is computed from the animated bounds, not set by
  hand. Evidence: bounds per subject and first, middle and last frames.
- **AC-19:** Every subject is rendered through the same true isometric camera, owned by the
  framework: orthographic, looking along (1, 1, 1) toward the origin (elevation 35.264
  degrees, azimuth 45 degrees), Z up. A subject cannot change the projection or the angles;
  it may only choose which of the four diagonal azimuths (45, 135, 225, 315) to view from.
  The camera never moves or rotates during a loop: motion comes from the subject. Evidence:
  the camera matrix printed by `--check` for each subject, identical apart from azimuth.
- **AC-13:** Rendering never writes outside the repo, and never touches the user's Blender
  config (`--factory-startup`). Evidence: the Blender command line.

## System report (intended state)

### Packages

| Package | Original or third-party | Purpose |
| --- | --- | --- |
| Blender 5.2 (`/Applications/Blender.app`) | third-party | Modelling, line render, video encode |
| `art/framework` | original | Scene, line style, loop helpers, checks, encode |
| `art/builders` | original | Procedural mesh builders |
| `art/cli.py` | original | Entry point |
| `ffmpeg-static` or similar | third-party, only if needed | Encoding formats Blender cannot write (GIF, WebP, AVIF) for the bake-off |

The Homebrew `ffmpeg` on this machine is broken. Do not use or repair it.

### Primitives

- **Subject:** `art/subjects/<slug>.py` with `build`, `animate(t)`, framing hints.
- **Builder:** a function returning a clean quad mesh.
- **Master:** RGBA PNG sequence, the source for every delivery format.
- **Loop:** delivery files plus `meta.json` under `public/art/<slug>/`.

### High-level workflows

- Render: cli → Blender headless → build → animate per frame → line render → master →
  loop check → encode → poster and blur → `meta.json`.
- New subject: prompt → skill → subject file → preview → look → final render → commit.

### Data and endpoints

- Writes `public/art/<slug>/{loop.webm,loop.mp4,poster.png,meta.json}` (committed).
- Writes `art/.cache/` (ignored).

## Constraints and notes

- **Owns:** `art/`, `public/art/*` except `public/art/_placeholder/`,
  `.claude/skills/wireframe-art/`, `.orchestration/reports/art.md`,
  `.orchestration/reports/art-formats.md`, `.orchestration/reports/art-shots/`.
- **Must not touch:** `src/`, `package.json`, lockfiles, `public/art/_placeholder/`,
  `CLAUDE.md`, `.gitignore`, other designs or reports.
- **Proven baseline, start here.** `.orchestration/designs/ref/spike.py` renders
  `ref/spike.png` in about 1 second per 1600px frame on this machine (EEVEE, 64 samples,
  Blender 5.2, headless). Its technique: every mesh edge becomes a 2-point poly spline in a
  curve object with `bevel_depth = 1`, and each point's radius is
  `(px / resolution) * (sensor / lens) / 2 * depth_along_view`, which gives constant
  screen-space width under perspective. The material is emission only, strength mapped from
  camera Z depth. Front and back edges go to two curve objects with different strengths.
  Rebuild the curves each frame. Another technique is allowed only if it beats this on AC-4
  and AC-5; a plain Wireframe modifier does not, its width changes with depth.
- **Isometric changes the spike in two ways.** The spike uses a perspective camera; the
  framework uses the orthographic isometric camera of AC-19. Under orthographic projection
  screen width no longer depends on depth, so the point radius is a constant
  `(px / resolution) * ortho_scale / 2`. Depth dimming stays, mapped from distance along the
  view axis across the subject's bounds. With no perspective to separate near from far, the
  back-edge dimming of AC-14 and the depth dimming carry the whole depth read: tune them
  with that in mind. Where the reference image and isometric disagree (it is a perspective
  render), isometric wins; AC-17 still judges topology, line quality, depth read and
  composition.
- Model subjects so isometric flatters them: axes of rotation along X, Y or Z, parts
  stacked and offset along the axes, so circles become the three standard isometric
  ellipses.
- **What the spike gets wrong, and the design requires fixed:** blocky trapezoid teeth
  (AC-16), spokes bunching at the hubs (AC-15), back-edge dimming too weak to read (AC-14),
  gears lying flat and not meshed (AC-11, AC-18), near-duplicate rings 0.002 apart that
  double the lines at steps (use real step geometry), tube ends not joined at vertices
  (chain edges into continuous splines along edge loops so corners are clean).
- **What the reference does that we keep:** all edges visible, polar quad grids on faces,
  mid loops on side walls, raised hubs and rims, parts overlapping in depth, slight
  brightening where lines converge. **What we drop:** the colour and the glow.
- Reference image: `.orchestration/designs/ref/gears-reference.webp`. Open it before
  modelling and again before writing the report.
- Final renders may be slow. Run them in the background, one at a time, and keep each
  foreground command under 2 minutes.
- Look at your own stills before claiming quality. List in the report anything a critical
  eye would still pick at.

## How to test

```bash
python3 art/cli.py gears --preview
python3 art/cli.py gears
python3 art/cli.py --check gears     # loop, size and contract checks only
```

Passing: all exit 0 for all three subjects, the checks print their measured values, and the
report includes stills and zoomed crops.

## Amendment 1 (2026-11-16, from the owner after watching the loops)

The owner dropped the gears and asked for two new subjects. Where this amendment conflicts
with the text above, the amendment wins.

**Dropped:** the `gears` subject and its output. Delete `art/subjects/gears.py` and
`public/art/gears/`. AC-11's gear clause, AC-16 and AC-17 no longer apply. The gear builder
may stay if it is clean; nothing needs to use it. The bake-off report stays as it is.
`gyroscope` and `knot` are accepted as they are: do not change their look.

**Camera rule (replaces the last two sentences of AC-19):** the projection and the
isometric angles stay fixed for every subject. A subject may animate the orthographic
scale (zoom) and the camera's pan in the view plane, both periodic in `t`, through a
framework API. Line width stays constant in pixels at every zoom level.

- **AC-20 `spikeball`:** a sphere covered in soft rounded spikes, like a child's sensory
  toy ball: 60-120 stubby tapered nubs with rounded tips, evenly spread (no pole pinching:
  cube-sphere or similar all-quad base, spikes grown from quad patches with clean support
  loops at the base). Evidence: still, and a 300% crop of three neighbouring spikes.
- **AC-21 `spikeball` motion:** the surface looks alive. Three layered motions, all exactly
  periodic over the loop: a slow breathing of the whole radius; waves that travel across
  the surface so spikes lengthen, shorten and lean in sequence rather than in unison; and
  a crawl, where the surface between spikes slides and bulges as if something moves under
  the skin (looped noise sampled on a closed path, displacing along the normal and
  tangent). No rigid turntable as the main motion; a slow drift in orientation is allowed
  if it closes. It must read as organic, not as a sine wobble: at least two noise
  octaves, no visible mirror symmetry, no moment where everything is at rest. Evidence:
  six evenly spaced frames, the loop check, and the motion formula in the report.
- **AC-22 `spikeball-zoom`:** a second clip, same ball and same living motion throughout.
  Timeline: hold on the whole ball for roughly the first quarter; then zoom into one
  region the way a satellite view dives into a city map, to at least 12x; hold briefly on
  the close view; then pull back out to the exact starting framing so it loops. Ease in
  and out; no linear zoom, no cut. Zoom exponentially (constant apparent speed).
  Evidence: frames at the start, mid-dive, closest, mid-return, and the loop check.
- **AC-23 detail on the way in:** the dive must reveal structure, not just enlarge a coarse
  grid. As the zoom passes each level, finer wire detail fades in inside the target region
  (finer subdivision of the same surface, then a surface micro-structure at the closest
  level, for example smaller nubs, pores or ridges between the spikes, still crawling) and
  fades out again on the way back. On-screen edge spacing stays between 5 and 60px at every
  zoom level. Fades are by brightness, never pops. Evidence: a 5-frame strip through the
  dive with measured spacing at each.
- **AC-24:** AC-3, AC-4, AC-6, AC-7, AC-13, AC-14, AC-15 and AC-18 apply to both new
  subjects (AC-18's fill rule applies to the wide framing only). AC-5's 2px-per-frame limit
  applies to `spikeball` and to the held parts of `spikeball-zoom`; during the dive use
  motion blur or enough frames that lines do not strobe. AC-8 applies with these changes:
  `spikeball` loop 8-12s; `spikeball-zoom` loop 16-24s and each file under 3 MB. AC-10's
  80-line limit is relaxed to 150 lines for these two; shared code goes in builders.
- **AC-25:** update `SKILL.md` for the zoom and pan API and the level-of-detail fade, and
  remove gears from its examples.

Report as round 2 in `.orchestration/reports/art.md`: add rows for AC-20 to AC-25, mark the
dropped criteria as dropped, and keep the earlier rows.

## Amendment 2 (2026-11-16, from the owner)

The owner's words: "can i get an alternative front page art piece that puts the life
simulation as metallic colors on the spikeball's surface. I also want a waveball with the
same effects." Light process: no evidence tables, crops or measurements. Build it, look at
it, make sure `python3 art/cli.py <slug>` runs and the loop closes, short note in the report.

This is the one place colour is allowed in the art. The plain `spikeball` stays as it is.

- **AC-26 life on the surface.** A framework feature any subject can switch on: Conway's
  Life runs on the mesh's own quads (each face is a cell, neighbours are the faces sharing
  an edge or corner), stepping about 10 times a second, kept alive by planting small
  long-lived seeds when activity drops. It rides the deforming surface, so cells stretch
  and crawl with the skin and climb the spikes.
- **AC-27 metallic cells.** A live face is a filled, flat-shaded, metallic tile: real
  glossy shading from a fixed key light so tiles flash as the surface turns and breathes
  under it, dark saturated base, small hot highlights, slight hue shift with angle. Colours
  are the site's: emerald `#76c8a5`, teal `#579d87`, deep `#326e54`, with patches (about a
  tenth each) of aqua `#58b3b3` and metallic blue `#4a86c8`, assigned by surface region, not
  per cell. Highlights go toward white-green. No yellow, gold or orange. A face that dies
  fades out over a second or so in its own hue. Dead faces are fully transparent. Faces on
  the far side are hidden or much dimmer so the front reads cleanly. Keep most of the
  surface empty (roughly 70-85%) so it is wire first, jewels second.
- **AC-28 wire stays.** The same light wireframe lines are drawn over the tiles, unchanged
  in width and brightness rules. Delivery is still video on pure black for screen blending,
  now with colour. Size limit for these pieces: 3 MB per file; raise the bitrate enough
  that the tiles do not smear.
- **AC-29 loop.** The clip must still loop seamlessly, surface motion and Life both. Life
  is not periodic, so engineer the seam (for example let activity ebb to nothing just
  before the loop point and seed in just after, or blend the last second of cell
  brightness into the first). No visible pop or cut. Loop length 12-20s.
- **AC-30 `spikeball-life`:** the existing spike ball, same living motion, with AC-26 to
  AC-28 on its surface.
- **AC-31 `waveball-life`:** a new form, a sphere with no spikes whose surface carries
  rolling waves: several wave trains of different wavelength travelling across it in
  different directions, crests sharpening and troughs flattening like a liquid planet,
  plus the same slow breathing and under-the-skin crawl. All-quad cube-sphere, even
  density, exactly periodic. With AC-26 to AC-28 on its surface. Same isometric camera.
- Finish the `spikeball-zoom` render already in progress first if it is close; otherwise
  these two take priority and the zoom clip follows. One final render at a time.

Output contract unchanged: `public/art/<slug>/{loop.webm,loop.mp4,poster.png,meta.json}`.
