"""Boxes and lattices.

`box` is a subdivided quad box (even grid on all six faces, shared edges, no triangles).
`lattice` is an n x m x k cubic lattice of square-section beams built as one quad surface per
beam; nodes are left as plain overlaps, which reads cleanly as wireframe because every beam
edge is straight and evenly divided.
"""
import math

from .mesh import MeshBuilder


def box(name, size=(2.0, 2.0, 2.0), target=0.25):
    """Quad box centred on the origin with faces divided to ~target spacing."""
    sx, sy, sz = size
    n = [max(1, round(s / target)) for s in size]
    mb = MeshBuilder()
    verts = {}

    def vid(i, j, k):
        key = (i, j, k)
        if key not in verts:
            verts[key] = mb.v((sx * (i / n[0] - 0.5), sy * (j / n[1] - 0.5), sz * (k / n[2] - 0.5)))
        return verts[key]

    for axis in range(3):
        a, b = [q for q in range(3) if q != axis]
        for side in (0, n[axis]):
            for u in range(n[a]):
                for w in range(n[b]):
                    def idx(du, dw):
                        c = [0, 0, 0]
                        c[axis], c[a], c[b] = side, u + du, w + dw
                        return vid(*c)
                    mb.quad(idx(0, 0), idx(1, 0), idx(1, 1), idx(0, 1))
    return mb.to_object(name)


def beam(mb, p0, p1, w, target):
    """Square-section beam from p0 to p1 (axis-aligned), sides divided to ~target."""
    d = [p1[i] - p0[i] for i in range(3)]
    L = math.sqrt(sum(x * x for x in d))
    ax = max(range(3), key=lambda i: abs(d[i]))
    o = [i for i in range(3) if i != ax]
    segs = max(1, round(L / target))
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    rings = []
    for s in range(segs + 1):
        f = s / segs
        ring = []
        for cu, cv in corners:
            c = [p0[i] + d[i] * f for i in range(3)]
            c[o[0]] += cu * w / 2
            c[o[1]] += cv * w / 2
            ring.append(mb.v(c))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        mb.bridge(r0, r1)
    mb.quad(*rings[0][::-1])
    mb.quad(*rings[-1])


def lattice(name, counts=(3, 3, 3), cell=1.0, width=0.08, target=0.25):
    """Cubic lattice of beams, centred on the origin."""
    mb = MeshBuilder()
    nx, ny, nz = counts
    off = [cell * c / 2 for c in counts]
    for i in range(nx + 1):
        for j in range(ny + 1):
            for k in range(nz + 1):
                p = (i * cell - off[0], j * cell - off[1], k * cell - off[2])
                for ax, lim in ((0, nx), (1, ny), (2, nz)):
                    idx = (i, j, k)[ax]
                    if idx < lim:
                        q = list(p)
                        q[ax] += cell
                        beam(mb, p, q, width, target)
    return mb.to_object(name)
