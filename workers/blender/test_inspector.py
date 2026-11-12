"""No renders/network: generate original fixtures, round-trip actual importers."""
import bpy
import sys
import json
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from character import generate, BONES, curves
from inspect_character import inspect
output=Path(sys.argv[sys.argv.index('--')+1]);output.mkdir(parents=True,exist_ok=True)
generate(None)
rig=bpy.data.objects['DemoRig']
rig.name='ExternalRig'
for bone in list(rig.data.bones): bone.name='External_'+bone.name
# Unbound fake-user clips must have their paths updated explicitly in this fixture.
for action in bpy.data.actions:
    for slot in action.slots:
        for curve in curves(action,slot):
            for name in BONES:
                curve.data_path=curve.data_path.replace('pose.bones[\"'+name+'\"]','pose.bones[\"External_'+name+'\"]')
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
mesh.shape_key_add(name='Basis');blink=mesh.shape_key_add(name='Blink')
blink.data[0].co.z+=.03
rig.animation_data_create();rig.animation_data.action=bpy.data.actions['demo.walk.v1'];rig.animation_data.action_slot=rig.animation_data.action.slots[0]
bpy.context.scene.frame_end=25
bpy.ops.wm.save_as_mainfile(filepath=str(output/'original.blend'))
bpy.ops.export_scene.gltf(filepath=str(output/'original.glb'),export_format='GLB',export_animations=True)
rig.animation_data_create();rig.animation_data.action=bpy.data.actions['demo.walk.v1'];rig.animation_data.action_slot=rig.animation_data.action.slots[0]
bpy.ops.export_scene.fbx(filepath=str(output/'original.fbx'),add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False)
base={'targetRig':'demo-v1','boneMap':{n:'External_'+n for n in BONES},'actionMap':{},'heightMeters':{'min':.5,'max':4},'orientation':{'up':'Z','forward':'-Y'}}
def run(file,config):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return inspect(file,deepcopy(config))
for suffix in ('blend','glb','fbx'):
    file=output/('original.'+suffix)
    report=run(file,base)
    assert report['meshes'] and len(report['armatures'])==1,suffix
    assert report['materials'] and report['animations'],(suffix,len(report['materials']),len(report['animations']))
    assert report['facialControls']['shapeKeys'],suffix
    assert all(m['exists'] for m in report['requiredBoneMappings']),suffix
    assert not report['retargeting']['implemented'] and not report['animationReady']
    assert not any(i['severity']=='error' for i in report['issues']), (suffix,report['issues'])
    (output/(suffix+'-report.json')).write_text(json.dumps(report,indent=2))
original=output/'original.blend'
for patch,code in [
    ({'armature':'Missing'},'ARMATURE_SELECTION'),
    ({'boneMap':{**base['boneMap'],'head':'Missing'}},'MISSING_MAPPED_BONE'),
    ({'boneMap':{**base['boneMap'],'head':'External_root'}},'DUPLICATE_MAPPING'),
    ({'boneMap':{**base['boneMap'],'torso':'External_leg.L'}},'HIERARCHY_MISMATCH'),
    ({'heightMeters':{'min':10,'max':20}},'HEIGHT_OUT_OF_RANGE'),
    ({'orientation':{'up':'Y','forward':'Z'}},'ORIENTATION_MISMATCH'),
    ({'actionMap':{'walk':'Missing'}},'INCOMPATIBLE_ACTION'),
]:
    report=run(original,{**base,**patch})
    assert code in {i['code'] for i in report['issues']},(code,report)
report=run(original,{**base,'boneMap':{}});assert report['status']=='needs_mapping'
report=run(original,{**base,'actionMap':{'walk':'demo.walk.v1'}})
assert report['animationCompatibility']['existingLocalActionChannelChecksPassed']
# An actual missing rig, not only a selector mismatch.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add()
bpy.ops.wm.save_as_mainfile(filepath=str(output/'no-rig.blend'))
assert 'NO_ARMATURE' in {i['code'] for i in run(output/'no-rig.blend',base)['issues']}
# An invalid positive-height model scale, preserved in Blender fixture.
bpy.ops.wm.read_factory_settings(use_empty=True);generate(None)
bpy.data.objects['DemoRig'].scale.x=-1
bpy.ops.wm.save_as_mainfile(filepath=str(output/'negative-scale.blend'))
assert 'INVALID_SCALE' in {i['code'] for i in run(output/'negative-scale.blend',base)['issues']}
print('INSPECTOR_FIXTURE_TESTS_PASSED',output)
