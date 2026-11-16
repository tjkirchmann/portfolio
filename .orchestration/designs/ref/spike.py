import bpy, bmesh, math, sys
from mathutils import Vector, Matrix
OUT=sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
M=0.25  # module
def gear(name,N,width=0.6,phase=0.0):
    rp=M*N/2; rr=rp-1.25*M; rt=rp+M
    bore=max(0.18,rp*0.22); hub=bore+0.22; rim=rr-0.28
    K=4; A=N*K
    radii=[bore,(bore+hub)/2,hub,hub+0.002]
    nweb=max(2,int((rim-hub)/0.34))
    radii+=[hub+(rim-hub)*i/nweb for i in range(1,nweb)]
    radii+=[rim,rim+0.002,(rim+rr)/2+0.001,rr]
    bm=bmesh.new(); grid=[]
    for r in radii:
        grid.append([bm.verts.new((r*math.cos(2*math.pi*j/A+phase),r*math.sin(2*math.pi*j/A+phase),0)) for j in range(A)])
    for i in range(len(radii)-1):
        for j in range(A):
            bm.faces.new((grid[i][j],grid[i][(j+1)%A],grid[i+1][(j+1)%A],grid[i+1][j]))
    # teeth: columns 2..6 of each period, two radial rows (pitch, tip) with narrowing
    for t in range(N):
        base=[grid[-1][(t*K+c)%A] for c in range(1,4)]
        c0=2*math.pi*(t*K+2)/A+phase
        prev=base
        for r,sh in((rp,0.8),(rt,0.42)):
            row=[]
            for c in range(1,4):
                a=c0+(2*math.pi*(c-2)/A)*sh
                row.append(bm.verts.new((r*math.cos(a),r*math.sin(a),0)))
            for q in range(2): bm.faces.new((prev[q],prev[q+1],row[q+1],row[q]))
            prev=row
    bm.normal_update()
    ext=bmesh.ops.extrude_face_region(bm,geom=bm.faces[:])
    top=[e for e in ext['geom'] if isinstance(e,bmesh.types.BMVert)]
    bmesh.ops.translate(bm,verts=top,vec=(0,0,width))
    # mid loop on walls
    walls=[e for e in bm.edges if abs(e.verts[0].co.z-e.verts[1].co.z)>width*0.9]
    bmesh.ops.subdivide_edges(bm,edges=walls,cuts=1)
    # profile: raised hub, recessed web
    for v in bm.verts:
        r=math.hypot(v.co.x,v.co.y); z=v.co.z
        if z>width*0.9 or z<width*0.1:
            s=1 if z>width/2 else -1
            if r<=hub+0.001: v.co.z+=s*0.18
            elif hub+0.0015<r<rim+0.001: v.co.z-=s*0.16
    for v in bm.verts: v.co.z-=width/2
    me=bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob=bpy.data.objects.new(name,me); return ob,rp
# gear train
g1,r1=gear('g1',24); g2,r2=gear('g2',16,phase=math.pi/16); g3,r3=gear('g3',32,phase=math.pi/32)
g1.location=(0,0,0); g2.location=(r1+r2,0,0)
ang=math.radians(115); g3.location=(math.cos(ang)*(r1+r3),math.sin(ang)*(r1+r3),0)
gears=[g1,g2,g3]
# camera
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.data.lens=85
ctr=Vector((0.9,1.6,0)); cam.location=ctr+Vector((14,-19,17))
d=ctr-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
fwd=d.normalized()
# material: emission dimmed by depth
mat=bpy.data.materials.new('line'); mat.use_nodes=True; nt=mat.node_tree; nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial'); em=nt.nodes.new('ShaderNodeEmission')
cd=nt.nodes.new('ShaderNodeCameraData'); mr=nt.nodes.new('ShaderNodeMapRange')
mr.inputs['From Min'].default_value=24; mr.inputs['From Max'].default_value=35
mr.inputs['To Min'].default_value=1.0; mr.inputs['To Max'].default_value=0.22
nt.links.new(cd.outputs['View Z Depth'],mr.inputs['Value']); nt.links.new(mr.outputs['Result'],em.inputs['Strength'])
em.inputs['Color'].default_value=(0.9,0.93,0.9,1); nt.links.new(em.outputs[0],out.inputs['Surface'])
# edges -> curve, radius proportional to depth => constant screen width
RES=1600; PX=1.3
sensor=cam.data.sensor_width; k=(PX/RES)*(sensor/cam.data.lens)/2  # world radius per unit depth
import bmesh as _b
def mk(name,strength):
    cu=bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.bevel_depth=1.0; cu.bevel_resolution=1
    m=mat.copy(); n=m.node_tree; mul=n.nodes.new('ShaderNodeMath'); mul.operation='MULTIPLY'; mul.inputs[1].default_value=strength
    e=[x for x in n.nodes if x.type=='EMISSION'][0]; r=[x for x in n.nodes if x.type=='MAP_RANGE'][0]
    n.links.new(r.outputs['Result'],mul.inputs[0]); n.links.new(mul.outputs[0],e.inputs['Strength'])
    ob=bpy.data.objects.new(name,cu); cu.materials.append(m); sc.collection.objects.link(ob); return cu
front=mk('front',1.0); back=mk('back',0.28); ne=0
for g in gears:
    mw=Matrix.Translation(g.location); bm=_b.new(); bm.from_mesh(g.data); bm.normal_update()
    for e in bm.edges:
        mid=mw@((e.verts[0].co+e.verts[1].co)/2); view=(cam.location-mid)
        vis=any(f.normal.dot(view)>0 for f in e.link_faces)
        sp=(front if vis else back).splines.new('POLY'); sp.points.add(1)
        for i,v in enumerate(e.verts):
            p=mw@v.co; depth=(p-cam.location).dot(fwd)
            sp.points[i].co=(p.x,p.y,p.z,1); sp.points[i].radius=k*depth
        ne+=1
    bm.free()
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(0,0,0,1)
for eng in('BLENDER_EEVEE','BLENDER_EEVEE_NEXT'):
    try: sc.render.engine=eng; break
    except Exception: pass
sc.eevee.taa_render_samples=64
sc.render.resolution_x=sc.render.resolution_y=RES; sc.render.filter_size=1.2
sc.view_settings.view_transform='Standard'
sc.render.image_settings.file_format='PNG'; sc.render.filepath=OUT
import time; t=time.time(); bpy.ops.render.render(write_still=True)
print('SPIKE edges',ne,'engine',sc.render.engine,'secs',round(time.time()-t,1))
