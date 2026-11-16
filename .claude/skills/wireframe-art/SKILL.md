---
name: wireframe-art
description: Make a new looping isometric wireframe animation for the portfolio site. Use when asked to "make art of X", "add a wireframe loop", "new subject for the art pipeline", or to change or re-render an existing subject in art/subjects/.
---

# Wireframe art: new subject

The pipeline in `art/` turns a short Python subject file into a seamless loop:
`public/art/<slug>/{loop.webm, loop.mp4, poster.png, meta.json}`. The framework owns the
camera, line rendering, framing, loop check and encoding. You write only the subject.

Rules that are not negotiable (house rules, see `CLAUDE.md`):

- Light neutral lines on transparency. No colour, no fills, no glow, ever.
- One fixed true isometric orthographic camera. The subject moves, never the camera. A
  subject may pick `AZIMUTH` from 45, 135, 225, 315 and nothing else.
- Procedural geometry only (`mesh_source` is a reserved seam; it is not implemented).

## 1. Read the prompt as a form and a motion

Write down, before any code:

- **Form**: what is it made of? Map each part to a builder (below). Prefer forms whose
  axes of rotation lie on X, Y or Z, with parts stacked or offset along those axes, so
  circles become the standard isometric ellipses. Something that "is" a circle should be a
  revolve; something that "is" a tube should be a sweep.
- **Motion**: what does the thing *do*? Pick a motion that suits it, not a turntable:
  gears mesh, rotors spin, gimbals nod, a tube flows along itself, a lattice breathes.
- **Depth**: which parts pass in front of which? Plan at least one overlap in depth.

## 2. Pick builders (`art/builders/`)

| Builder | Use for | Notes |
| --- | --- | --- |
| `gear.Train(module, axis, cycles)` + `.add(name, N, at= / mesh=other, angle= / shaft=other, layer=)` | gear trains | involute teeth, fillets, rim/web/hub steps; `pose(t)` animates with correct ratios and computes the loop rotation. Use even N >= 14. Compound gears: `shaft=` plus `layer=` (axial offset, ~3.2 modules clears both hub bosses). |
| `lathe.revolve(name, [(r, z), ...], cols=64, target=, closed=False)` | anything turned: rotors, vases, pins, stands, rings | points with r == 0 at either end close with clean polar caps; columns halve toward the axis through 2:1 bands. `closed=True` for rings. |
| `lathe.torus(name, R, r, cols)` | round rings | |
| `sweep.Sweep(name, curve, radius, sides=, target=)` + `.update(slide, roll)` | tubes along a closed path, knots | `slide` in rings and `roll` in sides; whole-number totals per loop are seamless. `sweep.torus_knot(p, q, R, r, z)` gives a curve. |
| `lattice.box`, `lattice.lattice` | boxes, beam lattices | quad grids, even division |
| `mesh.MeshBuilder` | custom quads | `ring`, `bridge`, `bridge_loops`, `reduce_2to1`, `reduce_3to1`, `build_annulus` |

Topology rules the checks enforce: quads only (no triangles), even density (in-surface
spacing between neighbouring parallel edges 5-60 px at delivery size), polar surfaces
reduce their columns toward the centre instead of bunching spokes.

## 3. Write `art/subjects/<slug>.py` (about 80 lines max)

```python
"""One line: what it is and what it does."""
import math
from builders.lathe import revolve

TITLE = "Gyroscope"      # goes into meta.json as "subject"
LOOP_SECONDS = 10        # 6-12
AZIMUTH = 45             # optional: 45 | 135 | 225 | 315
FILL = 0.78              # optional: share of the frame the loop bounds fill (0.70-0.85)

def build():
    global part
    part = revolve("part", [(0, 1), (1, 1), (1, -1), (0, -1)], cols=32)
    return [part]        # every object to draw; set .parent between them if needed

def animate(t):          # t in [0, 1); must be periodic: animate(1.0) == animate(0.0)
    part.rotation_euler = (0, 0, 2 * math.pi / 4 * t)   # a quarter turn of a 4-fold shape
```

Never put camera, lights, materials, render settings or encoding in a subject.

**Making the loop close.** At `t = 1` every object must look exactly as at `t = 0`:

- Oscillations: use `sin(2 * pi * t + phase)`; they always close.
- Rotations: rotate a part by a multiple of its own symmetry angle. A revolve with `cols`
  columns and polar caps is 4-fold (caps end in one quad), so a quarter turn closes;
  without caps it is `cols`-fold. Gear trains compute this for you.
- Sweeps: `slide` by a whole number of rings, `roll` by a whole number of sides.

**Keeping motion slow.** No vertex may move more than 2 px per frame at 1200 px. Rotation
speed is limited by the radius: at 30 fps for N frames, a point at radius r px turning by
angle A radians moves r * A / N px per frame. `--check` measures it.

## 4. Preview, then look

```bash
python3 art/cli.py <slug> --still 0 0.33 0.66        # 1200 px stills -> art/.cache/<slug>/stills/
python3 art/cli.py <slug> --still 0 --no-back-dim    # same, without back/hidden dimming
python3 art/cli.py <slug> --preview                  # 600 px loop -> art/.cache/<slug>/preview/out/loop.mp4
```

Open the stills with the Read tool and crop with `magick in.png -crop WxH+X+Y -filter point
-resize 300% out.png` (ImageMagick is only a viewing aid; the pipeline does not use it).
Be a harsh critic. Check:

- Silhouette fills the frame and reads at a glance; parts overlap in depth.
- Hidden and back lines are clearly dimmer than front lines; the form reads as a solid.
- No spokes bunching at a centre, no thin slivers, no near-duplicate lines, no tangles
  where two parts sit at the same depth.
- Lines are even and unbroken at 300% zoom; joins are round, crossings clean.

Iterate on the subject (and builders, if a form needs a new one) until it holds up.

## 5. Check, render final, check again

```bash
python3 art/cli.py --check <slug>     # camera, topology, density, motion, framing, loop, widths
python3 art/cli.py <slug>             # final: 1200 px, 64 samples at 2x, ~3-4 s/frame; run in the background
python3 art/cli.py --check <slug>     # now also verifies the four delivered files
```

The final render fails (exit 1, nothing written) if frame N+1 differs from frame 1 by
0.5/255 or more. `--check` exits 1 if any criterion fails; read its `[AC-n]` lines.
`--encode-only` re-encodes cached frames without rendering. Commit `art/subjects/<slug>.py`
and `public/art/<slug>/`.

## How the framework works (when something looks wrong)

- `art/framework/camera.py`: the one camera (ortho, ortho_scale 10, from (1, 1, 1)).
- `art/framework/scene.py`: loads the subject, parents it to a root, samples 72 phases and
  scales/centres the root to `FILL`. The camera never changes.
- `art/framework/lines.py`: each edge becomes a screen-facing ribbon (1.25 px at delivery)
  with round joins. Brightness = depth fade x (BACK 0.28 for edges of back faces, OCC 0.45
  for front edges hidden behind nearer surfaces, from a per-frame depth pass). Ribbons are
  pushed along the view axis by brightness so crossings take the brighter line.
- `art/framework/render.py`, `post.py`: EEVEE at 2x, Lanczos-3 down to 1200 px in linear
  light, master RGBA PNG in `art/.cache/<slug>/frames/`, over-black frames for video.
- `art/framework/encode.py`: Blender's own FFmpeg (H.264 + VP9); `mp4.py` makes MP4s
  faststart and probes outputs. The Homebrew ffmpeg on this machine is broken: never use it.
