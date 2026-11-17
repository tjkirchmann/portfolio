"""Life on the surface: Conway's Life on a mesh's own quads, drawn as metallic tiles.

Any subject can switch it on with `attach(obj, frames, fps, seed=...)` after building its
mesh. Each face is a cell; neighbours are the faces sharing an edge or a corner. Life steps
STEP_HZ times a second (B3/S23), and small random seeds are planted where it has died out
whenever the live share drops below a floor, so the surface never goes quiet.

Brightness per face per frame: a cell that is born brightens in about 0.15 s, a cell that
dies fades over about 1 s in its own hue. Life is not periodic, so the seam is engineered:
the simulation runs one blend window past the loop, and the first window of the loop is a
cross-fade from that overrun to the start (frame 0 shows the state just after the last
frame), so the cut is invisible.

Tiles: live faces are rendered by EEVEE in a separate pass with a metallic material
(Principled, metallic 1, low roughness) lit by a fixed key light and a dark environment with
a bright green-white band to reflect, flat shaded, back faces culled, dead faces held out
(transparent but still hiding what is behind them). Colours by surface region: emerald,
teal and deep, with patches of aqua and blue. The wire pass is composited on top.
"""
import math

import bpy
import numpy as np

REGISTRY = {}  # object name -> Life

STEP_HZ = 10.0
BLEND_S = 1.5
RISE_S = 0.15
FADE_S = 1.0

PALETTE = {  # display sRGB
    "emerald": (0x76, 0xC8, 0xA5), "teal": (0x57, 0x9D, 0x87), "deep": (0x32, 0x6E, 0x54),
    "aqua": (0x58, 0xB3, 0xB3), "blue": (0x4A, 0x86, 0xC8),
}


def _lin(rgb):
    c = np.array(rgb, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _field(u, rng, waves=6, f=(1.0, 2.2)):
    """Smooth random field on the sphere (sum of plane waves), roughly in [-1, 1]."""
    s = np.zeros(len(u))
    for _ in range(waves):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        s += np.sin(2 * np.pi * rng.uniform(*f) * (u @ d) + rng.uniform(0, 2 * np.pi))
    return s / math.sqrt(waves / 2)


class Life:
    def __init__(self, obj, frames, fps, seed=3, floor=0.10, density=0.22):
        me = obj.data
        self.obj = obj
        F = np.array([p.vertices[:] for p in me.polygons], dtype=object)
        nf = len(me.polygons)
        V = np.array([v.co[:] for v in me.vertices])
        centres = np.array([V[list(f)].mean(0) for f in F])
        self.u = centres / np.linalg.norm(centres, axis=1)[:, None]
        # neighbours: faces sharing any vertex
        vf = {}
        for i, f in enumerate(F):
            for v in f:
                vf.setdefault(v, []).append(i)
        nb = [set() for _ in range(nf)]
        for faces in vf.values():
            for a in faces:
                nb[a].update(faces)
        rows, cols = [], []
        for i, s in enumerate(nb):
            s.discard(i)
            rows += [i] * len(s)
            cols += list(s)
        self.rows, self.cols = np.array(rows), np.array(cols)
        self.nb = [np.fromiter(s, int) for s in nb]
        self.nf = nf
        rng = np.random.default_rng(seed)
        self.rng = rng
        self.floor = floor
        self.density = density
        # colour by region
        lo = _field(self.u, rng)
        aqua = _field(self.u, rng, f=(1.2, 2.6)) > 1.25
        blue = _field(self.u, rng, f=(1.2, 2.6)) > 1.25
        base = np.where(lo[:, None] > 0.45, _lin(PALETTE["emerald"]),
                        np.where(lo[:, None] < -0.45, _lin(PALETTE["deep"]), _lin(PALETTE["teal"])))
        base[aqua] = _lin(PALETTE["aqua"])
        base[blue & ~aqua] = _lin(PALETTE["blue"])
        self.colour = base
        self.frames = frames
        self.fps = fps
        # the history is computed once and shared by parallel render workers
        import os
        cdir = os.environ.get("ART_CACHE_DIR")
        path = os.path.join(cdir, f"life_{obj.name}_{nf}_{frames}_{seed}.npy") if cdir else None
        if path and os.path.exists(path):
            self.brightness = np.load(path)
        else:
            self.brightness = self._simulate(frames, fps)
            if path:
                np.save(path + ".tmp.npy", self.brightness)
                os.replace(path + ".tmp.npy", path)

    def _count(self, alive):
        c = np.zeros(self.nf, np.int32)
        np.add.at(c, self.rows, alive[self.cols].astype(np.int32))
        return c

    def _seed(self, alive, n):
        """Plant n small blobs (a cell and about half its neighbours) in empty places."""
        dead = np.nonzero(~alive)[0]
        for i in self.rng.choice(dead, size=min(n, len(dead)), replace=False):
            alive[i] = True
            nbs = self.nb[i]
            alive[nbs[self.rng.random(len(nbs)) < 0.5]] = True

    def _simulate(self, frames, fps):
        alive = np.zeros(self.nf, bool)
        self._seed(alive, int(self.nf * self.density / 5))
        blend = int(round(BLEND_S * fps))
        total = frames + blend
        per_step = fps / STEP_HZ
        rise = 1.0 / max(1, RISE_S * fps)
        fall = 1.0 / max(1, FADE_S * fps)
        b = np.zeros(self.nf)
        # warm up so the first frame is a settled, living surface
        warm = int(4 * STEP_HZ)
        for _ in range(warm):
            alive = self._step(alive)
            b = np.where(alive, np.minimum(1, b + rise * per_step), np.maximum(0, b - fall * per_step))
        out = np.empty((total, self.nf), np.float32)
        acc = 0.0
        for f in range(total):
            acc += 1.0
            if acc >= per_step:
                acc -= per_step
                alive = self._step(alive)
            b = np.where(alive, np.minimum(1, b + rise), np.maximum(0, b - fall))
            out[f] = b
        # seam: frames [0, blend) cross-fade from the overrun (frames + i) to the start (i)
        w = (np.arange(blend) + 0.5) / blend
        w = w * w * (3 - 2 * w)
        out[:blend] = out[frames:frames + blend] * (1 - w[:, None]) + out[:blend] * w[:, None]
        return out[:frames]

    def _step(self, alive):
        c = self._count(alive)
        nxt = (c == 3) | (alive & (c == 2))
        if nxt.mean() < self.floor:
            self._seed(nxt, max(1, int(self.nf * 0.004)))
        return nxt

    def at(self, t):
        """Face brightness at loop phase t (linear interpolation between frames, periodic)."""
        x = (t % 1.0) * self.frames
        i = int(math.floor(x)) % self.frames
        j = (i + 1) % self.frames
        f = x - math.floor(x)
        return self.brightness[i] * (1 - f) + self.brightness[j] * f


def attach(obj, frames, fps=30, seed=3, **kw):
    life = Life(obj, frames, fps, seed, **kw)
    REGISTRY[obj.name] = life
    me = obj.data
    a = me.attributes.new("life", "FLOAT", "FACE")
    c = me.attributes.new("tile", "FLOAT_COLOR", "FACE")
    rgba = np.concatenate([life.colour, np.ones((life.nf, 1))], 1).astype(np.float32)
    c.data.foreach_set("color", rgba.ravel())
    a.data.foreach_set("value", np.zeros(life.nf, np.float32))
    me.materials.clear()
    me.materials.append(metal_material())
    return life


def update(obj, t):
    life = REGISTRY.get(obj.name)
    if life is None:
        return
    obj.data.attributes["life"].data.foreach_set("value", life.at(t).astype(np.float32))


def metal_material():
    mat = bpy.data.materials.get("life_metal")
    if mat:
        return mat
    mat = bpy.data.materials.new("life_metal")
    mat.use_nodes = True
    mat.use_backface_culling = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    hold = nt.nodes.new("ShaderNodeHoldout")
    mix = nt.nodes.new("ShaderNodeMixShader")
    life = nt.nodes.new("ShaderNodeAttribute")
    life.attribute_type = "GEOMETRY"
    life.attribute_name = "life"
    tile = nt.nodes.new("ShaderNodeAttribute")
    tile.attribute_type = "GEOMETRY"
    tile.attribute_name = "tile"
    # slight hue shift toward aqua at grazing angles
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    shift = nt.nodes.new("ShaderNodeMix")
    shift.data_type = "RGBA"
    shift.inputs["B"].default_value = (*_lin(PALETTE["aqua"]), 1.0)
    nt.links.new(lw.outputs["Facing"], shift.inputs["Factor"])
    nt.links.new(tile.outputs["Color"], shift.inputs["A"])
    nt.links.new(shift.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.2
    nt.links.new(life.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(hold.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def setup_lighting(scene):
    """Fixed key light plus a dark environment with a bright band for the metal to reflect.
    The film is transparent in every pass, so none of this shows as background."""
    sun = bpy.data.lights.new("key", "SUN")
    sun.energy = 4.0
    sun.color = (0.85, 1.0, 0.9)
    sun.angle = math.radians(6)
    ob = bpy.data.objects.new("key", sun)
    scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(50), math.radians(-25), math.radians(20))
    w = scene.world
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    els = ramp.color_ramp.elements
    # world "Generated" is the direction; Z in [-1, 1] (below 0 clamps to the first stop)
    els[0].position, els[0].color = 0.10, (0.002, 0.006, 0.005, 1)
    els[1].position, els[1].color = 0.20, (0.35, 0.5, 0.45, 1)
    for pos, col in ((0.30, (0.004, 0.01, 0.008)), (0.58, (0.006, 0.015, 0.012)),
                     (0.68, (1.2, 1.4, 1.25)), (0.78, (0.008, 0.02, 0.016)),
                     (0.98, (0.06, 0.12, 0.10))):
        e = els.new(pos)
        e.color = (*col, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 2.0
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
