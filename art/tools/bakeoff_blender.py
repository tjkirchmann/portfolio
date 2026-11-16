"""Blender half of the bake-off: video encodes with Blender's FFmpeg, and frame decodes."""
import os
import sys

sys.dont_write_bytecode = True

import bpy

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ART)
from framework import encode  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
mode = argv[0]

if mode == "encode":
    black, out = argv[1], argv[2]
    # H.264 and VP9 are the delivered files (copied by bakeoff.py); AV1 is encoded here at a
    # bitrate in the same range so the comparison is at roughly equal size
    n = encode.encode(black, os.path.join(out, "loop_av1.webm"), 30, "av1", 34, "GOOD", kbps=900)
    print("ENC loop_av1.webm", n)
else:
    out, frame = argv[1], int(argv[2])
    for name, tag in (("loop_h264.mp4", "h264"), ("loop_vp9.webm", "vp9"), ("loop_av1.webm", "av1")):
        sc = bpy.data.scenes.new("dec_" + tag)
        sc.view_settings.view_transform = "Standard"
        ed = sc.sequence_editor_create()
        strips = ed.strips if hasattr(ed, "strips") else ed.sequences
        st = strips.new_movie(tag, os.path.join(out, name), channel=1, frame_start=1)
        sc.render.resolution_x, sc.render.resolution_y = 1200, 1200
        sc.render.resolution_percentage = 100
        sc.frame_current = frame
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        sc.render.filepath = os.path.join(out, "decoded", tag + ".png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        print("DEC", tag)
