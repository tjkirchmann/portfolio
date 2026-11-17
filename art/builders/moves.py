"""Camera moves for subjects that zoom: a satellite-style dive and its motion time warp.

`Dive` holds wide, zooms in exponentially (constant apparent speed) with eased ends, holds
close, pulls back the same way and holds wide again, so zoom(1) == zoom(0) == 1.

`Dive.tau(t)` is the motion phase for the living subject: it runs at a rate proportional to
1 / zoom, so on-screen motion keeps the same speed at every zoom (the closer you look, the
slower the world moves in world units). tau(0) = 0 and tau(1) = 1 exactly, and
tau(t + 1) = tau(t) + 1, so motion that is periodic in tau stays periodic in t.
"""
import math

import numpy as np


def _smoother(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


class Dive:
    def __init__(self, z_max=18.0, hold=0.25, dive=0.25, close=0.12, back=0.28, samples=20000):
        self.z_max, self.hold, self.dive, self.close, self.back = z_max, hold, dive, close, back
        ts = np.linspace(0.0, 1.0, samples + 1)
        inv = np.array([1.0 / self.zoom(x) for x in ts])
        c = np.concatenate([[0.0], np.cumsum((inv[1:] + inv[:-1]) / 2 * np.diff(ts))])
        self._ts, self._tau = ts, c / c[-1]
        self._tau[-1] = 1.0

    def zoom(self, t):
        t = t % 1.0
        a = self.hold
        b = a + self.dive
        c = b + self.close
        d = c + self.back
        if t < a or t >= d:
            s = 0.0
        elif t < b:
            s = _smoother((t - a) / self.dive)
        elif t < c:
            s = 1.0
        else:
            s = 1.0 - _smoother((t - c) / self.back)
        return math.exp(math.log(self.z_max) * s)

    def tau(self, t):
        k = math.floor(t)
        return k + float(np.interp(t - k, self._ts, self._tau))
