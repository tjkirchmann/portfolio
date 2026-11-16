#!/usr/bin/env python3
"""Format bake-off (AC-9): encode one subject's over-black master frames six ways.

  python3 art/tools/bakeoff.py gears

Writes art/.cache/bakeoff/<slug>/ (encodes, decoded frames) and crops to
.orchestration/reports/art-shots/. Encoders:
  - H.264 MP4, VP9 WebM: the delivered files (Blender's bundled FFmpeg, capped bitrate)
  - AV1 WebM: Blender's bundled FFmpeg (libaom/SVT via Blender), 900 kbps
  - GIF: ImageMagick `magick` (Homebrew), 64-level grey palette, no dither
  - animated WebP: libwebp `img2webp` (Homebrew), lossy
  - animated AVIF: libheif `heif-enc -S` (Homebrew), AV1 sequence
The Homebrew ffmpeg is not used (it is broken on this machine).
"""
import glob
import json
import os
import shutil
import subprocess
import sys

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ART)
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def run(cmd, **kw):
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, **kw)


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "gears"
    black = os.path.join(ART, ".cache", slug, "black")
    frames = sorted(glob.glob(os.path.join(black, "f_*.png")))
    if not frames:
        sys.exit(f"no frames in {black}; run python3 art/cli.py {slug} first")
    out = os.path.join(ART, ".cache", "bakeoff", slug)
    os.makedirs(out, exist_ok=True)
    shots = os.path.join(REPO, ".orchestration", "reports", "art-shots")
    os.makedirs(shots, exist_ok=True)
    res = {}
    # videos: the delivered H.264 / VP9 files, plus AV1 via Blender
    pub = os.path.join(REPO, "public", "art", slug)
    shutil.copyfile(os.path.join(pub, "loop.mp4"), os.path.join(out, "loop_h264.mp4"))
    shutil.copyfile(os.path.join(pub, "loop.webm"), os.path.join(out, "loop_vp9.webm"))
    fresh = "--fresh" in sys.argv  # otherwise reuse encodes already in the cache
    if fresh or not os.path.exists(os.path.join(out, "loop_av1.webm")):
        run([BLENDER, "-b", "--factory-startup", "--python", os.path.join(ART, "tools", "bakeoff_blender.py"),
             "--", "encode", black, out], stdout=subprocess.DEVNULL)
    # GIF
    gif = os.path.join(out, "loop.gif")
    if fresh or not os.path.exists(gif):
            run(["magick", "-delay", "1x30", "-loop", "0", *frames, "-colorspace", "Gray", "+dither",
             "-colors", "64", "-layers", "OptimizeTransparency", gif])
    # animated WebP
    webp = os.path.join(out, "loop.webp")
    if fresh or not os.path.exists(webp):
            run(["img2webp", "-loop", "0", "-lossy", "-q", "70", "-m", "6", "-d", "33", *frames, "-o", webp],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # animated AVIF (AV1 image sequence)
    avif = os.path.join(out, "loop.avif")
    if fresh or not os.path.exists(avif):
            run(["heif-enc", "-S", "--fps", "30", "--repetitions", "infinite", "-q", "60", "-o", avif, frames[0]],
            stdout=subprocess.DEVNULL)
    for name in ("loop_h264.mp4", "loop_vp9.webm", "loop_av1.webm", "loop.gif", "loop.webp", "loop.avif"):
        p = os.path.join(out, name)
        res[name] = os.path.getsize(p) if os.path.exists(p) else None
    # decode frame 1 of each (the AVIF sequence is set to repeat forever, so heif-dec cannot
    # dump it; ImageMagick reads its first frame)
    mid = 0
    dec = os.path.join(out, "decoded")
    os.makedirs(dec, exist_ok=True)
    shutil.copyfile(frames[mid], os.path.join(dec, "master.png"))
    run(["magick", f"{gif}[{mid}]", "-coalesce", os.path.join(dec, "gif.png")])
    run(["magick", f"{webp}[{mid}]", os.path.join(dec, "webp.png")])
    run(["magick", f"{avif}[0]", os.path.join(dec, "avif.png")])
    run([BLENDER, "-b", "--factory-startup", "--python", os.path.join(ART, "tools", "bakeoff_blender.py"),
         "--", "decode", out, str(mid + 1)], stdout=subprocess.DEVNULL)
    # one contact sheet: 200% crops of the same region from every format
    with open(os.path.join(out, "sizes.json"), "w") as f:
        json.dump(res, f, indent=2)
    labels = [("master.png", "master PNG"), ("h264.png", "H.264 MP4"), ("vp9.png", "VP9 WebM"),
              ("av1.png", "AV1 WebM"), ("gif.png", "GIF"), ("webp.png", "animated WebP"),
              ("avif.png", "animated AVIF")]
    tiles = []
    for fn, label in labels:
        src = os.path.join(dec, fn)
        if not os.path.exists(src):
            continue
        t = os.path.join(dec, "crop_" + fn)
        run(["magick", src, "-crop", "200x200+520+420", "+repage", "-filter", "point", "-resize", "200%",
             "-background", "black", "-fill", "white", "-gravity", "north", "-splice", "0x24",
             "-pointsize", "16", "-annotate", "+0+4", label, t])
        tiles.append(t)
    run(["magick", "montage", *tiles, "-tile", "4x", "-geometry", "+6+6", "-background", "#222",
         os.path.join(shots, f"{slug}-formats-200pct.png")])
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
