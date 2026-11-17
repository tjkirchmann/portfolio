# Throwaway stacked-alpha clip for public/art/_placeholder-stacked/ (Amendment 8 contract).
# Top half: light lines on black, hidden behind the solid body. Bottom half: white matte.
# Usage: Blender -b --factory-startup --python scripts/placeholder-stacked.py -- <outdir> <png|mp4|webm>
import bpy, math, sys, os

OUT, KIND = sys.argv[sys.argv.index('--') + 1:][:2]
W, FPS, FRAMES = 480, 24, 96
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def body(z, wire):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(0, 0, z))
    solid = bpy.context.active_object
    solid.color = (0, 0, 0, 1) if wire else (1, 1, 1, 1)
    # a wave on the surface so it reads as moving
    tex = bpy.data.textures.new('wave', 'WOOD')
    tex.wood_type = 'BANDNOISE'; tex.noise_scale = 0.4
    d = solid.modifiers.new('d', 'DISPLACE'); d.texture = tex; d.strength = 0.12
    objs = [solid]
    if wire:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.006, location=(0, 0, z))
        lines = bpy.context.active_object
        d2 = lines.modifiers.new('d', 'DISPLACE'); d2.texture = tex; d2.strength = 0.12
        m = lines.modifiers.new('w', 'WIREFRAME'); m.thickness = 0.014; m.use_replace = True
        lines.color = (0.86, 0.9, 0.87, 1)
        objs.append(lines)
    for o in objs:
        o.rotation_mode = 'XYZ'
        o.rotation_euler = (math.radians(20), 0, 0)
        o.keyframe_insert('rotation_euler', index=2, frame=1)
        o.rotation_euler[2] = math.radians(360 / 5)  # icosphere symmetry: seamless loop
        o.keyframe_insert('rotation_euler', index=2, frame=FRAMES + 1)
        ad = o.animation_data.action
        try:
            curves = list(ad.fcurves)
        except AttributeError:
            curves = [fc for layer in ad.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
        for fc in curves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

body(1.25, True)    # top: picture
body(-1.25, False)  # bottom: matte

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 5.0
cam.location = (0, -10, 0); cam.rotation_euler = (math.radians(90), 0, 0)

sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'; sh.color_type = 'OBJECT'
try:
    sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
except Exception:
    pass
try:
    sc.display.render_aa = '16'
except Exception:
    pass
w = bpy.data.worlds.new('w'); sc.world = w; w.color = (0, 0, 0)
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = W; sc.render.resolution_y = 2 * W; sc.render.resolution_percentage = 100
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, FRAMES
im = sc.render.image_settings
if KIND == 'png':
    sc.frame_set(1); im.file_format = 'PNG'; im.color_mode = 'RGB'
    sc.render.filepath = os.path.join(OUT, 'frame1.png')
    bpy.ops.render.render(write_still=True)
else:
    try:
        im.media_type = 'VIDEO'
    except Exception:
        pass
    im.file_format = 'FFMPEG'
    ff = sc.render.ffmpeg
    if KIND == 'mp4':
        ff.format = 'MPEG4'; ff.codec = 'H264'; ff.constant_rate_factor = 'HIGH'
    else:
        ff.format = 'WEBM'; ff.codec = 'WEBM'; ff.constant_rate_factor = 'NONE'; ff.video_bitrate = 1400; ff.maxrate = 1800; ff.minrate = 0
    ff.gopsize = 24; ff.audio_codec = 'NONE'
    sc.render.use_file_extension = False
    sc.render.filepath = os.path.join(OUT, 'loop.' + KIND)
    bpy.ops.render.render(animation=True)
print('STACKED done', KIND)
