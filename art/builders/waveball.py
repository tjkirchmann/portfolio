"""Wave ball: a spikeless cube-sphere whose surface carries rolling waves, like a liquid
planet.

Several wave trains of different wavelength travel across the sphere in different
directions. Each is a Gerstner wave on the sphere: the surface rises and falls along the
normal and slides along the travel direction, so crests sharpen and troughs flatten. On top:
the spike ball's slow breathing and under-the-skin crawl (looped noise plus bulges on closed
loops). Every time term uses whole cycles of tau, so tau = 1 equals tau = 0 exactly.
"""
import math

import bpy
import numpy as np

from .mesh import MeshBuilder
from .spikeball import FACES, REST, Motion


def cube_sphere(G=32, R=1.0):
    """All-quad equal-angle cube sphere with G x G cells per face, shared seams."""
    mb = MeshBuilder()
    index = {}

    def v(f, i, j):
        n, e1, e2 = (np.array(x, float) for x in FACES[f])
        a = math.tan(math.pi / 4 * (2 * i / G - 1))
        b = math.tan(math.pi / 4 * (2 * j / G - 1))
        p = n + a * e1 + b * e2
        p = p / np.linalg.norm(p) * R
        key = tuple(np.round(p, 9))
        if key not in index:
            index[key] = mb.v(p)
        return index[key]

    for f in range(6):
        V = [[v(f, i, j) for j in range(G + 1)] for i in range(G + 1)]
        for i in range(G):
            for j in range(G):
                mb.quad(V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])
    P = np.array(mb.verts) @ REST.T
    return P, np.array(mb.faces, dtype=np.int64)


class WaveBall:
    # (cycles over the sphere, cycles per loop, amplitude / R, steepness q = A k Q; the
    # sideways slide is q / k, so q < 1 keeps crests from folding over)
    TRAINS = [(1.6, 1, 0.045, 0.30), (2.7, -2, 0.026, 0.22), (4.1, 2, 0.015, 0.16), (6.3, -3, 0.008, 0.10)]

    def __init__(self, name, G=32, R=1.0, seed=11):
        P, F = cube_sphere(G, R)
        a, b, c, d = (P[F[:, k]] for k in range(4))
        out = (np.cross(c - a, d - b) * (a + b + c + d)).sum(1) < 0
        F[out] = F[out][:, ::-1]
        self.P0, self.F, self.R = P, F, R
        self.u = P / np.linalg.norm(P, axis=1)[:, None]
        rng = np.random.default_rng(seed)
        self.trains = []
        for f, m, amp, q in self.TRAINS:
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            self.trains.append((d, f, m, amp, q, rng.uniform(0, 2 * np.pi)))
        # breathing and crawl from the spike ball's motion (no spikes: empty axis set is
        # never used because every vertex sits on the skin)
        self.motion = Motion(np.array([[0.0, 0.0, 1.0]]), R, 1.0, seed)
        self.motion.k.update(noise=0.012, bulge=0.03, slide=0.008)
        me = bpy.data.meshes.new(name)
        me.from_pydata(P.tolist(), [], F.tolist())
        me.update()
        self.obj = bpy.data.objects.new(name, me)

    def positions(self, tau):
        u, R = self.u, self.R
        h = np.zeros(len(u))
        slide = np.zeros_like(u)
        for d, f, m, amp, q, ph in self.trains:
            x = u @ d
            phase = 2 * np.pi * (f * x - m * tau) + ph
            h += amp * np.cos(phase)
            t = d - x[:, None] * u
            tn = np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
            k = 2 * np.pi * f
            # Gerstner: slide toward the crest, |q| <= 1 keeps the surface from folding
            slide -= ((q / k) * np.sin(phase))[:, None] * (t / tn)
        kk = self.motion.k
        breath = 1 + kk["breath"] * (np.sin(2 * np.pi * tau) + 0.33 * np.sin(4 * np.pi * tau + 1.3))
        n, bl, grad = self.motion.crawl(u, tau)
        h = h + kk["noise"] * n + kk["bulge"] * bl
        tang = kk["slide"] * grad + slide
        return R * (u * (breath + h)[:, None] + tang)

    def update(self, tau):
        co = self.positions(tau)
        self.obj.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
        self.obj.data.update()
