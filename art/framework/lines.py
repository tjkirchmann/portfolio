"""Line rendering: every mesh edge becomes a screen-facing ribbon with round joins.

Under the orthographic camera a ribbon of constant world width has constant screen width,
so line width never depends on depth. Each frame:

- edges whose adjacent faces all point away from the camera are "back" edges and are drawn
  at BACK of the brightness of front edges (re-evaluated every frame);
- brightness also fades with distance along the view axis across the subject's whole-loop
  depth range (near 1.0, far FAR);
- front-facing edges hidden behind nearer surfaces (from a per-frame depth pass of the
  real meshes) are drawn at OCC, so the form reads as a solid while every edge stays visible;
- every ribbon and join disc is moved along the view axis to a depth set by its brightness
  (brighter is nearer). Orthographic projection makes this invisible in screen position,
  but it means that where lines cross, the brighter one wins: a max composite, so dim back
  lines never cut notches into bright front lines and overlapping joins never double up.

Brightness values are display-space fractions of the line colour; the emission is the
linear equivalent, so anti-aliasing happens in linear light (steady under motion).
"""
import bpy
import numpy as np

from . import camera as cammod

COLOR_DISPLAY = 0.92  # line colour, display value (neutral grey #ebebeb)
BACK = 0.28           # back-edge brightness relative to front (AC-14: 25-40%)
FAR = 0.3             # brightness of the farthest point relative to the nearest
OCC = 0.45            # front-facing edges hidden behind nearer surfaces
JOIN_SEGS = 12


def srgb_to_linear(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(np.asarray(x, dtype=np.float64), 0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


class _Topo:
    def __init__(self, obj):
        me = obj.data
        self.obj = obj
        self.nv = len(me.vertices)
        e = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", e)
        self.edges = e.reshape(-1, 2)
        nl = len(me.loops)
        lv = np.empty(nl, np.int64)
        le = np.empty(nl, np.int64)
        me.loops.foreach_get("vertex_index", lv)
        me.loops.foreach_get("edge_index", le)
        npoly = len(me.polygons)
        ls = np.empty(npoly, np.int64)
        lt = np.empty(npoly, np.int64)
        me.polygons.foreach_get("loop_start", ls)
        me.polygons.foreach_get("loop_total", lt)
        poly_of_loop = np.repeat(np.arange(npoly), lt)
        nxt = np.arange(nl) + 1
        last = ls + lt - 1
        nxt[last] = ls
        self.lv, self.le, self.ls, self.poly_of_loop, self.nxt = lv, le, ls, poly_of_loop, nxt
        self.has_face = np.bincount(le, minlength=len(self.edges)) > 0

    def world_verts(self):
        me = self.obj.data
        co = np.empty(self.nv * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(self.obj.matrix_world, dtype=np.float64)
        return co @ m[:3, :3].T + m[:3, 3]

    def facing(self, P, toward):
        """Per-edge: True if any adjacent face points toward the camera (or edge is wire)."""
        lp = P[self.lv]
        cr = np.cross(lp, lp[self.nxt])
        n = np.add.reduceat(cr, self.ls, axis=0)
        f = (n @ toward) > 0
        front = np.zeros(len(self.edges), bool)
        np.logical_or.at(front, self.le, f[self.poly_of_loop])
        return front | ~self.has_face


def make_material():
    mat = bpy.data.materials.new("line")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = "lum"
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(at.outputs["Fac"], em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


class LineRenderer:
    def __init__(self, scene, cam, objects, render_res, line_px):
        self.scene = scene
        self.X, self.Y, self.Z = (np.array(v, dtype=np.float64) for v in cammod.basis(cam))
        self.topos = [_Topo(o) for o in objects]
        self.hw = (line_px / 2) * cammod.ORTHO_SCALE / render_res
        self.mat = make_material()
        self.obj = bpy.data.objects.new("lines", bpy.data.meshes.new("lines"))
        scene.collection.objects.link(self.obj)
        self.depth_range = (-1.0, 1.0)
        self.back = BACK
        self.far = FAR
        self.occ = OCC
        self.depth_max = None
        ang = np.linspace(0, 2 * np.pi, JOIN_SEGS, endpoint=False)
        self.circle = np.stack([np.cos(ang), np.sin(ang)], 1)

    def gather(self):
        """World vertices, global edges and per-edge front flags for the current pose."""
        Ps, Es, Fs = [], [], []
        off = 0
        toward = self.Z
        for t in self.topos:
            P = t.world_verts()
            Ps.append(P)
            Es.append(t.edges + off)
            Fs.append(t.facing(P, toward))
            off += len(P)
        return np.concatenate(Ps), np.concatenate(Es), np.concatenate(Fs)

    def set_depth_map(self, D):
        """D: (R, R) distance from the camera of the nearest surface, top row first; 0 = none."""
        D = np.where(D <= 0, np.inf, D)
        pad = np.pad(D, 1, mode="edge")
        R = D.shape[0]
        m = np.full_like(D, -np.inf)
        for dy in range(3):
            for dx in range(3):
                m = np.maximum(m, pad[dy:dy + R, dx:dx + R])
        self.depth_max = m  # farthest surface in each 3x3 neighbourhood
        self.eps = 1.5 * cammod.ORTHO_SCALE / R

    def occluded(self, Q):
        if self.depth_max is None:
            return np.zeros(len(Q), bool)
        R = self.depth_max.shape[0]
        ix = np.floor((Q @ self.X / cammod.ORTHO_SCALE + 0.5) * R).astype(int)
        iy = np.floor((0.5 - Q @ self.Y / cammod.ORTHO_SCALE) * R).astype(int)
        inside = (ix >= 0) & (ix < R) & (iy >= 0) & (iy < R)
        out = np.zeros(len(Q), bool)
        dist = cammod.DISTANCE - Q @ self.Z
        out[inside] = self.depth_max[iy[inside], ix[inside]] < dist[inside] - self.eps
        return out

    def fade(self, Q):
        lo, hi = self.depth_range
        u = np.clip((Q @ self.Z - lo) / max(hi - lo, 1e-9), 0, 1)
        return self.far + (1 - self.far) * u

    def brightness(self, P, E, front, back_dim=True):
        """Per-edge end brightness from facing and depth fade (no occlusion)."""
        f = self.fade(P)
        k = np.where(front, 1.0, self.back if back_dim else 1.0)
        return f[E[:, 0]] * k, f[E[:, 1]] * k

    def segments(self, back_dim=True):
        """Half-edge segments (a, b, brightness a, brightness b) with facing, depth and
        occlusion applied. Occlusion is sampled at both ends and the middle of each edge."""
        P, E, front = self.gather()
        k = np.where(front, 1.0, self.back if back_dim else 1.0)
        M = (P[E[:, 0]] + P[E[:, 1]]) / 2
        if back_dim:
            ov = np.where(self.occluded(P), self.occ, 1.0)
            om = np.where(self.occluded(M), self.occ, 1.0)
            # back edges are already at BACK; occlusion only dims front-facing edges
            k0 = np.where(front, ov[E[:, 0]], k)
            k1 = np.where(front, ov[E[:, 1]], k)
            km = np.where(front, om, k)
        else:
            k0 = k1 = km = k
        fv, fm = self.fade(P), self.fade(M)
        b0, b1, bm = fv[E[:, 0]] * k0, fv[E[:, 1]] * k1, fm * km
        A = np.concatenate([P[E[:, 0]], M])
        B = np.concatenate([M, P[E[:, 1]]])
        bA = np.concatenate([b0, bm])
        bB = np.concatenate([bm, b1])
        # join discs sit on real vertices only
        vb = np.full(len(P), -1.0)
        np.maximum.at(vb, E[:, 0], b0)
        np.maximum.at(vb, E[:, 1], b1)
        return P, E, front, A, B, bA, bB, vb

    def update(self, back_dim=True):
        P, E, front, A, B, bA, bB, vb = self.segments(back_dim)
        x0, y0, x1, y1 = A @ self.X, A @ self.Y, B @ self.X, B @ self.Y
        sx, sy = P @ self.X, P @ self.Y
        dx, dy = x1 - x0, y1 - y0
        L = np.hypot(dx, dy)
        ok = L > 1e-9
        x0, y0, x1, y1, dx, dy, L, b0r, b1r = (a[ok] for a in (x0, y0, x1, y1, dx, dy, L, bA, bB))
        nx, ny = -dy / L * self.hw, dx / L * self.hw
        rx = np.stack([x0 + nx, x0 - nx, x1 - nx, x1 + nx], 1).ravel()
        ry = np.stack([y0 + ny, y0 - ny, y1 - ny, y1 + ny], 1).ravel()
        rb = np.stack([b0r, b0r, b1r, b1r], 1).ravel()
        used = np.nonzero(vb >= 0)[0]
        cx = (sx[used][:, None] + self.circle[None, :, 0] * self.hw).ravel()
        cy = (sy[used][:, None] + self.circle[None, :, 1] * self.hw).ravel()
        cb = np.repeat(vb[used], JOIN_SEGS)
        X = np.concatenate([rx, cx])
        Y = np.concatenate([ry, cy])
        Bv = np.concatenate([rb, cb])
        co = (X[:, None] * self.X + Y[:, None] * self.Y + (5.0 + 10.0 * Bv)[:, None] * self.Z)
        nr, nd = len(rx) // 4, len(used)
        starts = np.concatenate([np.arange(nr) * 4, nr * 4 + np.arange(nd) * JOIN_SEGS])
        loops = np.arange(len(X))
        me = bpy.data.meshes.new("lines")
        me.vertices.add(len(X))
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops.astype(np.int32))
        me.polygons.add(len(starts))
        me.polygons.foreach_set("loop_start", starts.astype(np.int32))
        me.update(calc_edges=True)
        lum = srgb_to_linear(np.clip(Bv, 0, 1) * COLOR_DISPLAY).astype(np.float32)
        a = me.attributes.new("lum", "FLOAT", "POINT")
        a.data.foreach_set("value", lum)
        me.materials.append(self.mat)
        old = self.obj.data
        self.obj.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        return dict(edges=int(len(E)), front=int(front.sum()), ribbons=int(nr), joins=int(nd),
                    occluded=float((bA < self.fade(A) * 0.999).mean()))
