"""Spike ball: a soft sensory toy ball whose skin breathes, ripples and crawls."""
from builders.spikeball import SpikeBall

TITLE = "Spike ball"
LOOP_SECONDS = 12
AZIMUTH = 45


def build():
    global ball
    ball = SpikeBall("spikeball", seed=7)
    return [ball.obj]


def animate(t):
    ball.update(t)
