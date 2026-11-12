"""Blender-only negative import compatibility tests; no rendering."""
import bpy
import sys
import json
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from import_asset import inspect_asset
asset=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
def rejects(patch,message):
    clear();bad=deepcopy(asset);bad.update(patch)
    try: inspect_asset(bad)
    except ValueError as error:
        assert message in str(error),(message,str(error))
    else: raise AssertionError('Expected rejection: '+message)
rejects({'armature':'Absent'},'armature')
rejects({'normalization':{'scale':0,'rotationDegrees':[0,0,0]}},'scale')
rejects({'bones':['Absent']},'bones')
rejects({'meshes':['Absent']},'meshes')
rejects({'actions':{'walk':'Absent'}},'action')
rejects({'facialControls':{'blink':'Absent'}},'facial control')
clear();report=inspect_asset(asset);assert report['valid']
print('IMPORT_COMPATIBILITY_TESTS_PASSED')
from facial import apply_expressions
rig=bpy.data.objects[asset['armature']]
for name in ('neutral','smile','sad','surprised','blink','look_left','look_right'):
    rig.animation_data_clear();rig.animation_data_create()
    apply_expressions(rig,[{'name':name,'startFrame':1,'endFrame':11,'intensity':1}],24)
    bpy.context.scene.frame_set(1);bpy.context.scene.frame_set(6)
    if name=='smile': assert rig.pose.bones['face.mouth'].scale.y>3
    if name=='sad': assert rig.pose.bones['face.mouth'].scale.y<0
    if name=='surprised': assert rig.pose.bones['face.mouth'].scale.x<.5
    if name=='blink': assert rig.pose.bones['face.eye.R'].scale.y<.1
    if name=='look_left': assert rig.pose.bones['face.pupil.R'].location.x<0
    if name=='look_right': assert rig.pose.bones['face.pupil.R'].location.x>0
print('ALL_FACIAL_CONTROLS_TESTED')
rig.animation_data_clear();rig.animation_data_create()
apply_expressions(rig,[{'name':'blink','startFrame':1,'endFrame':11,'intensity':1},{'name':'look_left','startFrame':1,'endFrame':11,'intensity':1}],24)
bpy.context.scene.frame_set(1);bpy.context.scene.frame_set(6)
assert rig.pose.bones['face.pupil.L'].scale.y<.1
assert rig.pose.bones['face.pupil.L'].location.x<0, 'Blink reset gaze'
from lighting import configure
scene=bpy.context.scene
scene.world=bpy.data.worlds.new('TestWorld');scene.world.use_nodes=True
bpy.ops.object.camera_add();scene.camera=bpy.context.object
for preset,count in [('soft_studio',3),('sunny_outdoor',2),('neutral_preview',1)]:
    configure({'lighting':preset,'renderMode':'preview'})
    assert len([o for o in scene.objects if o.type=='LIGHT'])==count
    assert scene.eevee.taa_render_samples==8
configure({'lighting':'soft_studio','renderMode':'final'})
assert scene.eevee.taa_render_samples==32
print('FACIAL_CHANNEL_INDEPENDENCE_AND_LIGHTING_PRESETS_PASSED')
