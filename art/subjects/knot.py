"""Trefoil knot: a tube on a (2, 3) torus knot whose surface flows along itself."""
from builders.sweep import Sweep, torus_knot

TITLE = "Trefoil knot"
LOOP_SECONDS = 10
AZIMUTH = 45

RINGS = 180      # rings along the knot
SIDES = 16       # sides around the tube
SLIDE = 12       # rings travelled per loop (whole number, so the loop closes)
ROLL = 2         # sides rolled per loop (whole number)


def build():
    global tube
    tube = Sweep("knot", torus_knot(p=2, q=3, R=2.0, r=0.85, z=0.9), radius=0.42,
                 rings=RINGS, sides=SIDES)
    return [tube.obj]


def animate(t):
    tube.update(slide=SLIDE * t, roll=ROLL * t)
