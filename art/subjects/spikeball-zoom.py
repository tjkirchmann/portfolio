"""Spike ball, close up: the living ball, then a satellite-style dive into the skin between
the spikes, where finer wire and a crawling micro-relief fade in, and back out."""
from builders.moves import Dive
from builders.spikeball import SpikeBall

TITLE = "Spike ball, close up"
LOOP_SECONDS = 16
AZIMUTH = 45
MAX_MB = 2.8  # AC-24: each file under 3 MB (2.8 MiB = 2.94 MB)

DIVE = Dive(z_max=18.0, hold=0.25, dive=0.25, close=0.12, back=0.28)

# Level of detail: each level halves the wire spacing. It fades in (by brightness, with its
# new vertices morphing onto the true surface) while the zoom passes `zoom`, inside a cap of
# `theta` degrees around the dive target (full inside the first angle, gone at the second).
LEVELS = [
    dict(zoom=(1.6, 2.3), theta=(180, 180)),
    dict(zoom=(3.2, 4.6), theta=(25, 33)),
    dict(zoom=(6.4, 9.2), theta=(13, 18)),
    dict(zoom=(12.5, 17.5), theta=(9, 13)),
]


def build():
    global ball
    ball = SpikeBall("spikeball_zoom", seed=7, lod=LEVELS, target=("gap_near", (0.82, 0.82, 0.45)),
                     micro_zoom=(12.5, 17.5))
    return [ball.obj]


def animate(t):
    ball.update(DIVE.tau(t), DIVE.zoom(t))


def view(t):
    return DIVE.zoom(t), ball.focus(DIVE.tau(t))
