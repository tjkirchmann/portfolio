"""Wave ball: a liquid planet of rolling wave trains, breathing and crawling, drawn as an
opaque solid (true hidden-line removal) and delivered with a stacked alpha matte."""
from builders.waveball import WaveBall

TITLE = "Wave ball"
LOOP_SECONDS = 14
AZIMUTH = 45
OPAQUE = True   # solid: hidden lines removed, matte in the bottom half of the video
MAX_MB = 2.8    # each file under 3 MB (the frame is 1200 x 2400)


def build():
    global ball
    ball = WaveBall("waveball", G=32, seed=11, relax=60)
    return [ball.obj]


def animate(t):
    ball.update(t)
