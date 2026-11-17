"""Spike ball: a sphere covered in soft rounded nubs, with a living surface and optional
level-of-detail refinement for zoom shots.

Geometry. The skin is an equal-angle cube sphere (all quads, no pole pinching). On each
cube face a grid of square patches is cut out and a spike is grown from each patch: the
patch border is the spike's base ring, a support loop sits just above it, the section
turns from square to round as it rises, tapers, and closes in a hemispherical tip through
2:1 reduction bands ending in one quad.

Motion. Every vertex position is a pure function D(rest position, tau), so any refinement
of the mesh moves with exactly the same surface. tau is the motion phase in [0, 1); every
term uses whole cycles of tau, so tau = 1 equals tau = 0 exactly.
  - breathing: radius x (1 + 0.03 sin 2pi tau + 0.01 sin(4pi tau + 1.3))
  - spike waves: three plane waves travelling over the sphere set each spike's length
    (x 1 +- 0.16) and lean (bend up to ~0.22 rad toward the wave's gradient), so spikes
    move in sequence, never in unison
  - crawl: two octaves of looped spectral noise (random directions, whole-cycle drift)
    plus five Gaussian bulges that travel closed loops under the skin; they push the skin
    out along the normal and slide it along the tangent; spikes ride on the skin
  - micro-structure (zoom only): ridged high-frequency noise relief between the spikes,
    faded in by the level-of-detail controller

Level of detail. `lod=` builds nested 1->4 subdivisions of the same surface (level 1
everywhere, deeper levels only inside shrinking caps around a target direction). Each
level's new edges fade in by brightness and its new vertices morph from the coarse
position to the true surface position as the zoom passes that level, so nothing pops.
"""
import math

import bpy
import numpy as np

from .mesh import MeshBuilder

WEIGHTS = {}  # object name -> callable(edges) -> per-edge brightness weight (framework hook)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


# ------------------------------------------------------------------ geometry

FACES = [  # normal, e1, e2 (right-handed so faces wind outward)
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
]

# spike profile above the support loop: (radius as fraction of base half-width, height / H)
PROFILE = [(0.80, 0.16), (0.71, 0.36), (0.64, 0.56), (0.59, 0.73), (0.56, 0.84)]

# fixed rest orientation so no cube face, edge or corner lines up with the camera
def _axis_angle(axis, deg):
    k = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    a = math.radians(deg)
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def _rest():
    # turn the cube so the camera looks at the middle of a cube edge (two faces meet at a
    # gentle angle there) instead of a corner, then a small twist to break alignment
    a = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)
    c = np.array([1.0, 1.0, 1.0]) / math.sqrt(3)
    ax = np.cross(a, c)
    m1 = _axis_angle(ax, math.degrees(math.acos(np.dot(a, c))))
    return _axis_angle(c, 17.0) @ m1


REST = _rest()


def build_base(R=1.0, H=0.36, per_edge=4, patch=4, gap=2, margin=1):
    G = 2 * margin + per_edge * patch + (per_edge - 1) * gap
    mb = MeshBuilder()
    index = {}

    def grid_v(f, i, j):
        n, e1, e2 = (np.array(x, float) for x in FACES[f])
        a = math.tan(math.pi / 4 * (2 * i / G - 1))
        b = math.tan(math.pi / 4 * (2 * j / G - 1))
        p = n + a * e1 + b * e2
        p = p / np.linalg.norm(p) * R
        key = tuple(np.round(p, 9))
        if key not in index:
            index[key] = mb.v(p)
        return index[key]

    def in_patch(c):
        k = c - margin
        return 0 <= k < G - 2 * margin and k % (patch + gap) < patch

    spikes = []
    for f in range(6):
        V = [[grid_v(f, i, j) for j in range(G + 1)] for i in range(G + 1)]
        for i in range(G):
            for j in range(G):
                if not (in_patch(i) and in_patch(j)):
                    mb.quad(V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])
        for si in range(per_edge):
            for sj in range(per_edge):
                i0 = margin + si * (patch + gap)
                j0 = margin + sj * (patch + gap)
                ring = ([V[i0 + k][j0] for k in range(patch)] + [V[i0 + patch][j0 + k] for k in range(patch)]
                        + [V[i0 + patch - k][j0 + patch] for k in range(patch)]
                        + [V[i0][j0 + patch - k] for k in range(patch)])
                centre = np.array(mb.verts[V[i0 + patch // 2][j0 + patch // 2]])
                spikes.append((ring, centre / np.linalg.norm(centre)))
    axes = []
    for ring, n in spikes:
        axes.append(n)
        _grow_spike(mb, ring, n, R, H)
    P = np.array(mb.verts) @ REST.T
    F = np.array(mb.faces, dtype=np.int64)
    return P, F, np.array(axes) @ REST.T, G


def _grow_spike(mb, ring, n, R, H):
    P = np.array([mb.verts[i] for i in ring])
    base = n * R
    e1 = P[0] - base
    e1 -= n * np.dot(e1, n)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    rel = P - base
    tx, ty = rel @ e1, rel @ e2
    b = float(np.mean(np.hypot(tx, ty)))
    ang = np.arctan2(ty, tx)
    m = len(ring)
    sgn = 1.0 if np.sin(ang[1] - ang[0]) > 0 else -1.0
    uni = ang[0] + sgn * 2 * np.pi * np.arange(m) / m

    def at(r, z, a):
        return base + n * z + r * (np.cos(a) * e1 + np.sin(a) * e2)

    # support loop: mostly the square patch shape, pulled in and lifted a little
    cur = [mb.v(base + n * (0.05 * H) + 0.86 * ((1 - 0.3) * (tx[k] * e1 + ty[k] * e2)
                                                 + 0.3 * b * (np.cos(ang[k]) * e1 + np.sin(ang[k]) * e2)))
           for k in range(m)]
    mb.bridge(ring, cur)
    for rf, zf in PROFILE:
        nxt = [mb.v(at(rf * b, zf * H, uni[k])) for k in range(m)]
        mb.bridge(cur, nxt)
        cur = nxt
    # hemispherical tip, 16 -> 8 -> 4 -> one quad
    rt, z0 = PROFILE[-1][0] * b, PROFILE[-1][1] * H

    def cap(a, s):  # s: polar angle from the tip ring (0) toward the top (pi/2)
        return at(rt * math.cos(s), z0 + rt * math.sin(s), a)

    p = list(uni)
    s = 0.0
    steps = int(round(math.log2(m // 4)))
    for k in range(steps):
        s_in = (k + 1) / (steps + 0.6) * (math.pi / 2)
        cur, p = mb.reduce_2to1(cur, p, cap, (s + s_in) / 2, s_in)
        s = s_in
    mb.quad(*cur)


def orient_outward(P, F):
    """Flip faces whose normal points inward (the base mesh is star-shaped about 0)."""
    a, b, c, d = (P[F[:, k]] for k in range(4))
    nrm = np.cross(c - a, d - b)
    out = (nrm * (a + b + c + d)).sum(1) < 0
    F = F.copy()
    F[out] = F[out][:, ::-1]
    return F


# ------------------------------------------------------------------ motion

class Motion:
    """D(rest position, tau): the living surface. Deterministic for a seed."""

    def __init__(self, axes, R, H, seed=7, micro=0.0):
        rng = np.random.default_rng(seed)
        self.axes, self.R, self.H = axes, R, H
        # spike waves: (direction, cycles over the sphere, cycles per loop, phase, amplitude)
        self.waves = [(_unit(rng.normal(size=3)), f, m, rng.uniform(0, 2 * np.pi), a)
                      for f, m, a in ((1.1, 1, 0.55), (1.7, -2, 0.30), (2.6, 1, 0.20))]
        # crawl noise, two octaves of plane waves on the sphere with whole-cycle drift
        self.noise = []
        for f_lo, f_hi, count, amp, ms in ((1.2, 2.2, 7, 1.0, (1, -1, 2)), (3.5, 5.5, 9, 0.45, (-2, 1, 3, -1))):
            for _ in range(count):
                self.noise.append((_unit(rng.normal(size=3)), rng.uniform(f_lo, f_hi),
                                   int(rng.choice(ms)), rng.uniform(0, 2 * np.pi), amp / count ** 0.5))
        # bulges travelling closed loops under the skin
        self.blobs = []
        for q in (1, -1, 1, 1, -1):
            axis = _unit(rng.normal(size=3))
            p0 = _unit(np.cross(axis, _unit(rng.normal(size=3))) + 0.35 * axis)
            self.blobs.append((axis, p0, q, rng.uniform(0.2, 0.3), rng.uniform(0.7, 1.0)))
        # micro relief (zoom only): ridged high-frequency noise, slow whole-cycle drift
        self.micro = [(_unit(rng.normal(size=3)), rng.uniform(30, 46), int(rng.choice((1, -1))),
                       rng.uniform(0, 2 * np.pi)) for _ in range(14)]
        self.micro_amp = micro
        self.k = dict(breath=0.03, length=0.16, lean=0.22, noise=0.022, bulge=0.06, slide=0.012)

    def wave(self, u, tau):
        w = np.zeros(len(u))
        g = np.zeros_like(u)
        for d, f, m, ph, a in self.waves:
            arg = 2 * np.pi * (f * (u @ d) - m * tau) + ph
            w += a * np.sin(arg)
            g += (a * 2 * np.pi * f * np.cos(arg))[:, None] * (d - (u @ d)[:, None] * u)
        return w, g

    def crawl(self, u, tau):
        n = np.zeros(len(u))
        for d, f, m, ph, a in self.noise:
            n += a * np.sin(2 * np.pi * (f * (u @ d) + m * tau) + ph)
        bl = np.zeros(len(u))
        grad = np.zeros_like(u)
        for axis, p0, q, sig, amp in self.blobs:
            c = _rot(p0, axis, 2 * np.pi * q * tau)
            cos = u @ c
            e = amp * np.exp(-(1 - cos) / (sig * sig))
            bl += e
            grad += (e / (sig * sig))[:, None] * (c - cos[:, None] * u)  # d e / d u, tangential
        return n, bl, grad

    def micro_field(self, u, tau):
        """Small nubs: the peaks of a high-frequency looped noise (and its gradient)."""
        s = np.zeros(len(u))
        g = np.zeros_like(u)
        for d, f, m, ph in self.micro:
            arg = 2 * np.pi * (f * (u @ d)) + 2 * np.pi * m * tau + ph
            s += np.sin(arg)
            g += (np.cos(arg) * 2 * np.pi * f)[:, None] * (d - (u @ d)[:, None] * u)
        k = 1.0 / math.sqrt(len(self.micro) / 2)
        s, g = s * k, g * k
        lo, hi = 0.35, 1.6
        x = np.clip((s - lo) / (hi - lo), 0, 1)
        nub = x * x * (3 - 2 * x)
        dn = (6 * x * (1 - x) / (hi - lo))[:, None] * g
        return nub, dn

    def apply(self, P0, tau, micro_w=None):
        R, H = self.R, self.H
        r0 = np.linalg.norm(P0, axis=1)
        u = P0 / r0[:, None]
        h = np.clip((r0 - R) / H, 0, None)
        j = np.argmax(u @ self.axes.T, axis=1)
        nj = self.axes[j]
        spike = smoothstep(0.0, 0.12, h)
        kk = self.k
        breath = 1 + kk['breath'] * (np.sin(2 * np.pi * tau) + 0.33 * np.sin(4 * np.pi * tau + 1.3))
        # spike length and lean from the travelling waves, sampled at each spike's axis
        w, g = self.wave(nj, tau)
        rel = P0 - nj * R
        ax = (rel * nj).sum(1)
        rel = rel + nj * (ax * kk['length'] * w * spike)[:, None]
        gl = np.linalg.norm(g, axis=1) + 1e-9
        k = np.cross(nj, g / gl[:, None])
        beta = kk['lean'] * np.tanh(gl / 4.0) * smoothstep(0.0, 0.45, h)
        rel = _rot_rows(rel, k, beta)
        # crawl: sampled at the skin point under each vertex (spikes ride along)
        uc = u  # the field is smooth on the sphere; each vertex samples it at its own direction
        n, bl, grad = self.crawl(uc, tau)
        normal_disp = R * (kk['noise'] * n + kk['bulge'] * bl)
        tang = R * kk['slide'] * grad
        if micro_w is not None and self.micro_amp:
            wm = micro_w * (1 - spike)
            nub, dn = self.micro_field(u, tau)
            normal_disp = normal_disp + R * self.micro_amp * wm * nub
        base = nj * R
        P = (base + rel) * breath
        return P + uc * normal_disp[:, None] + tang


def _rot(v, axis, ang):
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * np.dot(axis, v) * (1 - math.cos(ang))


def _rot_rows(v, k, ang):
    c, s = np.cos(ang)[:, None], np.sin(ang)[:, None]
    return v * c + np.cross(k, v) * s + k * (k * v).sum(1, keepdims=True) * (1 - c)


# ------------------------------------------------------------------ level of detail

class LOD:
    """Nested subdivision around `target` (unit rest direction).

    levels: list of dicts {zoom: (z_start, z_full), theta: (deg_full, deg_zero)}; level 1 is
    built everywhere, deeper levels only inside theta_zero + margin.
    """

    def __init__(self, P, F, R, target, levels, micro_zoom=None):
        self.target = target / np.linalg.norm(target)
        self.levels = levels
        self.micro_zoom = micro_zoom
        P = [p for p in P]
        level_of = [0] * len(P)
        parents = [()] * len(P)
        edge_org = {}

        def ekey(a, b):
            return (a, b) if a < b else (b, a)

        for f in F:
            for k in range(4):
                edge_org[ekey(f[k], f[(k + 1) % 4])] = 0
        leaves = []
        cur = [tuple(f) for f in F]
        self.level_faces = [np.array(cur)]
        for L, spec in enumerate(levels, start=1):
            lim = math.radians(spec["theta"][1]) + spec.get("margin", 0.12)
            mids = {}
            nxt, keep = [], []
            for f in cur:
                c = np.mean([P[i] for i in f], axis=0)
                ang = math.acos(max(-1, min(1, np.dot(c / np.linalg.norm(c), self.target))))
                if L > 1 and ang > lim:
                    keep.append(f)
                    continue

                def mid(a, b):
                    k = ekey(a, b)
                    if k not in mids:
                        q = (P[a] + P[b]) / 2
                        if _on_skin(P[a], R) and _on_skin(P[b], R):
                            q = q / np.linalg.norm(q) * R
                        P.append(q)
                        level_of.append(L)
                        parents.append((a, b))
                        mids[k] = len(P) - 1
                        org = edge_org[k]
                        edge_org[ekey(a, mids[k])] = org
                        edge_org[ekey(mids[k], b)] = org
                    return mids[k]

                a, b, c4, d = f
                mab, mbc, mcd, mda = mid(a, b), mid(b, c4), mid(c4, d), mid(d, a)
                q = np.mean([P[i] for i in f], axis=0)
                if all(_on_skin(P[i], R) for i in f):
                    q = q / np.linalg.norm(q) * R
                P.append(q)
                level_of.append(L)
                parents.append((a, b, c4, d))
                cc = len(P) - 1
                for x in (mab, mbc, mcd, mda):
                    edge_org[ekey(x, cc)] = L
                nxt += [(a, mab, cc, mda), (mab, b, mbc, cc), (cc, mbc, c4, mcd), (mda, cc, mcd, d)]
            leaves += keep
            cur = nxt
            self.level_faces.append(np.array(nxt))
        leaves += cur
        self.P0 = np.array(P)
        self.F = np.array(leaves, dtype=np.int64)
        self.level_of = np.array(level_of)
        self.parents = parents
        self.edge_org = edge_org
        self.L = len(levels)
        # per level: new vertex ids and padded parent arrays for vectorised morphing
        self.morph = []
        for L in range(1, self.L + 1):
            ids = np.nonzero(self.level_of == L)[0]
            par = np.full((len(ids), 4), -1, np.int64)
            for r, v in enumerate(ids):
                pp = parents[v]
                par[r, :len(pp)] = pp
            self.morph.append((ids, par))
        self.u = self.P0 / np.linalg.norm(self.P0, axis=1)[:, None]
        self.ang = np.degrees(np.arccos(np.clip(self.u @ self.target, -1, 1)))

    def alpha(self, L, ang_deg, zoom):
        if L == 0:
            return np.ones_like(ang_deg)
        spec = self.levels[L - 1]
        z0, z1 = spec["zoom"]
        zf = smoothstep(math.log(z0), math.log(z1), math.log(max(zoom, 1e-6)))
        th0, th1 = spec["theta"]
        sp = 1 - smoothstep(th0, th1, ang_deg) if L > 1 else np.ones_like(ang_deg)
        return zf * sp

    def micro_weight(self, zoom):
        if not self.micro_zoom:
            return np.zeros(len(self.P0))
        z0, z1 = self.micro_zoom
        zf = smoothstep(math.log(z0), math.log(z1), math.log(max(zoom, 1e-6)))
        th0, th1 = self.levels[-1]["theta"]
        return zf * (1 - smoothstep(th0, th1, self.ang))

    def positions(self, motion, tau, zoom):
        true = motion.apply(self.P0, tau, micro_w=self.micro_weight(zoom))
        disp = true.copy()
        for L, (ids, par) in enumerate(self.morph, start=1):
            if not len(ids):
                continue
            cnt = (par >= 0).sum(1)
            acc = np.zeros((len(ids), 3))
            for k in range(4):
                ok = par[:, k] >= 0
                acc[ok] += disp[par[ok, k]]
            coarse = acc / cnt[:, None]
            a = self.alpha(L, self.ang[ids], zoom)[:, None]
            disp[ids] = coarse + (true[ids] - coarse) * a
        return disp


def gap_near(P, axes, R, near, within=30.0):
    """Skin point near `near` that is farthest from every spike: a crossing of the streets
    between spikes, the natural place to dive into."""
    near = near / np.linalg.norm(near)
    u = P / np.linalg.norm(P, axis=1)[:, None]
    skin = np.abs(np.linalg.norm(P, axis=1) - R) < 1e-6
    ok = skin & (u @ near > math.cos(math.radians(within)))
    clear = np.arccos(np.clip(u @ axes.T, -1, 1)).min(1)
    score = clear - 0.25 * np.arccos(np.clip(u @ near, -1, 1))
    score[~ok] = -1e9
    return u[int(np.argmax(score))]


def _on_skin(p, R):
    return abs(np.linalg.norm(p) - R) < 1e-6 * max(R, 1)


# ------------------------------------------------------------------ object

class SpikeBall:
    def __init__(self, name, R=1.0, H=0.27, per_edge=4, seed=7, lod=None, target=None,
                 micro_zoom=None, micro=0.007):
        P, F, axes, self.G = build_base(R, H, per_edge)
        F = orient_outward(P, F)
        if target is not None and len(target) == 2 and target[0] == "gap_near":
            target = gap_near(P, axes, R, np.asarray(target[1], float))
        self.target = None if target is None else np.asarray(target, float)
        self.base_faces = F
        self.n_spikes = len(axes)
        self.motion = Motion(axes, R, H, seed, micro=micro if lod else 0.0)
        self.R, self.H = R, H
        self.zoom = 1.0
        if lod:
            self.lod = LOD(P, F, R, np.asarray(target, float), lod, micro_zoom)
            self.P0, F = self.lod.P0, self.lod.F
        else:
            self.lod, self.P0 = None, P
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.P0.tolist(), [], F.tolist())
        me.update()
        self.obj = bpy.data.objects.new(name, me)
        self.faces = F
        if self.lod:
            e = np.empty(len(me.edges) * 2, np.int64)
            me.edges.foreach_get("vertices", e)
            e = e.reshape(-1, 2)
            self.edge_org = np.array([self.lod.edge_org.get((min(a, b), max(a, b)), 0) for a, b in e])
            WEIGHTS[name] = self.edge_weights

    def update(self, tau, zoom=1.0):
        self.zoom = zoom
        if self.lod:
            co = self.lod.positions(self.motion, tau, zoom)
        else:
            co = self.motion.apply(self.P0, tau)
        self.obj.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.obj.data.update()

    def edge_weights(self, E):
        """Brightness weight per mesh edge: alpha of the level that introduced its line."""
        u = self.lod.u
        mid = _unit(u[E[:, 0]] + u[E[:, 1]])
        ang = np.degrees(np.arccos(np.clip(mid @ self.lod.target, -1, 1)))
        w = np.ones(len(E))
        for L in range(1, self.lod.L + 1):
            sel = self.edge_org == L
            if sel.any():
                w[sel] = self.lod.alpha(L, ang[sel], self.zoom)
        return w

    def focus(self, tau):
        """Current (moving) surface point under the target direction, in object space."""
        p = self.motion.apply((self.lod.target * self.R)[None], tau)[0]
        return p
