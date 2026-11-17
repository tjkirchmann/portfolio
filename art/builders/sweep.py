"""Extrude along a path: sweep a circle (or any closed profile) along a closed 3D curve.

Rings are spaced evenly by arc length and oriented with parallel-transport frames; the
leftover twist is spread along the loop so the tube closes without a seam. `Sweep.update`
can slide the rings along the path and roll them around it, which makes the surface flow
along itself. Shifts by whole rings / whole sides reproduce the start exactly, so such
motions loop seamlessly.
"""
import math

import numpy as np

from .mesh import MeshBuilder


def _resample(curve, n_dense=4000):
    """curve(u) for u in [0,1) -> dense points with cumulative arc length."""
    u = np.arange(n_dense) / n_dense
    P = np.array([curve(x) for x in u], dtype=np.float64)
    seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return P, cum


class Sweep:
    def __init__(self, name, curve, radius, rings=None, sides=12, target=None):
        P, cum = _resample(curve)
        self.length = cum[-1]
        self.radius = radius
        if rings is None:
            seg = target or 2 * math.pi * radius / sides
            rings = int(round(self.length / seg))
        self.rings, self.sides = rings, sides
        self._P, self._cum = P, cum
        # parallel transport frames on the dense curve
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        n = len(P)
        N = np.zeros_like(P)
        a = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        N[0] = np.cross(T[0], np.cross(a, T[0]))
        N[0] /= np.linalg.norm(N[0])
        for i in range(1, n + 1):
            t = T[i % n]
            v = N[i - 1] - t * np.dot(N[i - 1], t)
            v /= np.linalg.norm(v)
            if i < n:
                N[i] = v
            else:
                closing = v
        # twist needed to close: angle from transported N back to N[0] around T[0]
        B0 = np.cross(T[0], N[0])
        self.twist = math.atan2(np.dot(closing, B0), np.dot(closing, N[0]))
        self._T, self._N = T, N
        self._closing = closing
        mb = MeshBuilder()
        co = self.positions(0.0, 0.0).reshape(rings, sides, 3)
        idx = [[mb.v(co[i, k]) for k in range(sides)] for i in range(rings)]
        for i in range(rings):
            mb.bridge(idx[i], idx[(i + 1) % rings])
        self.obj = mb.to_object(name)

    def _frame(self, s):
        """Point, normal, binormal at arc-length fraction s (periodic)."""
        s = s % 1.0
        x = s * self.length
        i = int(np.searchsorted(self._cum, x, side="right") - 1)
        i = min(i, len(self._P) - 1)
        f = (x - self._cum[i]) / max(self._cum[i + 1] - self._cum[i], 1e-12)
        j = (i + 1) % len(self._P)
        p = self._P[i] * (1 - f) + self._P[j] * f
        t = self._T[i] * (1 - f) + self._T[j] * f
        t /= np.linalg.norm(t)
        nj = self._closing if j == 0 else self._N[j]  # last interval ends on the transported frame
        nrm = self._N[i] * (1 - f) + nj * f
        nrm -= t * np.dot(nrm, t)
        nrm /= np.linalg.norm(nrm)
        # spread the closing twist linearly so the frame field is periodic
        ang = -self.twist * s
        b = np.cross(t, nrm)
        n2 = nrm * math.cos(ang) + b * math.sin(ang)
        b2 = np.cross(t, n2)
        return p, n2, b2

    def positions(self, slide=0.0, roll=0.0, radius_fn=None):
        """slide: shift in rings; roll: shift in sides. radius_fn(s, k) optional."""
        co = np.empty((self.rings, self.sides, 3))
        for i in range(self.rings):
            s = (i + slide) / self.rings
            p, n, b = self._frame(s)
            for k in range(self.sides):
                a = 2 * math.pi * (k + roll) / self.sides
                r = radius_fn(s, a) if radius_fn else self.radius
                co[i, k] = p + r * (n * math.cos(a) + b * math.sin(a))
        return co.reshape(-1, 3)

    def update(self, slide=0.0, roll=0.0, radius_fn=None):
        co = self.positions(slide, roll, radius_fn)
        self.obj.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.obj.data.update()



def torus_knot(p=2, q=3, R=2.0, r=0.8, z=0.8):
    """Closed (p, q) torus knot curve u in [0,1) -> point."""
    def f(u):
        t = 2 * math.pi * u
        rr = R + r * math.cos(q * t)
        return (rr * math.cos(p * t), rr * math.sin(p * t), z * math.sin(q * t))
    return f
