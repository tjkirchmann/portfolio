# Renders the stand-in loop for public/art/_placeholder/.
# Usage: Blender -b --factory-startup --python scripts/placeholder-art.py -- <outdir> <kind>
#   kind = poster | mp4 | webm
# Not the real art pipeline (that lives in art/). Quick wireframe icosphere on a fixed iso camera.
import bpy, math, sys, os

args = sys.argv[sys.argv.index('--') + 1:]
OUT, KIND = args[0], args[1]
RES, FPS, FRAMES = 640, 24, 96

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def add_wire(op, name, **kw):
    op(**kw)
    ob = bpy.context.active_object
    ob.name = name
    m = ob.modifiers.new('wire', 'WIREFRAME')
    m.thickness = 0.012
    m.use_replace = True
    return ob

ico = add_wire(bpy.ops.mesh.primitive_ico_sphere_add, 'ico', subdivisions=2, radius=1.1)
ring = add_wire(bpy.ops.mesh.primitive_torus_add, 'ring', major_radius=1.7, minor_radius=0.08,
                major_segments=48, minor_segments=4)
ring.rotation_euler = (math.radians(70), 0, 0)

# subject turns once per loop; camera never moves
for ob in (ico, ring):
    ob.rotation_mode = 'XYZ'
    ob.keyframe_insert('rotation_euler', index=2, frame=1)
    r = list(ob.rotation_euler); r[2] += math.radians(360 if ob is ico else -360)
    ob.rotation_euler = r
    ob.keyframe_insert('rotation_euler', index=2, frame=FRAMES + 1)
    ad = ob.animation_data.action
    try:
        curves = list(ad.fcurves)
    except AttributeError:
        curves = [fc for layer in ad.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 4.4
cam.location = (8, -8, 8 * math.sqrt(2) * math.tan(math.radians(35.264)))
cam.rotation_euler = (math.radians(54.736), 0, math.radians(45))

sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'SINGLE'
sh.single_color = (0.85, 0.88, 0.85)
try:
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0, 0, 0)
except Exception:
    pass
try:
    sc.display.render_aa = '16'
except Exception:
    pass
w = bpy.data.worlds.new('w'); sc.world = w
w.color = (0, 0, 0)
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.film_transparent = False

im = sc.render.image_settings
if KIND == 'poster':
    sc.frame_set(1)
    im.file_format = 'PNG'
    im.color_mode = 'RGB'
    sc.render.filepath = os.path.join(OUT, 'poster.png')
    bpy.ops.render.render(write_still=True)
else:
    try:
        im.media_type = 'VIDEO'
    except Exception:
        pass
    im.file_format = 'FFMPEG'
    ff = sc.render.ffmpeg
    if KIND == 'mp4':
        ff.format = 'MPEG4'; ff.codec = 'H264'
    else:
        ff.format = 'WEBM'; ff.codec = 'WEBM'
    if KIND == 'mp4':
        ff.constant_rate_factor = 'LOW'
    else:
        # Blender's VP9 CRF presets come out large; a fixed bitrate keeps the stand-in small
        ff.constant_rate_factor = 'NONE'
        ff.video_bitrate = 900
        ff.maxrate = 1200
        ff.minrate = 0
    ff.gopsize = 24
    ff.audio_codec = 'NONE'
    sc.render.use_file_extension = False
    sc.render.filepath = os.path.join(OUT, 'loop.' + KIND)
    bpy.ops.render.render(animation=True)
print('PLACEHOLDER done', KIND)
