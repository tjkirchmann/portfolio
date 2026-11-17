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
MAX_BYTES = 1_500_000  # decimal MB, the stricter reading


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


def lod_provider(o):
    try:
        from builders.spikeball import WEIGHTS
    except ImportError:
        return None
    fn = WEIGHTS.get(o.name)
    return fn.__self__ if fn else None


def density(stage, rep, size):
    """In-surface spacing between opposite edges of every quad, in delivery px, at the wide
    framing. For level-of-detail meshes the base level is measured (finer levels are only
    visible when zoomed: see the AC-23 strip)."""
    stage.pose(0.0)
    ppu = stage.px_per_unit(size)
    lo_all, hi_all = 1e9, 0
    for o in stage.objects:
        P, lt, lv = object_arrays(o)
        prov = lod_provider(o)
        if prov is not None:
            a, b, c, d = (P[prov.base_faces[:, k]] for k in range(4))
        else:
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
    """Screen displacement per frame of on-screen vertices, under the camera of each frame.
    For zooming subjects the 2 px limit applies to frames where the camera holds; during
    camera moves the renderer adds motion-blur sub-frames instead (reported)."""
    n = stage.frames
    prev = None
    worst = (0, 0)
    moving = (0, 0)
    fills = []
    clip = False
    held_frames = 0
    for i in range(n + 1):
        t = i / n
        stage.pose(t)
        view = stage.view
        px = stage.to_px(stage.world_points(), size)
        if prev is not None:
            on = ((px >= 0) & (px <= size)).all(1)
            d = np.linalg.norm(px - prev, axis=1)
            dmax = float(d[on].max()) if on.any() else 0.0
            held = abs(view[0] - prev_view[0]) < 1e-9  # zoom holding (pan may track the focus)
            if held:
                held_frames += 1
                if dmax > worst[0]:
                    worst = (dmax, i)
            elif dmax > moving[0]:
                moving = (dmax, i)
        prev, prev_view = px, view
        if view[0] == 1.0:
            w = px[:, 0].max() - px[:, 0].min()
            h = px[:, 1].max() - px[:, 1].min()
            fills.append(max(w, h) / size)
            if px.min() < 0 or px.max() > size:
                clip = True
    rep.line("AC-5", f"max vertex displacement {worst[0]:.3f}px/frame (frame {worst[1]}) over "
                     f"{held_frames} frames with the zoom holding", worst[0] <= MAX_MOVE_PX)
    if moving[0]:
        from .pipeline import motion_blur_subframes
        subs = [motion_blur_subframes(stage, i / n, n, size) for i in range(n)]
        rep.line("AC-5", f"camera moving on {n - held_frames} frames: max on-screen displacement "
                         f"{moving[0]:.1f}px/frame (frame {moving[1]}); motion-blur sub-frames per "
                         f"frame {min(subs)}-{max(subs)} (camera <= ~1.5px between sub-frames)")
    rep.line("AC-18", f"geometry bounds fill {min(fills):.3f}-{max(fills):.3f} of frame, "
                      f"clips edge: {clip}", FILL_RANGE[0] <= min(fills) and max(fills) <= FILL_RANGE[1] and not clip)
    return worst, (min(fills), max(fills))


def rendered_framing(stats_path, size, rep):
    if not os.path.exists(stats_path):
        rep.line("AC-18", f"no render stats at {stats_path} (run a final render first)", None)
        return
    st = json.load(open(stats_path))
    boxes = [s["bbox"] for s in st["stats"] if s.get("bbox") and s.get("zoom", 1.0) == 1.0]
    fills = [max(b[2] - b[0] + 1, b[3] - b[1] + 1) / size for b in boxes]
    clip = any(b[0] <= 0 or b[1] <= 0 or b[2] >= size - 1 or b[3] >= size - 1 for b in boxes)
    az = [s["alpha_zero"] for s in st["stats"] if s.get("zoom", 1.0) == 1.0]
    rep.line("AC-18", f"rendered bbox fill per wide frame ({len(boxes)} frames) {min(fills):.3f}-{max(fills):.3f}; first {boxes[0]}, "
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


# ---------------------------------------------------------------- level of detail (zoom)

def visible_spacing(stage, prov, size):
    """In-surface spacing (x current px per unit) of the wire actually visible: for each
    level, its faces where that level is at least half faded in and the next level is not,
    front-facing, centre on screen. The far side of the ball seen dimly through the skin
    (faces more than a quarter of the depth range behind the nearest visible face) is left
    out. Returns (min, 1st percentile, max, count, levels used)."""
    lod = prov.lod
    P = stage.world_points()
    z = stage.view[0]
    ppu = stage.px_per_unit(size)
    cand = []
    for L, F in enumerate(lod.level_faces):
        if not len(F):
            continue
        ang = lod.ang[F].mean(1)
        aL = lod.alpha(L, ang, z)
        an = lod.alpha(L + 1, ang, z) if L < lod.L else np.zeros(len(F))
        a, b, c, d = (P[F[:, k]] for k in range(4))
        ctr = stage.to_px((a + b + c + d) / 4, size)
        nrm = np.cross(c - a, d - b)
        sel = (aL >= 0.5) & (an < 0.5) & ((ctr >= 0) & (ctr <= size)).all(1) & (nrm @ stage.Z > 0)
        if sel.any():
            depth = ((a + b + c + d) / 4)[sel] @ stage.Z
            s1 = np.linalg.norm((a + b) / 2 - (d + c) / 2, axis=1)[sel]
            s2 = np.linalg.norm((b + c) / 2 - (a + d) / 2, axis=1)[sel]
            cand.append((L, depth, np.minimum(s1, s2) * ppu, np.maximum(s1, s2) * ppu))
    near = max(c[1].max() for c in cand)
    span = stage.depth_range[1] - stage.depth_range[0]
    lo, hi, vals, used = [], [], [], []
    for L, depth, smin, smax in cand:
        keep = depth > near - 0.25 * span
        if keep.any():
            vals.append(np.concatenate([smin[keep], smax[keep]]))
            used.append(L)
    v = np.concatenate(vals)
    return float(v.min()), float(np.percentile(v, 1)), float(v.max()), len(v) // 2, used


def lod_checks(stage, r, rep, size, cache):
    prov = next((lod_provider(o) for o in stage.objects if lod_provider(o)), None)
    if prov is None or stage.view_fn is None:
        return
    ts = np.linspace(0, 1, 4001)[:-1]
    zs = np.array([stage.view_at(t)[0] for t in ts])
    zmax = zs.max()
    rep.line("AC-22", f"zoom 1.0 for t in [0, {ts[np.argmax(zs > 1.0001)]:.3f}), max zoom {zmax:.2f}x "
                      f"held for t in [{ts[np.argmax(zs >= zmax - 1e-6)]:.3f}, "
                      f"{ts[len(zs) - 1 - np.argmax(zs[::-1] >= zmax - 1e-6)]:.3f}], zoom at t=0 "
                      f"{zs[0]:.3f} and t=1 {stage.view_at(1.0)[0]:.3f}", zmax >= 12 and abs(stage.view_at(1.0)[0] - 1) < 1e-9)
    rising = np.nonzero((np.diff(zs) > 0))[0]
    strip = [("start", 0.0)]
    for target in (3.0, 6.0, 10.0):
        k = rising[np.argmax(zs[rising + 1] >= target)] + 1
        strip.append((f"dive {target:.0f}x", float(ts[k])))
    close = ts[zs >= zmax - 1e-6]
    strip.append(("closest", float(close[len(close) // 2])))
    falling = np.nonzero(np.diff(zs) < 0)[0]
    strip.append(("mid-return", float(ts[falling[len(falling) // 2]])))
    sdir = os.path.join(cache, "strip")
    os.makedirs(sdir, exist_ok=True)
    for name, t in strip:
        r.render(t, None, os.path.join(sdir, f"{name.replace(' ', '_')}.png"),
                 sub=1, shutter=0.0)
        lo, p1, hi, n, used = visible_spacing(stage, prov, size)
        rep.line("AC-23", f"{name}: t={t:.4f} zoom {stage.view[0]:.2f}x, visible levels {used}, "
                          f"spacing min {lo:.1f} (1st pct {p1:.1f}) max {hi:.1f} px over {n} quads",
                 lo >= MIN_SPACING and hi <= MAX_SPACING)
    worst_lo, worst_hi = 1e9, 0
    n = stage.frames
    for i in range(0, n, 5):
        t = i / n
        stage.pose(t)
        lo, p1, hi, _, _ = visible_spacing(stage, prov, size)
        worst_lo, worst_hi = min(worst_lo, lo), max(worst_hi, hi)
    rep.line("AC-23", f"every 5th frame of the loop: visible spacing {worst_lo:.1f}-{worst_hi:.1f} px",
             worst_lo >= MIN_SPACING and worst_hi <= MAX_SPACING)


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
    lo_s, hi_s = (16, 24) if stage.view_fn is not None else (6, 12)
    rep.line("AC-8", f"meta {meta['width']}x{meta['height']} {meta['fps']}fps {meta['frames']} frames "
                     f"{meta['duration']}s (allowed {lo_s}-{hi_s}s)",
             meta["width"] == meta["height"] == 1200 and meta["fps"] == 30 and lo_s <= meta["duration"] <= hi_s)
    for f in ("loop.mp4", "loop.webm"):
        sz = os.path.getsize(os.path.join(public, f))
        info = mp4.probe_mp4(os.path.join(public, f)) if f.endswith("mp4") else mp4.probe_webm(os.path.join(public, f))
        cap = 3_000_000 if stage.view_fn is not None else MAX_BYTES
        ok = sz < cap and info.get("width") == 1200 and info.get("height") == 1200 \
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
    lod_checks(stage, r, rep, size, cache)
    if stage.view_fn is not None:  # widths at the closest zoom too: constant in pixels
        ts = np.linspace(0, 1, 2001)[:-1]
        tz = ts[int(np.argmax([stage.view_at(t)[0] for t in ts]))]
        close, _ = r.render(float(tz))
        print(f"[AC-4] at zoom {stage.view[0]:.2f}x:")
        line_measure(stage, r, close, rep, size)
    rendered_framing(os.path.join(cache, "render_stats.json"), size, rep)
    outputs(rep, a.public, a.slug, stage)
    print(f"CHECK {a.slug}: {'FAIL ' + ', '.join(sorted(set(rep.fails))) if rep.fails else 'all checks passed'}")
    return 1 if rep.fails else 0
