"""Lathe / revolve: spin a 2D profile (r, z) around local Z into a clean quad surface.

Column counts are powers of two chosen from the local circumference so quads stay near
square; where the profile moves toward the axis, columns halve through 2:1 reduction bands
(no triangles, no spokes bunching at the hub). Ends on the axis close with a quad.
"""
import math

from .mesh import MeshBuilder


def _polyline(profile, target):
    """Subdivide a profile so no segment is longer than target. Keeps every corner."""
    out = [profile[0]]
    for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
        n = max(1, math.ceil(math.hypot(r1 - r0, z1 - z0) / target - 1e-9))
        for k in range(1, n + 1):
            out.append((r0 + (r1 - r0) * k / n, z0 + (z1 - z0) * k / n))
    return out


def _cols_for(r, target, max_cols, min_cols=4):
    want = 2 * math.pi * r / target
    c = max_cols
    while c > min_cols and c / 2 >= want * 1.0 and c > want * 1.45:
        c //= 2
    return c


def revolve(name, profile, cols=64, target=None, closed=False, pos_fn=None):
    """Revolve `profile` [(r, z), ...]. Points with r == 0 at either end become poles.

    cols: maximum column count (power of two). target: segment length along the profile
    and the circumference (defaults to the column spacing at the largest radius).
    closed: join the last profile point back to the first (for tori and rings).
    """
    rmax = max(r for r, _ in profile)
    target = target or 2 * math.pi * rmax / cols
    pts = _polyline(profile + ([profile[0]] if closed else []), target)
    if closed:
        pts = pts[:-1]
    mb = MeshBuilder()
    n = len(pts)

    def pos(a, i):
        """Angle a, fractional profile index i."""
        i0 = min(int(math.floor(i)), n - 1)
        f = i - i0
        i1 = (i0 + 1) % n if closed else min(i0 + 1, n - 1)
        r = pts[i0][0] + (pts[i1][0] - pts[i0][0]) * f
        z = pts[i0][1] + (pts[i1][1] - pts[i0][1]) * f
        return (r * math.cos(a), r * math.sin(a), z)

    pole_start = not closed and pts[0][0] < 1e-9
    pole_end = not closed and pts[-1][0] < 1e-9
    first = 1 if pole_start else 0
    last = n - 2 if pole_end else n - 1
    colc = [_cols_for(pts[i][0], target, cols) for i in range(n)]
    if closed:
        colc = [min(colc)] * n  # a closed profile keeps one column count
    else:
        # at most one 2:1 band per profile segment, so bands never get squeezed thin
        for _ in range(2):
            for i in range(1, n):
                colc[i] = max(colc[i], colc[i - 1] // 2)
            for i in range(n - 2, -1, -1):
                colc[i] = max(colc[i], colc[i + 1] // 2)
    rings = {}

    def params(c):
        return [2 * math.pi * k / c for k in range(c)]

    i = first
    rings[i] = (mb.ring(pos, params(colc[i]), i), params(colc[i]))
    while i < last:
        j = i + 1
        ring, p = rings[i]
        cj = colc[j]
        if cj == len(ring):
            rings[j] = (mb.ring(pos, params(cj), j), params(cj))
            mb.bridge(ring, rings[j][0])
        elif cj < len(ring):
            # reduce toward the axis, one halving per band (bands share the segment)
            steps = int(round(math.log2(len(ring) / cj)))
            cur, cp = ring, p
            for k in range(steps):
                s_in = i + (k + 1) / steps
                cur, cp = mb.reduce_2to1(cur, cp, pos, i + (k + 0.5) / steps, s_in)
            rings[j] = (cur, cp)
        else:
            # expand away from the axis: build the new outer ring, reduce back onto ours
            steps = int(round(math.log2(cj / len(ring))))
            cur, cp = ring, p
            for k in range(steps):
                s_out = i + (k + 1) / steps
                op = params(len(cur) * 2)
                outer = mb.ring(pos, op, s_out)
                _reduce_onto(mb, outer, op, cur, pos, i + (k + 0.5) / steps)
                cur, cp = outer, op
            rings[j] = (cur, cp)
        i = j
    if closed:
        mb.bridge(rings[last][0], rings[first][0])
    for end, pole in ((first, pole_start), (last, pole_end)):
        if not pole:
            continue
        ring, p = rings[end]
        tip = 0 if end == first else n - 1
        _cap(mb, ring, p, pos, end, tip)
    return mb.to_object(name)


def _reduce_onto(mb, outer, op, inner, pos, s_mid):
    """2:1 band between a new outer ring and an existing inner ring (outer = 2x inner)."""
    n = len(outer)
    m = len(inner)
    for u in range(n // 4):
        k = 4 * u
        a = [outer[(k + q) % n] for q in range(5)]
        m1 = mb.v(pos(op[k + 1], s_mid))
        m2 = mb.v(pos(op[k + 2], s_mid))
        m3 = mb.v(pos(op[k + 3], s_mid))
        c0, c2, c4 = inner[2 * u], inner[2 * u + 1], inner[(2 * u + 2) % m]
        mb.quad(a[0], a[1], m1, c0)
        mb.quad(a[1], a[2], m2, m1)
        mb.quad(a[2], a[3], m3, m2)
        mb.quad(a[3], a[4], c4, m3)
        mb.quad(c0, m1, m2, c2)
        mb.quad(c2, m2, m3, c4)


def _cap(mb, ring, p, pos, s_ring, s_pole):
    """Close a ring to the pole: halve to 4 columns, then one quad."""
    c = len(ring)
    steps = int(round(math.log2(c // 4)))
    cur, cp = ring, p
    span = s_pole - s_ring
    # the last band stops short of the pole so the closing quad has room
    for k in range(steps):
        f_in = (k + 1) / (steps + 0.6)
        f_mid = (k + 0.5) / (steps + 0.6)
        cur, cp = mb.reduce_2to1(cur, cp, pos, s_ring + span * f_mid, s_ring + span * f_in)
    mb.quad(*cur)


def torus(name, R, r, cols=64, sides=None):
    """Torus about local Z (major radius R, tube radius r)."""
    sides = sides or max(8, int(round(cols * r / R / 4)) * 4)
    prof = [(R + r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides))
            for k in range(sides)]
    return revolve(name, prof, cols=cols, target=2 * math.pi * r / sides * 1.001, closed=True)
