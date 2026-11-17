#!/usr/bin/env python3
"""Report shots (evidence images) from rendered frames. Viewing aid only: uses ImageMagick.

  python3 art/tools/shots.py

Needs final renders in art/.cache/<slug>/black/ and dimming stills from
`python3 art/cli.py gears --still 0 [--no-back-dim]`.
"""
import os
import subprocess

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ART)
SHOTS = os.path.join(REPO, ".orchestration", "reports", "art-shots")
REF = os.path.join(REPO, ".orchestration", "designs", "ref", "gears-reference.webp")


def m(*args):
    subprocess.run(["magick", *args], check=True, stdin=subprocess.DEVNULL)


def black(slug, i):
    return os.path.join(ART, ".cache", slug, "black", f"f_{i:04d}.png")


def label(src, text, out, size=None):
    args = [src]
    if size:
        args += ["-resize", size]
    m(*args, "-background", "black", "-fill", "#ccc", "-gravity", "north", "-splice", "0x30",
      "-pointsize", "20", "-annotate", "+0+5", text, out)


def main():
    os.makedirs(SHOTS, exist_ok=True)
    tmp = os.path.join(ART, ".cache", "shots_tmp")
    os.makedirs(tmp, exist_ok=True)
    for slug in ("gears", "gyroscope", "knot"):
        n = len(os.listdir(os.path.join(ART, ".cache", slug, "black")))
        # first, middle, last frames
        tiles = []
        for i, name in ((1, "first"), (n // 2 + 1, "middle"), (n, "last")):
            t = os.path.join(tmp, f"{slug}_{name}.png")
            label(black(slug, i), f"{slug} frame {i} ({name})", t, "600x600")
            tiles.append(t)
        m("montage", *tiles, "-tile", "3x", "-geometry", "+4+4", "-background", "#222",
          os.path.join(SHOTS, f"{slug}-first-middle-last.png"))
        # full still (topology evidence)
        m(black(slug, 1), os.path.join(SHOTS, f"{slug}-still.png"))
        # three consecutive frames at 400%
        tiles = []
        for i in (150, 151, 152):
            t = os.path.join(tmp, f"{slug}_c{i}.png")
            m(black(slug, i), "-crop", "120x120+540+540", "+repage", "-filter", "point", "-resize", "400%", t)
            label(t, f"frame {i}", t)
            tiles.append(t)
        m("montage", *tiles, "-tile", "3x", "-geometry", "+4+4", "-background", "#222",
          os.path.join(SHOTS, f"{slug}-consecutive-400pct.png"))
    # gears against the reference, same height
    m(REF, "-resize", "x884", os.path.join(tmp, "ref.png"))
    m(os.path.join(tmp, "ref.png"), "(", black("gears", 1), "-resize", "884x884", ")", "+append",
      os.path.join(SHOTS, "gears-vs-reference.png"))
    # dimming on / off
    st = os.path.join(ART, ".cache", "gears", "stills")
    a, b = os.path.join(tmp, "dim_on.png"), os.path.join(tmp, "dim_off.png")
    label(os.path.join(st, "t0.000.png"), "with back + hidden dimming", a, "700x700")
    label(os.path.join(st, "t0.000_nodim.png"), "without dimming", b, "700x700")
    m(b, a, "+append", os.path.join(SHOTS, "gears-dimming-off-on.png"))


if __name__ == "__main__":
    main()
