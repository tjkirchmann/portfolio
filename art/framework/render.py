"""Frame rendering: pose -> depth pass -> line mesh -> EEVEE at 2x -> Lanczos -> master +
over-black."""
import os
import time

import bpy
import numpy as np

from . import camera as cammod, post, scene as scenemod
from .lines import LineRenderer

QUALITY = {
    # delivery size, render multiplier, samples, line width at delivery (px), filter (render px)
    "final": dict(size=1200, mult=2, samples=64, line_px=1.25, filter_px=1.0),
    "preview": dict(size=600, mult=2, samples=16, line_px=1.25, filter_px=1.0),
}


def depth_material():
    """Emission = (distance from the camera - d0) * k, for the depth pass. EEVEE's film is
    half float, so d0 and k are set per frame to spread the visible depth range over [0, 1]."""
    mat = bpy.data.materials.new("depth")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    cd = nt.nodes.new("ShaderNodeCameraData")
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.name = "d0"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.name = "k"
    nt.links.new(cd.outputs["View Z Depth"], sub.inputs[0])
    nt.links.new(sub.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


class Renderer:
    def __init__(self, stage, quality="final", tmp_dir=None, back_dim=True):
        q = QUALITY[quality]
        self.q = q
        self.stage = stage
        self.size = q["size"]
        self.res = q["size"] * q["mult"]
        scenemod.render_settings(stage.scene, self.res, q["samples"], q["filter_px"])
        self.lines = LineRenderer(stage.scene, stage.cam, stage.objects, self.res,
                                  q["line_px"] * q["mult"])
        self.lines.depth_range = stage.depth_range
        self.tmp = tmp_dir
        os.makedirs(tmp_dir, exist_ok=True)
        self.back_dim = back_dim
        self.depth_mat = depth_material()
        self.depth_res = q["size"] // 2

    def depth_pass(self):
        """Render the real meshes' distance-from-camera at depth_res (1 sample, no filter)."""
        sc = self.stage.scene
        r = sc.render
        vl = bpy.context.view_layer
        for o in self.stage.objects:
            o.hide_render = False
        self.lines.obj.hide_render = True
        vl.material_override = self.depth_mat
        r.resolution_x = r.resolution_y = self.depth_res
        old_f, old_s = r.filter_size, sc.eevee.taa_render_samples
        r.filter_size = 0.0
        sc.eevee.taa_render_samples = 1
        exr = os.path.join(self.tmp, "depth.exr")
        r.filepath = exr
        r.image_settings.file_format = "OPEN_EXR"
        r.image_settings.color_depth = "32"
        r.image_settings.exr_codec = "ZIP"
        # visible depth range -> [0, 1]
        P = self.stage.world_points()
        vx, vy = self.lines.view_xy(P)
        vis = (np.abs(vx) < 0.6) & (np.abs(vy) < 0.6)
        dist = cammod.DISTANCE - P[vis] @ self.lines.Z if vis.any() else np.array([40.0, 60.0])
        d0 = float(dist.min()) - 0.05
        span = float(dist.max() - dist.min()) + 0.1
        nt = self.depth_mat.node_tree
        nt.nodes["d0"].inputs[1].default_value = d0
        nt.nodes["k"].inputs[1].default_value = 1.0 / span
        bpy.ops.render.render(write_still=True)
        raw = post.load_exr(exr)
        D = np.where(raw > 0, raw * span + d0, 0.0)
        for o in self.stage.objects:
            o.hide_render = True
        self.lines.obj.hide_render = False
        vl.material_override = None
        r.resolution_x = r.resolution_y = self.res
        r.filter_size, sc.eevee.taa_render_samples = old_f, old_s
        self.lines.set_depth_map(D)

    def tiles_pass(self, samples):
        """Life tiles: the subject's own meshes with their metallic material, RGBA."""
        sc = self.stage.scene
        r = sc.render
        for o in self.stage.objects:
            o.hide_render = False
        self.lines.obj.hide_render = True
        r.image_settings.color_mode = "RGBA"
        sc.eevee.taa_render_samples = samples
        exr = os.path.join(self.tmp, "tiles.exr")
        r.filepath = exr
        bpy.ops.render.render(write_still=True)
        for o in self.stage.objects:
            o.hide_render = True
        self.lines.obj.hide_render = False
        r.image_settings.color_mode = "RGB"
        return post.load_exr_rgba(exr)

    def render_linear(self, t, samples=None):
        """One pose at phase t -> 2x linear image (and life tiles if any)."""
        self.stage.pose(t)
        self.lines.view = self.stage.view
        sc = self.stage.scene
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.image_settings.color_depth = "32"
        tm = [time.time()]
        if self.back_dim:
            self.depth_pass()
        tm.append(time.time())
        self.tiles = self.tiles_pass(samples or self.q["samples"]) if self.stage.life else None
        tm.append(time.time())
        info = self.lines.update(back_dim=self.back_dim)
        tm.append(time.time())
        sc.eevee.taa_render_samples = samples or self.q["samples"]
        exr = os.path.join(self.tmp, "render.exr")
        sc.render.filepath = exr
        bpy.ops.render.render(write_still=True)
        sc.eevee.taa_render_samples = self.q["samples"]
        img = post.load_exr(exr)
        tm.append(time.time())
        info["timing"] = dict(zip(("depth", "tiles", "lines_build", "lines_render"),
                                  [round(b - a, 2) for a, b in zip(tm, tm[1:])]))
        return img, info

    def render(self, t, master_path=None, black_path=None, sub=1, shutter=0.0):
        """Render phase t. With sub > 1, average `sub` poses spread over `shutter` (in t
        units) in linear light: motion blur for fast camera moves. The samples are split
        across the sub-frames so the total stays about the same."""
        t0 = time.time()
        if sub <= 1:
            lin, info = self.render_linear(t)
            tiles = self.tiles
        else:
            tiles = None
            per = max(8, self.q["samples"] // sub)
            lin = None
            for k in range(sub):
                tk = t + shutter * ((k + 0.5) / sub - 0.5)
                img, info = self.render_linear(tk, per)
                lin = img if lin is None else lin + img
            lin /= sub
            self.stage.pose(t)
        disp, stats = post.finish_frame(lin, master_path, black_path, tiles)
        stats.update(info)
        stats["sub"] = sub
        stats["zoom"] = round(self.stage.view[0], 4)
        stats["secs"] = round(time.time() - t0, 2)
        return disp, stats
