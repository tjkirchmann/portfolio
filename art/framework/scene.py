"""Scene setup, subject loading and framing.

Framing never touches the camera. The subject's objects are parented to a root empty; the
framework samples the animation across the whole loop, measures the screen-space bounds and
sets the root's uniform scale and in-plane offset so the subject fills FILL of the frame.
"""
import importlib.util
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import camera as cammod

FILL = 0.78           # fraction of the frame's shorter side the loop bounds fill (AC-18)
FRAME_SAMPLES = 72    # phases sampled for framing and depth range


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    w = bpy.data.worlds.new("black")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0, 0, 0, 1)
    bg.inputs[1].default_value = 0.0
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0
    sc.view_settings.gamma = 1
    sc.render.film_transparent = False
    sc.render.use_motion_blur = False
    return sc


def load_subject(path):
    art_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if art_dir not in sys.path:
        sys.path.insert(0, art_dir)
    spec = importlib.util.spec_from_file_location("subject", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("build", "animate"):
        if not hasattr(mod, name):
            raise SystemExit(f"subject {path} must define {name}()")
    return mod


class Stage:
    """Subject + camera + root, ready to pose at any loop phase t."""

    def __init__(self, subject_path):
        self.scene = reset()
        self.subject = load_subject(subject_path)
        s = self.subject
        self.azimuth = getattr(s, "AZIMUTH", 45)
        self.seconds = float(getattr(s, "LOOP_SECONDS", 10))
        self.fps = 30
        self.frames = int(round(self.seconds * self.fps))
        if getattr(s, "mesh_source", None):
            raise SystemExit("mesh_source subjects are not supported yet (seam only)")
        self.cam = cammod.make_camera(self.scene, self.azimuth)
        self.root = bpy.data.objects.new("subject_root", None)
        self.scene.collection.objects.link(self.root)
        objs = s.build()
        self.objects = list(objs)
        for o in self.objects:
            if o.name not in self.scene.collection.objects:
                self.scene.collection.objects.link(o)
            if o.parent is None:
                o.parent = self.root
            o.hide_render = True
        self.X, self.Y, self.Z = (np.array(v) for v in cammod.basis(self.cam))
        self.fill = float(getattr(s, "FILL", FILL))
        self.view_fn = getattr(s, "view", None)
        self.cam_home = self.cam.location.copy()
        self.view = (1.0, 0.0, 0.0)
        self.frame_to_bounds()

    def pose(self, t):
        self.subject.animate(t)
        bpy.context.view_layer.update()
        self.view = self.view_at(t)
        z, cx, cy = self.view
        # zoom and pan only: same orthographic projection, same isometric angles
        self.cam.data.ortho_scale = cammod.ORTHO_SCALE / z
        self.cam.location = self.cam_home + Vector(cx * self.X + cy * self.Y)
        bpy.context.view_layer.update()

    def view_at(self, t):
        """(zoom, pan x, pan y) for phase t. A subject's `view(t)` returns (zoom, focus):
        the framework zooms about the focus point (subject space), so it drifts to the frame
        centre as the zoom grows, like a satellite view diving onto a map."""
        if self.view_fn is None:
            return (1.0, 0.0, 0.0)
        z, focus = self.view_fn(t)
        if focus is None or z == 1.0:
            return (float(z), 0.0, 0.0)
        Fw = np.array(self.root.matrix_world @ Vector(focus))
        k = 1.0 - 1.0 / z
        return (float(z), float(Fw @ self.X) * k, float(Fw @ self.Y) * k)

    def world_points(self):
        out = []
        for o in self.objects:
            me = o.data
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            m = np.array(o.matrix_world)
            out.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        return np.concatenate(out)

    def frame_to_bounds(self):
        self.root.matrix_world = Matrix.Identity(4)
        xs, ys, ds = [], [], []
        for i in range(FRAME_SAMPLES):
            self.pose(i / FRAME_SAMPLES)
            P = self.world_points()
            xs += [P @ self.X]
            ys += [P @ self.Y]
        x = np.concatenate(xs)
        y = np.concatenate(ys)
        cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
        ext = max(x.max() - x.min(), y.max() - y.min())
        k = self.fill * cammod.ORTHO_SCALE / ext
        off = -k * (cx * self.X + cy * self.Y)
        self.root.matrix_world = Matrix.Translation(Vector(off)) @ Matrix.Scale(k, 4)
        self.scale = k
        for i in range(FRAME_SAMPLES):
            self.pose(i / FRAME_SAMPLES)
            ds.append(self.world_points() @ self.Z)
        d = np.concatenate(ds)
        self.depth_range = (float(d.min()), float(d.max()))

    def view_speed(self, t, dt, size):
        """Largest screen motion (delivery px per frame) caused by the camera's zoom and pan
        alone, measured at the frame corners and centre."""
        if self.view_fn is None:
            return 0.0
        z0, cx0, cy0 = self.view_at(t)
        z1, cx1, cy1 = self.view_at(t + dt)
        k = cammod.ORTHO_SCALE
        best = 0.0
        for sx, sy in ((0, 0), (-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)):
            wx, wy = cx0 + sx * k / z0, cy0 + sy * k / z0  # world point under this screen spot
            nx, ny = (wx - cx1) * z1 / k, (wy - cy1) * z1 / k
            best = max(best, math.hypot(nx - sx, ny - sy) * size)
        return best

    def to_px(self, P, size, view=None):
        """World points -> delivery pixel coords (x right, y down) under the current view."""
        z, cx, cy = view or self.view
        sx = (P @ self.X - cx) * z / cammod.ORTHO_SCALE * size + size / 2
        sy = size / 2 - (P @ self.Y - cy) * z / cammod.ORTHO_SCALE * size
        return np.stack([sx, sy], 1)

    def px_per_unit(self, size):
        return size / cammod.ORTHO_SCALE * self.view[0]


def render_settings(scene, res, samples, filter_px):
    r = scene.render
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    r.filter_size = filter_px
    scene.eevee.taa_render_samples = samples
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "32"
    r.image_settings.exr_codec = "ZIP"
    r.image_settings.color_mode = "RGB"
    r.use_file_extension = True
