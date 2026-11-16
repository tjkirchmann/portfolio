"""`--check`: measured evidence for the camera, loop, topology, density, motion, framing,
gear meshing, line width, dimming and the delivered files. Exit code 1 on any failure."""
import json
import math
import os

import numpy as np

from . import camera as cammod, mp4
from .lines import COLOR_DISPLAY, linear_to_srgb, srgb_to_linear
from .pipeline import LOOP_MAD_LIMIT, loop_mad
from .render import Renderer

MAX_MOVE_PX = 2.0
MIN_SPACING, MAX_SPACING = 5.0, 60.0
FILL_RANGE = (0.70, 0.85)
MAX_BYTES = 1.5 * 1024 * 1024


class Report:
    def __init__(self):
        self.fails = []

    def line(self, key, msg, ok=None):
        tag = "" if ok is None else (" PASS" if ok else " FAIL")
        print(f"[{key}] {msg}{tag}", flush=True)
        if ok is False:
            self.fails.append(key)


# ---------------------------------------------------------------- geometry helpers

def object_arrays(o):
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    m = np.array(o.matrix_world)
    P = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    return P, lt, lv


def topology(stage, rep):
    for o in stage.objects:
        _, lt, _ = object_arrays(o)
        tris, quads, ngons = int((lt == 3).sum()), int((lt == 4).sum()), int((lt > 4).sum())
        rep.line("AC-7", f"{o.name}: {quads} quads, {tris} triangles, {ngons} n-gons, "
                         f"{len(o.data.edges)} edges", tris == 0)


def density(stage, rep, size):
    """In-surface spacing between opposite edges of every quad, in delivery px."""
    ppu = stage.px_per_unit(size)
    lo_all, hi_all = 1e9, 0
    for o in stage.objects:
        P, lt, lv = object_arrays(o)
        starts = np.concatenate([[0], np.cumsum(lt)[:-1]])
        q = starts[lt == 4]
        a, b, c, d = (P[lv[q + k]] for k in range(4))
        s1 = np.linalg.norm((a + b) / 2 - (d + c) / 2, axis=1)
        s2 = np.linalg.norm((b + c) / 2 - (a + d) / 2, axis=1)
        s = np.concatenate([s1, s2]) * ppu
        lo, hi = float(s.min()), float(s.max())
        p1 = float(np.percentile(s, 1))
        lo_all, hi_all = min(lo_all, lo), max(hi_all, hi)
        rep.line("AC-15", f"{o.name}: quad spacing min {lo:.1f}px (1st pct {p1:.1f}) max {hi:.1f}px",
                 lo >= MIN_SPACING and hi <= MAX_SPACING)
    return lo_all, hi_all


def motion_and_framing(stage, rep, size):
    n = stage.frames
    prev = None
    worst = (0, 0)
    fills = []
    clip = False
    for i in range(n + 1):
        stage.pose(i / n)
        px = stage.to_px(stage.world_points(), size)
        if prev is not None:
            dmax = float(np.linalg.norm(px - prev, axis=1).max())
            if dmax > worst[0]:
                worst = (dmax, i)
        prev = px
        w = px[:, 0].max() - px[:, 0].min()
        h = px[:, 1].max() - px[:, 1].min()
        fills.append(max(w, h) / size)
        if px.min() < 0 or px.max() > size:
            clip = True
    rep.line("AC-5", f"max vertex displacement {worst[0]:.3f}px/frame (frame {worst[1]})",
             worst[0] <= MAX_MOVE_PX)
    rep.line("AC-18", f"geometry bounds fill {min(fills):.3f}-{max(fills):.3f} of frame, "
                      f"clips edge: {clip}", FILL_RANGE[0] <= min(fills) and max(fills) <= FILL_RANGE[1] and not clip)
    return worst, (min(fills), max(fills))


def rendered_framing(stats_path, size, rep):
    if not os.path.exists(stats_path):
        rep.line("AC-18", f"no render stats at {stats_path} (run a final render first)", None)
        return
    st = json.load(open(stats_path))
    boxes = [s["bbox"] for s in st["stats"] if s.get("bbox")]
    fills = [max(b[2] - b[0] + 1, b[3] - b[1] + 1) / size for b in boxes]
    clip = any(b[0] <= 0 or b[1] <= 0 or b[2] >= size - 1 or b[3] >= size - 1 for b in boxes)
    az = [s["alpha_zero"] for s in st["stats"]]
    rep.line("AC-18", f"rendered bbox fill per frame {min(fills):.3f}-{max(fills):.3f}; first {boxes[0]}, "
                      f"middle {boxes[len(boxes) // 2]}, last {boxes[-1]}; touches edge: {clip}",
             FILL_RANGE[0] <= min(fills) and max(fills) <= FILL_RANGE[1] and not clip)
    rep.line("AC-3", f"alpha==0 fraction per frame {min(az):.3f}-{max(az):.3f}", min(az) > 0.5)
    rep.line("AC-6", f"render-time loop MAD {st['loop_mad']:.4f}/255", st["loop_ok"])


# ---------------------------------------------------------------- gears

def _pip(pts, poly):
    x, y = pts[:, 0:1], pts[:, 1:2]
    x0, y0 = poly[:, 0][None], poly[:, 1][None]
    x1, y1 = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cond = (y0 > y) != (y1 > y)
    xi = x0 + (y - y0) * (x1 - x0) / np.where(y1 - y0 == 0, 1e-12, y1 - y0)
    return ((cond & (x < xi)).sum(1) % 2) == 1


def _seg_dist(pts, poly):
    a = poly
    b = np.roll(poly, -1, 0)
    ab = b - a
    t = np.clip(((pts[:, None, :] - a[None]) * ab[None]).sum(2) / (ab ** 2).sum(1)[None], 0, 1)
    proj = a[None] + t[..., None] * ab[None]
    return np.linalg.norm(pts[:, None, :] - proj, axis=2).min(1)


def gear_checks(rep, phases=16):
    try:
        from builders.gear import TRAINS
    except ImportError:
        return
    for tr in TRAINS:
        r = tr.report()
        rep.line("AC-11", f"driver turns per loop {r['driver_turns']}")
        for g in r["gears"]:
            rep.line("AC-11", f"  {g['name']}: N={g['N']} mesh symmetry {g['sym']} ratio {g['ratio']} "
                              f"turns/loop {g['turns']} teeth passed {g['teeth_passed']:.3f} "
                              f"meshes {g['mesh_with']} layer {g['layer']}",
                     abs(g["teeth_passed"] * g["sym"] / g["N"] - round(g["teeth_passed"] * g["sym"] / g["N"])) < 1e-9)
        for g in tr.gears:
            p = g["partner"]
            if p is None:
                continue
            worst_pen, min_clear = 0, 1e9
            for k in range(phases):
                t = k / phases
                A = np.array(tr.outline_at(g, t))
                B = np.array(tr.outline_at(p, t))
                ca, cb = np.array(g["centre"]), np.array(p["centre"])
                ra_a = g["mesh"].info["ra"]
                ra_b = p["mesh"].info["ra"]
                An = A[np.linalg.norm(A - cb, axis=1) < ra_b * 1.01]
                Bn = B[np.linalg.norm(B - ca, axis=1) < ra_a * 1.01]
                pen = int(_pip(An, B).sum() + _pip(Bn, A).sum())
                worst_pen = max(worst_pen, pen)
                Bnear = B[np.linalg.norm(B - ca, axis=1) < ra_a * 1.2]
                Anear = A[np.linalg.norm(A - cb, axis=1) < ra_b * 1.2]
                if len(An):
                    min_clear = min(min_clear, float(_seg_dist(An, Bnear).min()))
                if len(Bn):
                    min_clear = min(min_clear, float(_seg_dist(Bn, Anear).min()))
            m = g["mesh"].M
            rep.line("AC-16", f"{g['name']} x {p['name']}: {phases} phases, vertices inside partner: "
                              f"{worst_pen}, min clearance {min_clear / m:.4f} module", worst_pen == 0)
        for g in tr.gears:
            info = g["mesh"].info
            rep.line("AC-16", f"{g['name']}: involute flank {len(info['side']) - 1 - 2} segs + fillet 2 segs "
                              f"(rho {info['rho']:.3f} M), rb {info['rb']:.3f} rf {info['rf']:.3f} ra {info['ra']:.3f}")


# ---------------------------------------------------------------- line measurements

def _bilinear(img, x, y):
    h, w = img.shape
    x0 = np.clip(np.floor(x).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 2)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
            + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def line_measure(stage, r, disp, rep, size):
    """Effective width (integrated linear light / expected luminance) of isolated edges."""
    lines = r.lines
    P, E, front, A, B, bA, bB, _ = lines.segments()  # brightness incl. occlusion, as drawn
    ne = len(E)
    b0, bmid, b1 = bA[:ne], bA[ne:], bB[ne:]
    px = stage.to_px(P, size)
    a, b = px[E[:, 0]], px[E[:, 1]]
    L = np.linalg.norm(b - a, axis=1)
    mid = (a + b) / 2
    d = P @ lines.Z
    lo, hi = lines.depth_range
    depth = np.clip(((d[E[:, 0]] + d[E[:, 1]]) / 2 - lo) / (hi - lo), 0, 1)
    lin = srgb_to_linear(disp)
    rng = np.random.default_rng(1)
    cand = np.nonzero((L > 14) & (np.abs(b0 - bmid) < 0.02) & (np.abs(bmid - b1) < 0.02))[0]
    rng.shuffle(cand)
    found = {}
    for e in cand[:20000]:
        m = mid[e]
        u = (b[e] - a[e]) / L[e]
        n = np.array([-u[1], u[0]])
        s = np.arange(-3, 3.001, 0.125)
        Q = m[None] + s[:, None] * n[None]
        # isolation: every other edge stays >= 3px from every profile sample point
        near = np.nonzero(np.linalg.norm(mid - m, axis=1) < L / 2 + 6)[0]
        near = near[near != e]
        if len(near):
            aa, ab = a[near], b[near] - a[near]
            t = np.clip(((Q[:, None, :] - aa[None]) * ab[None]).sum(2)
                        / np.maximum((ab ** 2).sum(1), 1e-9)[None], 0, 1)
            dist = np.linalg.norm(aa[None] + t[..., None] * ab[None] - Q[:, None, :], axis=2)
            if dist.min() < 3.0:
                continue
        fade = float(lines.fade(((P[E[e, 0]] + P[E[e, 1]]) / 2)[None])[0])
        kind = "back" if not front[e] else ("front_hidden" if bmid[e] < 0.7 * fade else "front")
        key = kind + ("_near" if depth[e] > 0.6 else "_far" if depth[e] < 0.4 else "_mid")
        if key in found:
            continue
        prof = _bilinear(lin, m[0] + n[0] * s, m[1] + n[1] * s)
        # subtract the local floor (tails of other lines, Lanczos ringing), taken at the ends
        prof = np.clip(prof - min(prof[:4].mean(), prof[-4:].mean()), 0, None)
        bb = bmid[e]
        expect = float(srgb_to_linear(bb * COLOR_DISPLAY))
        width = float(prof.sum() * 0.125 / expect)
        # measured brightness (assuming the nominal 1.25px width) over the depth fade at
        # this point = the facing / occlusion factor actually drawn
        lum = prof.sum() * 0.125 / r.q["line_px"]
        factor = float(linear_to_srgb(lum) / COLOR_DISPLAY / fade)
        peak = float(_bilinear(disp, np.array([m[0]]), np.array([m[1]]))[0] * 255)
        found[key] = dict(edge=int(e), px=[round(float(m[0]), 1), round(float(m[1]), 1)], width=round(width, 3),
                          brightness=round(float(bb), 3), depth=round(float(depth[e]), 2), peak=round(peak, 1),
                          factor=round(factor, 3))
        if len(found) == 9:
            break
    if not found:
        rep.line("AC-4", "no isolated edge found to measure", False)
    for k, v in sorted(found.items()):
        ok = 1.0 <= v["width"] <= 1.5
        rep.line("AC-4", f"{k}: width {v['width']}px brightness {v['brightness']} depth {v['depth']} "
                         f"at {v['px']} peak {v['peak']}/255", ok)
        rep.line("AC-14", f"{k}: drawn brightness / depth fade = {v['factor']} "
                          f"(front visible 1.0, front hidden {lines.occ}, back {lines.back})")
    return found


# ---------------------------------------------------------------- outputs

def outputs(rep, public, slug, stage):
    files = ["loop.webm", "loop.mp4", "poster.png", "meta.json"]
    missing = [f for f in files if not os.path.exists(os.path.join(public, f))]
    rep.line("AC-1", f"{public}: missing {missing}" if missing else f"{public}: all four files present", not missing)
    if missing:
        return
    meta = json.load(open(os.path.join(public, "meta.json")))
    keys = ["slug", "subject", "width", "height", "fps", "frames", "duration", "blurDataUrl"]
    rep.line("AC-2", f"meta keys {list(meta)}", list(meta) == keys)
    blur = meta["blurDataUrl"]
    import base64
    import struct
    raw = base64.b64decode(blur.split(",", 1)[1])
    bw, bh = struct.unpack(">II", raw[16:24])
    rep.line("AC-2", f"blurDataUrl {bw}x{bh} PNG, {len(raw)} bytes, data URL {len(blur)} chars",
             bw <= 32 and len(blur) < 2048 and raw[:8] == b"\x89PNG\r\n\x1a\n")
    rep.line("AC-8", f"meta {meta['width']}x{meta['height']} {meta['fps']}fps {meta['frames']} frames "
                     f"{meta['duration']}s", meta["width"] == meta["height"] == 1200 and meta["fps"] == 30
             and 6 <= meta["duration"] <= 12)
    for f in ("loop.mp4", "loop.webm"):
        sz = os.path.getsize(os.path.join(public, f))
        info = mp4.probe_mp4(os.path.join(public, f)) if f.endswith("mp4") else mp4.probe_webm(os.path.join(public, f))
        ok = sz < MAX_BYTES and info.get("width") == 1200 and info.get("height") == 1200 \
            and info.get("frames") == meta["frames"]
        if f.endswith("mp4"):
            ok = ok and info["codec"] == "avc1" and info["faststart"] and info["chroma"].startswith("4:2:0")
        else:
            ok = ok and info.get("codec") in ("V_VP9", "V_AV1")
        rep.line("AC-8", f"{f}: {sz} bytes ({sz / 1048576:.2f} MB) {json.dumps(info)}", ok)


def run(stage, a, cache):
    rep = Report()
    size = 1200
    print(f"[AC-13] Blender headless with --factory-startup; outputs under {os.path.dirname(cache)} and {a.public}")
    rep.line("AC-19", f"camera azimuth {stage.azimuth}\n  {cammod.matrix_text(stage.cam)}")
    rep.line("AC-18", f"framing: root scale {stage.scale:.5f}, fill target {stage.fill}, depth range "
                      f"{stage.depth_range[0]:.3f}..{stage.depth_range[1]:.3f}")
    topology(stage, rep)
    density(stage, rep, size)
    motion_and_framing(stage, rep, size)
    gear_checks(rep)
    r = Renderer(stage, "final", os.path.join(cache, "tmp"))
    end, _ = r.render(1.0)
    first, st = r.render(0.0)
    mad = loop_mad(first, end)
    rep.line("AC-6", f"frame {stage.frames + 1} (t=1) vs frame 1 (t=0): MAD {mad:.4f}/255, limit {LOOP_MAD_LIMIT}",
             mad < LOOP_MAD_LIMIT)
    rep.line("AC-3", f"check frame alpha==0 fraction {st['alpha_zero']:.3f}", st["alpha_zero"] > 0.5)
    line_measure(stage, r, first, rep, size)
    rendered_framing(os.path.join(cache, "render_stats.json"), size, rep)
    outputs(rep, a.public, a.slug, stage)
    print(f"CHECK {a.slug}: {'FAIL ' + ', '.join(sorted(set(rep.fails))) if rep.fails else 'all checks passed'}")
    return 1 if rep.fails else 0
