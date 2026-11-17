"""The one camera. True isometric, orthographic, owned by the framework.

It looks along (-1, -1, -1) toward the origin from azimuth 45 (elevation 35.264 degrees),
Z up. A subject may pick one of the four diagonal azimuths and nothing else. The camera
is created once and never moves: subjects are scaled and centred to fit it.
"""
import math

import bpy
from mathutils import Vector

ELEVATION = math.degrees(math.atan(1 / math.sqrt(2)))  # 35.2644
AZIMUTHS = (45, 135, 225, 315)
ORTHO_SCALE = 10.0
DISTANCE = 50.0


def toward_camera(azimuth=45):
    """Unit vector from the origin toward the camera."""
    if azimuth not in AZIMUTHS:
        raise ValueError(f"azimuth must be one of {AZIMUTHS}, got {azimuth}")
    az, el = math.radians(azimuth), math.radians(ELEVATION)
    return Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))


def make_camera(scene, azimuth=45):
    d = toward_camera(azimuth)
    cam = bpy.data.objects.new("iso_camera", bpy.data.cameras.new("iso_camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ORTHO_SCALE
    cam.data.clip_start = 1.0
    cam.data.clip_end = 100.0
    cam.data.sensor_fit = "AUTO"
    cam.location = d * DISTANCE
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = d.to_track_quat("Z", "Y")
    bpy.context.view_layer.update()
    return cam


def basis(cam):
    """Camera right, up and toward-camera unit vectors in world space."""
    m = cam.matrix_world.to_3x3()
    return m.col[0].normalized(), m.col[1].normalized(), m.col[2].normalized()


def matrix_text(cam):
    m = cam.matrix_world
    rows = ["[" + ", ".join(f"{m[r][c]: .6f}" for c in range(4)) + "]" for r in range(4)]
    return (f"type={cam.data.type} ortho_scale={cam.data.ortho_scale} "
            f"elevation={ELEVATION:.4f}\n  " + "\n  ".join(rows))
