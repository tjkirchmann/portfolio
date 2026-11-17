"""Wave ball with Life: a liquid planet of rolling wave trains, breathing and crawling, with
Conway's Life running on its quads as metallic tiles under the wire."""
from builders.waveball import WaveBall
from framework.life import attach

TITLE = "Wave ball, life"
LOOP_SECONDS = 14
AZIMUTH = 45
MAX_MB = 2.8  # AC-28: each file under 3 MB


def build():
    global ball
    ball = WaveBall("waveball_life", G=32, seed=11)
    attach(ball.obj, int(LOOP_SECONDS * 30), seed=9)
    return [ball.obj]


def animate(t):
    ball.update(t)
