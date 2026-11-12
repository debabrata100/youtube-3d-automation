import bpy
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from import_asset import inspect_asset
from character import curves
job=Path(sys.argv[sys.argv.index('--')+1])
plan=json.loads((job/'plan.json').read_text())
scene=bpy.context.scene
rig=bpy.data.objects['PebbleRig'];root=bpy.data.objects['CharacterRoot']
assert scene.frame_end==240 and scene.render.fps==24
assert scene.render.filepath==str(job/'frames'/'frame_')
for name in ('Pebble.Head','Pebble.Hand.L','Pebble.Foot.R','Pebble.Eye.L','Pebble.Pupil.R','Pebble.Nose','Pebble.Mouth.00'):
    obj=bpy.data.objects[name]
    assert any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers)
tracks=rig.animation_data.nla_tracks
assert any(t.name=='IndependentFacialControls' for t in tracks)
assert any(t.name=='Body.walk' for t in tracks) and any(t.name=='Body.wave' for t in tracks)
for name,start,blend in [('walk',1,0),('look_at',89,8),('wave',115,6)]:
    strip=next(t for t in tracks if t.name=='Body.'+name).strips[0]
    assert strip.frame_start==start and strip.blend_in==blend
    assert strip.extrapolation=='HOLD_FORWARD' and strip.blend_out==0
face=next(t for t in tracks if t.name=='IndependentFacialControls').strips[0]
assert all(c.data_path.startswith('pose.bones["face.') for c in curves(face.action,face.action_slot))
def state(frame,bone):
    scene.frame_set(frame)
    evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return evaluated.pose.bones[bone].matrix.copy()
assert state(12,'leg.L')!=state(24,'leg.L')
assert state(165,'arm.R')!=state(190,'arm.R')
scene.frame_set(1);assert abs(root.location.x+3)<.001
scene.frame_set(96);assert root.location.length<.001
scene.frame_set(240);assert root.location.length<.001
scene.frame_set(120);assert rig.pose.bones['face.mouth'].scale.y>3
scene.frame_set(143);assert rig.pose.bones['face.eye.L'].scale.y<.1
assert rig.pose.bones['face.mouth'].scale.y>3, 'Blink reset smile'
body=state(180,'arm.R')
facetrack=next(t for t in tracks if t.name=='IndependentFacialControls')
facetrack.mute=True
assert body==state(180,'arm.R'), 'Face overwrote body'
facetrack.mute=False
for frame in range(1,241):
    scene.frame_set(frame)
    assert -3.01<=root.location.x<=.01
    deps=bpy.context.evaluated_depsgraph_get()
    for obj in rig.children:
        if obj.type=='MESH':
            evaluated=obj.evaluated_get(deps)
            mesh=evaluated.to_mesh()
            for v in mesh.vertices:
                p=evaluated.matrix_world@v.co
                assert -4.5<p.x<4.5 and -.4<p.z<4.3, (frame,obj.name,tuple(p))
            evaluated.to_mesh_clear()
print('MASCOT_SCENE_VALIDATION_PASSED')
