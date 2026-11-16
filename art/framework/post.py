"""Image maths (inside Blender's Python, numpy): downscale, master RGBA, over-black frames.

The render is linear light at 2x. It is downscaled with a separable Lanczos-3 filter in
linear light, then encoded to display values. The master is RGBA with a constant neutral
colour and alpha = display value / colour, so master-over-black reproduces the render.
"""
import base64
import os

import bpy
import numpy as np

from .lines import COLOR_DISPLAY, linear_to_srgb


def lanczos_weights(a=3):
    """Taps for an exact 2x Lanczos-a decimation (output pixel between input 2j and 2j+1)."""
    d = np.arange(-2 * a + 1, 2 * a + 1) - 0.5  # input centre offsets in input pixels
    x = d / 2.0
    w = np.sinc(x) * np.sinc(x / a)
    w[np.abs(x) >= a] = 0
    return w / w.sum(), -2 * a + 1


def downscale2(img):
    """img (H, W) float -> (H/2, W/2) with Lanczos-3."""
    w, first = lanczos_weights()
    pad = len(w)
    def axis(a):
        a = np.pad(a, ((pad, pad), (0, 0)), mode="edge")
        n = (a.shape[0] - 2 * pad) // 2
        out = np.zeros((n, a.shape[1]), np.float64)
        for k, wk in enumerate(w):
            start = pad + first + k
            out += wk * a[start:start + 2 * n:2]
        return out
    return axis(axis(img).T).T


def load_exr(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, 0].astype(np.float64)  # top row first, R channel


def to_display(lin):
    return linear_to_srgb(np.clip(lin, 0, 1))


def save_png(path, arr, mode):
    """arr top-row-first, float 0..1. mode 'RGBA' (H,W,4), 'RGB' (H,W,3) or 'BW' (H,W)."""
    h, w = arr.shape[:2]
    if mode == "BW":
        rgba = np.repeat(arr[:, :, None], 3, 2)
        rgba = np.concatenate([rgba, np.ones((h, w, 1))], 2)
    elif mode == "RGB":
        rgba = np.concatenate([arr, np.ones((h, w, 1))], 2)
    else:
        rgba = arr
    img = bpy.data.images.new("tmp_save", w, h, alpha=(mode == "RGBA"))
    img.alpha_mode = "STRAIGHT"
    img.pixels.foreach_set(np.ascontiguousarray(rgba[::-1]).astype(np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    sc = bpy.context.scene
    s = sc.render.image_settings
    old = (s.file_format, s.color_mode, s.color_depth, s.compression)
    s.file_format, s.color_mode, s.color_depth, s.compression = "PNG", mode, "8", 90
    img.save_render(path, scene=sc)
    s.file_format, s.color_mode, s.color_depth, s.compression = old
    bpy.data.images.remove(img)


def load_png(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    ch = img.channels
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1]


def finish_frame(lin2x, master_path, black_path):
    """2x linear render -> master RGBA + over-black PNG. Returns display (H, W) and stats."""
    lin = downscale2(lin2x)
    disp = to_display(lin)
    alpha = np.clip(disp / COLOR_DISPLAY, 0, 1)
    disp = alpha * COLOR_DISPLAY
    h, w = alpha.shape
    if master_path:
        rgba = np.empty((h, w, 4))
        rgba[:, :, :3] = COLOR_DISPLAY
        rgba[:, :, 3] = alpha
        save_png(master_path, rgba, "RGBA")
    if black_path:
        save_png(black_path, disp, "BW")
    ys, xs = np.nonzero(alpha > 2.5 / 255)
    stats = dict(bbox=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None,
                 alpha_zero=float((np.round(alpha * 255) == 0).mean()))
    return disp, stats


def blur_data_url(disp, path, size=32):
    h, w = disp.shape
    f = h // size
    small = disp[: f * size, : f * size].reshape(size, f, size, f).mean((1, 3))
    small = np.clip(small / max(small.max(), 1e-6) * 0.6, 0, 1)  # visible placeholder glow
    save_png(path, small, "BW")
    with open(path, "rb") as fh:
        data = fh.read()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
