"""Gear train: compound spur gears meshing across two depth layers."""
from builders.gear import Train

TITLE = "Gear train"
LOOP_SECONDS = 10
AZIMUTH = 45
FILL = 0.83


def build():
    global train
    train = Train(module=1.0, axis="X", cycles=1)
    b = train.add("b", 24, at=(0, 0), backlash=0.16)
    bp = train.add("b_pinion", 16, shaft=b, layer=3.2)
    a = train.add("a", 14, mesh=b, angle=207)
    train.add("g", 18, mesh=a, angle=240)
    train.add("c", 14, mesh=bp, angle=262)
    d = train.add("d", 16, mesh=b, angle=24)
    train.add("e", 18, mesh=b, angle=112)
    train.add("f", 20, mesh=d, angle=75)
    return train.objects


def animate(t):
    train.pose(t)
