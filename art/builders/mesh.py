"""Mesh assembly helpers shared by every builder.

Builders describe geometry as vertices plus quads (n-gons only where a form needs one) and
turn it into a Blender object at the end. Normals are recalculated outward, because the line
renderer uses face normals to decide which edges face away from the camera.
"""
import math

import bmesh
import bpy


class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []

    def v(self, co):
        self.verts.append((float(co[0]), float(co[1]), float(co[2])))
        return len(self.verts) - 1

    def quad(self, a, b, c, d):
        self.faces.append((a, b, c, d))

    def face(self, idx):
        self.faces.append(tuple(idx))

    def ring(self, pos, params, s):
        """One vertex per angle parameter at radial parameter s."""
        return [self.v(pos(p, s)) for p in params]

    def bridge(self, a, b, closed=True):
        """Quads between two rings of equal length."""
        n = len(a)
        assert n == len(b), (n, len(b))
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            self.quad(a[i], a[j], b[j], b[i])

    def bridge_loops(self, a, b, loops, closed=True):
        """Bridge two rings with `loops` evenly spaced straight intermediate rings."""
        prev = a
        for k in range(1, loops + 1):
            f = k / (loops + 1)
            cur = []
            for i in range(len(a)):
                pa, pb = self.verts[a[i]], self.verts[b[i]]
                cur.append(self.v([pa[q] + (pb[q] - pa[q]) * f for q in range(3)]))
            self.bridge(prev, cur, closed)
            prev = cur
        self.bridge(prev, b, closed)

    def reduce_2to1(self, outer, outer_params, pos, s_mid, s_in):
        """Clean 2:1 quad reduction band (4 outer segments -> 2 inner), no triangles.

        a0--a1--a2--a3--a4
        |   |   |   |   |
        |   m1--m2--m3  |
        |  /    |     \\ |
        c0------c2------c4

        `pos(param, s)` maps a ring parameter (angle) and a radial parameter to 3D.
        Returns (inner ring, inner params).
        """
        n = len(outer)
        assert n % 4 == 0, n
        inner, inner_p = [], []
        for u in range(n // 4):
            k = 4 * u
            p0, p2 = outer_params[k], outer_params[k + 2]
            inner_p += [p0, p2]
            inner += [self.v(pos(p0, s_in)), self.v(pos(p2, s_in))]
        m = len(inner)
        for u in range(n // 4):
            k = 4 * u
            a = [outer[(k + i) % n] for i in range(5)]
            m1 = self.v(pos(outer_params[k + 1], s_mid))
            m2 = self.v(pos(outer_params[k + 2], s_mid))
            m3 = self.v(pos(outer_params[k + 3], s_mid))
            c0, c2, c4 = inner[2 * u], inner[2 * u + 1], inner[(2 * u + 2) % m]
            self.quad(a[0], a[1], m1, c0)
            self.quad(a[1], a[2], m2, m1)
            self.quad(a[2], a[3], m3, m2)
            self.quad(a[3], a[4], c4, m3)
            self.quad(c0, m1, m2, c2)
            self.quad(c2, m2, m3, c4)
        return inner, inner_p

    def reduce_3to1(self, outer, outer_params, pos, s_mid, s_in):
        """Clean 3:1 quad reduction band (3 outer segments -> 1 inner), no triangles.

        a0--a1--a2--a3
        |   |   |   |
        |   m1--m2  |
        |  /      \\ |
        c0----------c3
        """
        n = len(outer)
        assert n % 3 == 0, n
        inner = [self.v(pos(outer_params[3 * u], s_in)) for u in range(n // 3)]
        m = len(inner)
        for u in range(n // 3):
            k = 3 * u
            a = [outer[(k + i) % n] for i in range(4)]
            m1 = self.v(pos(outer_params[k + 1], s_mid))
            m2 = self.v(pos(outer_params[k + 2], s_mid))
            c0, c3 = inner[u], inner[(u + 1) % m]
            self.quad(a[0], a[1], m1, c0)
            self.quad(a[1], a[2], m2, m1)
            self.quad(a[2], a[3], c3, m2)
            self.quad(c0, m1, m2, c3)
        return inner, outer_params[0::3]

    def to_object(self, name, recalc_normals=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.validate(clean_customdata=False)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        if recalc_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()
        return bpy.data.objects.new(name, me)


def plan_annulus(s_out, s_in, cols, spacing_at, min_cols=4, target=None, aspect=1.0, reduce=True):
    """Plan rings inward from s_out to s_in on a polar surface.

    `spacing_at(s, cols)` is the distance between neighbouring columns at radius s.
    `target` is the wanted edge spacing. Columns halve through a 2:1 reduction band when
    their spacing falls below 0.75 x target; rings are spaced like the columns (square
    quads, times `aspect`) but never closer than 0.8 x target. Returns ops ("ring", s) or
    ("reduce", s_mid, s_in), rescaled so the last ring lands exactly on s_in.
    """
    target = target or spacing_at(s_out, cols)
    ops = []
    s = s_out
    c = cols
    while True:
        sp = spacing_at(s, c)
        if reduce and c % 4 == 0 and c // 2 >= min_cols and sp < 0.75 * target:
            band = max(1.6 * sp, 1.3 * target) * aspect
            if s - band < s_in - 0.2 * band:
                break
            ops.append(["reduce", s - band * 0.5, s - band])
            s -= band
            c //= 2
            continue
        step = max(sp, 0.8 * target) * aspect
        if s - step < s_in + 0.45 * step:
            break
        s -= step
        ops.append(["ring", s])
    if not ops:
        ops = [["ring", s_in]]
    else:
        last = ops[-1][-1]
        k = (s_out - s_in) / (s_out - last)
        for op in ops:
            for i in range(1, len(op)):
                op[i] = s_out - (s_out - op[i]) * k
    return [tuple(op) for op in ops], c


def build_annulus(mb, outer, params, pos, s_out, s_in, spacing_at, min_cols=4, aspect=1.0,
                  reduce=True, target=None):
    """Fill a polar annulus from an existing outer ring inward. Returns (inner ring, params)."""
    ops, _ = plan_annulus(s_out, s_in, len(outer), spacing_at, min_cols=min_cols,
                          target=target, aspect=aspect, reduce=reduce)
    ring, p = outer, params
    for op in ops:
        if op[0] == "ring":
            nxt = [mb.v(pos(a, op[1])) for a in p]
            mb.bridge(ring, nxt)
            ring = nxt
        else:
            ring, p = mb.reduce_2to1(ring, p, pos, op[1], op[2])
    return ring, p


def cap_disc(mb, outer, params, pos, s_out):
    """Close a polar ring to the pole with 2:1 reductions ending in a single quad."""
    n = len(outer)
    assert n >= 4 and (n & (n - 1)) == 0, "cap needs a power-of-two column count"
    steps = int(round(math.log2(n // 4)))
    ring, p, s = outer, params, s_out
    if steps:
        band = s_out / (steps + 0.7)
        for _ in range(steps):
            ring, p = mb.reduce_2to1(ring, p, pos, s - band * 0.5, s - band)
            s -= band
    mb.quad(*ring)
