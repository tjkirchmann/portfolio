"""Spike ball with Life: the living spike ball, with Conway's Life running on its own quads
as metallic emerald, teal and blue tiles under the wire."""
from builders.spikeball import SpikeBall
from framework.life import attach

TITLE = "Spike ball, life"
LOOP_SECONDS = 14
AZIMUTH = 45
MAX_MB = 2.8  # AC-28: each file under 3 MB


def build():
    global ball
    ball = SpikeBall("spikeball_life", seed=7)
    attach(ball.obj, int(LOOP_SECONDS * 30), seed=5)
    return [ball.obj]


def animate(t):
    ball.update(t)
