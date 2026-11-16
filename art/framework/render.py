"""Frame rendering: pose -> depth pass -> line mesh -> EEVEE at 2x -> Lanczos -> master +
over-black."""
import os
import time

import bpy

from . import post, scene as scenemod
from .lines import LineRenderer

QUALITY = {
    # delivery size, render multiplier, samples, line width at delivery (px), filter (render px)
    "final": dict(size=1200, mult=2, samples=64, line_px=1.25, filter_px=1.0),
    "preview": dict(size=600, mult=2, samples=16, line_px=1.25, filter_px=1.0),
}


def depth_material():
    """Emission = distance from the camera / 100, for the depth pass."""
    mat = bpy.data.materials.new("depth")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    cd = nt.nodes.new("ShaderNodeCameraData")
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.01
    nt.links.new(cd.outputs["View Z Depth"], mul.inputs[0])
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
        bpy.ops.render.render(write_still=True)
        D = post.load_exr(exr) * 100.0
        for o in self.stage.objects:
            o.hide_render = True
        self.lines.obj.hide_render = False
        vl.material_override = None
        r.resolution_x = r.resolution_y = self.res
        r.filter_size, sc.eevee.taa_render_samples = old_f, old_s
        self.lines.set_depth_map(D)

    def render(self, t, master_path=None, black_path=None):
        t0 = time.time()
        self.stage.pose(t)
        sc = self.stage.scene
        sc.render.image_settings.file_format = "OPEN_EXR"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.image_settings.color_depth = "32"
        if self.back_dim:
            self.depth_pass()
        info = self.lines.update(back_dim=self.back_dim)
        exr = os.path.join(self.tmp, "render.exr")
        sc.render.filepath = exr
        bpy.ops.render.render(write_still=True)
        lin = post.load_exr(exr)
        disp, stats = post.finish_frame(lin, master_path, black_path)
        stats.update(info)
        stats["secs"] = round(time.time() - t0, 2)
        return disp, stats
