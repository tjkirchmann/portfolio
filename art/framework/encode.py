"""Video encoding with Blender's own FFmpeg (the system ffmpeg is not used).

The over-black PNG sequence is loaded into a throwaway sequencer scene and written as
H.264 MP4 (yuv420p, then rewritten faststart) and VP9 or AV1 WebM.
"""
import glob
import os

import bpy

from . import mp4

PROFILES = {
    "h264": dict(format="MPEG4", codec="H264", ext="mp4"),
    "vp9": dict(format="WEBM", codec="WEBM", ext="webm"),
    "av1": dict(format="WEBM", codec="AV1", ext="webm"),
    "av1mp4": dict(format="MPEG4", codec="AV1", ext="mp4"),
}


def encode(frames_dir, out_path, fps=30, profile="h264", crf=23, preset="BEST", gop=None, kbps=None):
    """Encode a PNG sequence. Quality by CRF, or by average bitrate when kbps is given."""
    files = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
    if not files:
        raise SystemExit(f"no frames in {frames_dir}")
    p = PROFILES[profile]
    sc = bpy.data.scenes.new("encode")
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.sequencer_colorspace_settings.name = "sRGB"
    ed = sc.sequence_editor_create()
    strips = ed.strips if hasattr(ed, "strips") else ed.sequences
    st = strips.new_image("frames", files[0], channel=1, frame_start=1)
    for f in files[1:]:
        st.elements.append(os.path.basename(f))
    img = bpy.data.images.load(files[0], check_existing=False)
    w, h = img.size
    bpy.data.images.remove(img)
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.fps, r.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = 1, len(files)
    r.image_settings.media_type = "VIDEO"
    r.image_settings.file_format = "FFMPEG"
    r.image_settings.color_mode = "RGB"
    ff = r.ffmpeg
    ff.format = p["format"]
    ff.codec = p["codec"]
    if kbps:
        ff.constant_rate_factor = "NONE"
        ff.video_bitrate = kbps
        ff.maxrate = int(kbps * 2)
        ff.buffersize = int(kbps * 2)
    else:
        ff.constant_rate_factor = "CUSTOM"
        ff.custom_constant_rate_factor = crf
    ff.ffmpeg_preset = preset
    ff.gopsize = gop or fps * 2
    ff.use_max_b_frames = False
    ff.audio_codec = "NONE"
    tmp = out_path + ".tmp"
    r.filepath = tmp
    r.use_file_extension = False
    if os.path.exists(tmp):
        os.remove(tmp)
    bpy.ops.render.render(animation=True, scene=sc.name)
    bpy.data.scenes.remove(sc)
    if p["ext"] == "mp4":
        mp4.faststart(tmp, out_path)
        os.remove(tmp)
    else:
        os.replace(tmp, out_path)
    return os.path.getsize(out_path)
