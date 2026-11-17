"""Full render: every frame -> loop check -> encode -> poster, blur, meta.json."""
import glob
import json
import math
import os
import shutil
import time

import numpy as np

from . import encode, post
from .render import Renderer

LOOP_MAD_LIMIT = 0.5  # mean absolute difference, 0-255 scale (AC-6)
MAX_BYTES = int(1.40 * 1024 * 1024)  # AC-8: under 1.5 MB (decimal) with a margin
# Encode at constant quality first; if that is too big, re-encode at an average bitrate that
# fits a 10-12 s loop under MAX_BYTES (detailed subjects like gears need this).
CRF = {"h264": 23, "vp9": 32}
PRESET = {"h264": "BEST", "vp9": "GOOD"}


def encode_capped(src, dst, fps, profile, seconds, max_bytes=MAX_BYTES):
    """H.264: constant quality first, falling back to an average bitrate if too big.
    VP9 overshoots wildly at constant quality here (20+ MB), so it goes straight to an
    average bitrate. Each retry scales the bitrate by how far the last file overshot."""
    kbps = int(max_bytes * 8 / 1000 / seconds * 0.92)
    if profile == "vp9":
        n = encode.encode(src, dst, fps, profile, CRF[profile], PRESET[profile], kbps=kbps)
        mode = f"{kbps} kbps"
    else:
        n = encode.encode(src, dst, fps, profile, CRF[profile], PRESET[profile])
        mode = f"crf {CRF[profile]}"
    while n > max_bytes and kbps > 200:
        if mode.startswith("crf"):
            pass
        else:
            kbps = int(kbps * max_bytes / n * 0.95)
        n = encode.encode(src, dst, fps, profile, CRF[profile], PRESET[profile], kbps=kbps)
        mode = f"{kbps} kbps"
    return n, mode


def _clean(d):
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*.png")):
        os.remove(f)


def loop_mad(a, b):
    return float(np.abs(np.round(a * 255) - np.round(b * 255)).mean())


def motion_blur_subframes(stage, t, n, size):
    """Sub-frames for camera moves: enough that the camera moves at most ~1.5 px between
    them, so fine lines blur along the move instead of strobing (1 when the camera holds)."""
    v = stage.view_speed(t, 1.0 / n, size)
    return int(min(8, max(1, math.ceil(v * 0.75 / 1.5))))


def _dirs(cache, preview):
    root = os.path.join(cache, "preview") if preview else cache
    return root, os.path.join(root, "frames"), os.path.join(root, "black"), os.path.join(root, "loopcheck")


def render_all(stage, a, cache):
    """Render frames [a.frames) (default all), then the loop check and delivery unless this
    is one worker of a parallel render (`--no-deliver`). Every frame is a pure function of
    its index, so workers can split the range and their frames are identical to a single
    run's. With `--resume`, frames whose files already exist are skipped."""
    preview = a.quality == "preview"
    root, frames_dir, black_dir, lc_dir = _dirs(cache, preview)
    n = stage.frames
    lo, hi = (a.frames if a.frames else (0, n))
    for d in (frames_dir, black_dir, lc_dir):
        if a.frames or a.resume:
            os.makedirs(d, exist_ok=True)
        else:
            _clean(d)
    r = Renderer(stage, a.quality, os.path.join(cache, f"tmp_{lo}"))
    t0 = time.time()
    stats = []
    for i in range(lo, hi):
        name = f"f_{i + 1:04d}.png"
        mp, bp = os.path.join(frames_dir, name), os.path.join(black_dir, name)
        if a.resume and os.path.exists(mp) and os.path.exists(bp):
            continue
        sub = motion_blur_subframes(stage, i / n, n, r.size)
        disp, st = r.render(i / n, mp, bp, sub=sub, shutter=0.75 / n)
        st["t"] = i / n
        st["i"] = i
        stats.append(st)
        if (i - lo) % 30 == 0:
            print(f"FRAME {i + 1}/{n} [{lo}-{hi}) {st['secs']}s", flush=True)
    if a.loopcheck or not a.frames:
        r.render(1.0, os.path.join(lc_dir, "f_next_rgba.png"), os.path.join(lc_dir, "f_next.png"))
    with open(os.path.join(root, f"stats_{lo:05d}.json"), "w") as f:
        json.dump(stats, f)
    print(f"WORKER [{lo}-{hi}) {len(stats)} frames in {time.time() - t0:.0f}s", flush=True)
    if a.no_deliver:
        return 0
    return finish(stage, a, cache)


def finish(stage, a, cache):
    """Loop check from the files on disk, merged stats, then encode and write outputs."""
    preview = a.quality == "preview"
    root, frames_dir, black_dir, lc_dir = _dirs(cache, preview)
    n = stage.frames
    first = post.load_png(os.path.join(black_dir, "f_0001.png"))[:, :, :3].mean(2)
    end = post.load_png(os.path.join(lc_dir, "f_next.png"))[:, :, :3].mean(2)
    mad = loop_mad(first, end)
    ok = mad < LOOP_MAD_LIMIT
    print(f"LOOP CHECK frame {n + 1} vs frame 1: MAD {mad:.4f}/255 (limit {LOOP_MAD_LIMIT}) "
          f"{'PASS' if ok else 'FAIL'}")
    stats = []
    for fn in sorted(glob.glob(os.path.join(root, "stats_*.json"))):
        stats += json.load(open(fn))
    old = os.path.join(root, "render_stats.json")
    if os.path.exists(old):  # keep stats of frames rendered by an earlier, resumed run
        have = {s.get("i") for s in stats}
        stats += [s for s in json.load(open(old)).get("stats", []) if s.get("i") not in have]
    stats.sort(key=lambda s: s.get("t", 0))
    summary = dict(slug=a.slug, frames=n, loop_mad=mad, loop_ok=ok, scale=stage.scale,
                   depth_range=stage.depth_range, stats=stats)
    with open(old, "w") as f:
        json.dump(summary, f)
    for fn in glob.glob(os.path.join(root, "stats_*.json")):
        os.remove(fn)
    missing = [i for i in range(n) if not os.path.exists(os.path.join(black_dir, f"f_{i + 1:04d}.png"))]
    if missing:
        print(f"FAIL: {len(missing)} frames missing (first {missing[0] + 1})")
        return 1
    if not ok:
        print("FAIL: loop is not seamless; outputs not written")
        return 1
    return deliver(stage, a, cache, first, first.shape[0])


def deliver(stage, a, cache, first=None, size=None):
    """Encode the cached over-black frames and write poster, blur and meta.json."""
    preview = a.quality == "preview"
    root = os.path.join(cache, "preview") if preview else cache
    black_dir = os.path.join(root, "black")
    n = len(glob.glob(os.path.join(black_dir, "*.png")))
    if first is None:
        first = post.load_png(os.path.join(black_dir, "f_0001.png"))[:, :, 0]
    size = size or first.shape[0]
    out = os.path.join(root, "out") if preview else a.public
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    sizes = {}
    secs = n / stage.fps
    cap = int(float(getattr(stage.subject, "MAX_MB", 1.40)) * 1024 * 1024)
    sizes["loop.mp4"] = encode_capped(black_dir, os.path.join(out, "loop.mp4"), stage.fps, "h264", secs, cap)
    if not preview:
        sizes["loop.webm"] = encode_capped(black_dir, os.path.join(out, "loop.webm"), stage.fps, "vp9", secs, cap)
    shutil.copyfile(os.path.join(black_dir, "f_0001.png"), os.path.join(out, "poster.png"))
    blur = post.blur_data_url(first, os.path.join(cache, "tmp", "blur.png"))
    meta = dict(slug=a.slug, subject=getattr(stage.subject, "TITLE", a.slug), width=size, height=size,
                fps=stage.fps, frames=n, duration=round(n / stage.fps, 3), blurDataUrl=blur)
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    for k, v in sizes.items():
        print(f"WROTE {os.path.join(out, k)} {v[0]} bytes ({v[1]})")
    print(f"WROTE {out}/poster.png, meta.json (blurDataUrl {len(blur)} chars)")
    print(f"DONE {n} frames")
    return 0
