import bpy,sys,json,math,hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
sys.path.insert(0,str(Path(__file__).resolve().parent))
import wolf_native as native
job=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene
rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];motion=bpy.data.objects['CharacterMotion']
assert scene.frame_end==360 and scene.render.fps==24
scene.frame_set(1);assert (motion.location-Vector((-1.5,0,0))).length<.001
scene.frame_set(360);assert (motion.location-Vector((1.5,0,0))).length<.001
assert abs(motion.rotation_euler.z)<.001
for name in ['Wolf.Controller.Wave.v1','Wolf.Controller.Wave.v2','Wolf.Controller.StanceCorrection.v1']:assert name in bpy.data.actions
wave=bpy.data.actions['Wolf.Controller.Wave.v2'];bag=action_get_channelbag_for_slot(wave,wave.slots[0])
assert all(any(n in c.data_path for n in ['FK_UpperArm.R','FK_Forearm.R','FK_Hand.R']) for c in bag.fcurves)
track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.Wave')
a=native.points(body,330);track.mute=True;b=native.points(body,330);track.mute=False
assert native.mesh_delta(a,b)['max']<1e-5
quality=report['animationQuality'];paired=quality['footContact']['pairedPhase3Comparison']
assert paired['afterSameBaselineMasks']['meanMetersPerSecond']<paired['before']['meanMetersPerSecond']
assert quality['footContact']['maxLegSegmentLengthRatio']<=1.051
assert quality['footContact']['verifiedMaxLegLengthRatio']<=1.051
assert quality['camera']['intentionalCutFrames']==[193]
assert all(not s['framingFailures'] and s['framesChecked']==s['endFrame']-s['startFrame']+1 for s in quality['camera']['shots'])
assert quality['camera']['maxContinuousCameraStepMeters']<.1
for frame in [1,72,132,192,193,240,241,276,313,360]:
    assert min(p.z for p in native.points(body,frame))>=.014
native.blocked_drivers([rig,body]);assert not bpy.context.preferences.filepaths.use_scripts_auto_execute
# Compare original native curve data with newly appended source Action copies, not just names.
names=['01-Idle(60)','02-Walk (42)']
def digest(action):
    values=[]
    for slot in action.slots:
        bag=action_get_channelbag_for_slot(action,slot)
        for c in bag.fcurves if bag else []:values.append((c.data_path,c.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points]))
    return hashlib.sha256(repr(values).encode()).hexdigest()
original={n:digest(bpy.data.actions[n]) for n in names}
with bpy.data.libraries.load(report['source'],link=False) as (source,destination):destination.actions=list(names)
for n,action in zip(names,destination.actions):assert original[n]==digest(action),'Native Action data changed'
print('POLISH_RELOAD_AND_NATIVE_ACTION_INTEGRITY_PASSED')
# Exercise a nontrivial wide-to-medium smooth transition separately from the demo's deliberate cut.
from cinematic_camera import schedule as schedule_camera
scene.frame_end=48
result=schedule_camera(scene,body,motion,[{'start':0,'end':1,'preset':'wide','target':'wolf-warrior-native','transition':'cut','transitionFrames':0},{'start':1,'end':2,'preset':'medium','target':'wolf-warrior-native','transition':'smooth','transitionFrames':24}])
scene.frame_set(24);wide=scene.camera.data.ortho_scale
scene.frame_set(25);first=scene.camera.data.ortho_scale
scene.frame_set(48);medium=scene.camera.data.ortho_scale
assert medium<first<wide
assert result['intentionalCutFrames']==[]
print('CINEMATIC_SMOOTH_TRANSITION_PASSED')
