"""Inspect saved rig, NLA slots, actual evaluated deformation, and root movement."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from character import curves
job = Path(sys.argv[sys.argv.index('--')+1])
plan = json.loads((job/'plan.json').read_text())
scene = bpy.context.scene
assert scene.render.filepath == str(job/'frames'/'frame_')
assert scene.frame_end == 120
if 'character' in plan:
    rig = bpy.data.objects['DemoRig']
    assert set(('head','torso','arm.L','arm.R','leg.L','leg.R','root')) <= set(rig.data.bones.keys())
    for name in ('idle','walk','run','jump','wave'):
        action = bpy.data.actions['demo.'+name+'.v1']
        assert action.slots and action.use_fake_user
        channels = list(curves(action,action.slots[0]))
        assert channels and any(c.keyframe_points for c in channels)
    strips = list(rig.animation_data.nla_tracks[0].strips)
    assert len(strips) == 2
    assert [s.name for s in strips] == ['walk','wave']
    for strip in strips:
        assert strip.action_slot and len(list(curves(strip.action,strip.action_slot))) > 0
    def snapshot(frame,bone):
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        evaluated = rig.evaluated_get(deps)
        return evaluated.pose.bones[bone].matrix.copy()
    assert snapshot(8,'leg.L') != snapshot(20,'leg.L'), 'Walk pose is static'
    assert snapshot(85,'arm.R') != snapshot(100,'arm.R'), 'Wave pose is static'
    obj = bpy.data.objects['Demo.arm.R']
    def vertices(frame):
        scene.frame_set(frame)
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        result = [v.co.copy() for v in mesh.vertices]
        evaluated.to_mesh_clear()
        return result
    assert vertices(85) != vertices(100), 'Mesh is not deforming'
    root = bpy.data.objects['CharacterRoot']
    scene.frame_set(1)
    assert (root.location-Vector((-3,0,0))).length < .001
    scene.frame_set(72)
    assert root.location.length < .001
    scene.frame_set(120)
    assert root.location.length < .001
else:
    ball=bpy.data.objects['AnimatedBall']
    scene.frame_set(1)
    assert abs(ball.location.x+3)<.001
    scene.frame_set(120)
    assert abs(ball.location.x-3)<.001
print('SCENE_VALIDATION_PASSED')
