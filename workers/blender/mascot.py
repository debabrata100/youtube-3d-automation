"""Original Pebble mascot: weighted rigid parts with overlapping rounded joints."""
import bpy
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from character import generate, curves

PALETTE={'teal':(.025,.42,.42,1),'cream':(1,.78,.39,1),'white':(.98,.98,.92,1),'ink':(.012,.028,.045,1),'coral':(.9,.19,.12,1)}

def material(color):
    name='Pebble.'+color
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=PALETTE[color]
    shader.inputs['Roughness'].default_value=.48
    return mat

def part(rig,name,location,scale,color,bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=location)
    obj=bpy.context.object
    obj.name='Pebble.'+name
    obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(material(color))
    for polygon in obj.data.polygons: polygon.use_smooth=True
    obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
    obj.modifiers.new('Armature deformation','ARMATURE').object=rig
    obj.parent=rig
    return obj

def build(destination):
    generate(None)
    rig=bpy.data.objects['DemoRig']
    rig.name='PebbleRig'
    for obj in list(bpy.data.objects):
        if obj.type=='MESH': bpy.data.objects.remove(obj,do_unlink=True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.object.mode_set(mode='EDIT')
    controls={
        'face.mouth':(0,-.34,2.13), 'face.brow.L':(-.2,-.39,2.55), 'face.brow.R':(.2,-.39,2.55),
        'face.eye.L':(-.2,-.39,2.39),'face.eye.R':(.2,-.39,2.39),
        'face.pupil.L':(-.2,-.49,2.39),'face.pupil.R':(.2,-.49,2.39),
    }
    for name,point in controls.items():
        bone=rig.data.edit_bones.new(name)
        bone.head=point;bone.tail=(point[0],point[1],point[2]+.1)
        bone.parent=rig.data.edit_bones['head']
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones: bone.rotation_mode='XYZ'
    part(rig,'Body',(0,0,1.48),(.49,.32,.62),'teal','torso')
    part(rig,'Belly',(0,-.275,1.46),(.33,.08,.4),'cream','torso')
    part(rig,'Head',(0,0,2.32),(.57,.4,.53),'cream','head')
    part(rig,'Crest',(0,.03,2.82),(.16,.17,.23),'coral','head')
    for side,x in [('L',-.48),('R',.48)]:
        bone='arm.'+side
        part(rig,'Shoulder.'+side,(x,0,1.84),(.2,.22,.23),'teal',bone)
        part(rig,'Arm.'+side,(x,0,1.43),(.17,.19,.46),'teal',bone)
        part(rig,'Hand.'+side,(x,-.02,.99),(.21,.2,.22),'cream',bone)
        part(rig,'Leg.'+side,(x/2,0,.61),(.21,.23,.49),'teal','leg.'+side)
        part(rig,'Foot.'+side,(x/2,-.12,.16),(.25,.36,.16),'coral','leg.'+side)
        eyeX=x/2.4
        part(rig,'Eye.'+side,(eyeX,-.375,2.4),(.155,.095,.18),'white','face.eye.'+side)
        part(rig,'Pupil.'+side,(eyeX,-.464,2.4),(.07,.032,.09),'ink','face.pupil.'+side)
        part(rig,'Glint.'+side,(eyeX-.02,-.492,2.435),(.022,.014,.026),'white','face.pupil.'+side)
        part(rig,'Brow.'+side,(eyeX,-.365,2.64),(.15,.05,.035),'teal','face.brow.'+side)
    part(rig,'Nose',(0,-.422,2.27),(.095,.11,.075),'coral','head')
    # A shallow U curve made from connected beads, all deformed by mouth control.
    for i in range(17):
        x=-.22+i*.0275
        z=2.12+.035*(x/.22)**2
        part(rig,'Mouth.%02d'%i,(x,-.354,z),(.021,.025,.018),'ink','face.mouth')
    # Keep legacy clips available but give mascot locomotion a stable cycle rate.
    for name in ('idle','walk','run','jump','wave'):
        bpy.data.actions['demo.'+name+'.v1'].name='pebble.'+name+'.v2'
    wave=bpy.data.actions['pebble.wave.v2']
    for curve in curves(wave,wave.slots[0]):
        if curve.data_path == 'pose.bones[\"arm.R\"].rotation_euler' and curve.array_index==2:
            for key in curve.keyframe_points: key.co.y *= -1
    rig.animation_data_create()
    for kind in ('turn','look_at'):
        action=bpy.data.actions.new('pebble.'+kind+'.v2');action.use_fake_user=True
        rig.animation_data.action=action
        for frame,value in [(1,0),(13,.45 if kind=='turn' else -.22),(25,0)]:
            for bone in ('root','head'):
                rig.pose.bones[bone].rotation_euler=(0,value if bone=='root' and kind=='turn' else 0,value if bone=='head' else 0)
                rig.pose.bones[bone].keyframe_insert('rotation_euler',frame=frame)
        for curve in curves(action,rig.animation_data.action_slot):
            for key in curve.keyframe_points: key.interpolation='BEZIER'
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.rotation_euler=(0,0,0);bone.location=(0,0,0);bone.scale=(1,1,1)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))

if __name__=='__main__': build(sys.argv[sys.argv.index('--')+1])
