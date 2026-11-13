import bpy,json,sys,math,tempfile
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from bpy_extras.anim_utils import action_get_channelbag_for_slot
sys.path.insert(0,str(Path(__file__).resolve().parent))
import wolf_native as native
from performance_refinement import finalize_performance
job=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene;rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];motion=bpy.data.objects['CharacterMotion']
assert scene.frame_end==360 and scene.render.fps==24
scene.frame_set(360);assert (motion.location-Vector((1.5,0,0))).length<.001
for name in ['Wolf.Controller.Wave.v1','Wolf.Controller.Wave.v2','Wolf.Controller.Wave.v3','Wolf.Controller.StanceCorrection.v2']:assert name in bpy.data.actions
wave=bpy.data.actions['Wolf.Controller.Wave.v3'];slot=wave.slots[0];assert slot.target_id_type=='OBJECT'
bag=action_get_channelbag_for_slot(wave,slot)
assert all(len(c.keyframe_points)==73 and c.keyframe_points[0].co.x==0 and c.keyframe_points[-1].co.x==72 for c in bag.fcurves)
correction=bpy.data.actions['Wolf.Controller.StanceCorrection.v2']
for c in action_get_channelbag_for_slot(correction,correction.slots[0]).fcurves:
 assert abs(c.keyframe_points[0].co.y)<1e-7 and abs(c.keyframe_points[-1].co.y)<1e-7
 assert all(b.co.x-a.co.x==1 and math.isfinite(b.co.y) for a,b in zip(c.keyframe_points,c.keyframe_points[1:]))
assert all(any(n in c.data_path for n in ['FK_UpperArm.R','FK_Forearm.R','FK_Hand.R','FK_Spine_02']) for c in bag.fcurves)
curve=next(c for c in bag.fcurves if 'FK_Hand.R' in c.data_path and c.array_index==2)
values=[k.co.y for k in curve.keyframe_points if .38*72<=k.co.x<=.76*72 and abs(k.co.y)>1e-6]
signs=[1 if v>0 else -1 for v in values];assert sum(a!=b for a,b in zip(signs,signs[1:]))==3,'Expected two readable wrist cycles'
assert report['wave']['parameters']['anticipation']<.2 and report['wave']['parameters']['recovery']>.2
upper=next(c for c in bag.fcurves if 'FK_UpperArm.R' in c.data_path and c.array_index==0)
elbow=next(c for c in bag.fcurves if 'FK_Forearm.R' in c.data_path and c.array_index==0)
assert upper.evaluate(2)<0,'Anticipation must precede the raise'
assert abs(curve.evaluate(20))<1e-6 and abs(curve.evaluate(70))<1e-6
assert abs(upper.evaluate(68))<abs(upper.evaluate(50))
assert abs(elbow.evaluate(68))<abs(elbow.evaluate(50))
for c in bag.fcurves:assert abs(c.keyframe_points[0].co.y)<1e-7 and abs(c.keyframe_points[-1].co.y)<1e-7
track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.Wave')
a=native.points(body,330);track.mute=True;b=native.points(body,330);track.mute=False;assert native.mesh_delta(a,b)['max']<1e-5
assert report['animationQuality']['footContact']['maxSafetyGainStep']<=.0450001
assert report['animationQuality']['footContact']['maxLegSegmentLengthRatio']<=1.051
assert report['animationQuality']['camera']['intentionalCutFrames']==[193]
assert all(not s['framingFailures'] for s in report['animationQuality']['camera']['shots'])
assert report['wave']['oppositeArmRigLocalShift']<.035
assert report['animationQuality']['camera']['maxContinuousCameraStepMeters']<.03
for frame in [72,73,132,192,193,194,240,241,report['wave']['peakFrame'],312,313]:
 pts=native.points(body,frame);crop=report['animationQuality']['camera']['presets']['medium']['cropZ']
 region=pts if frame<=192 else [p for p in pts if p.z>=crop-.015]
 assert all(.015<uv.x<.985 and .015<uv.y<.985 and uv.z>0 for uv in [world_to_camera_view(scene,scene.camera,p) for p in region]),('Framing boundary',frame)
assert report['wave']['conservativeGeometry']['available']
assert not any(region['potentialOverlapFrames'] for region in report['wave']['conservativeGeometry']['regions'].values())
native.blocked_drivers([rig,body]);assert not bpy.context.preferences.filepaths.use_scripts_auto_execute
names=['01-Idle(60)','02-Walk (42)']
def data(action):
 return [(c.data_path,c.array_index,[tuple(k.co) for k in c.keyframe_points]) for s in action.slots for c in action_get_channelbag_for_slot(action,s).fcurves]
original={n:data(bpy.data.actions[n]) for n in names}
with bpy.data.libraries.load(report['source'],link=False) as (source,destination):destination.actions=list(names)
for n,action in zip(names,destination.actions):assert original[n]==data(action)
# The fallback produces no fabricated comparative values when a baseline is absent.
with tempfile.TemporaryDirectory(prefix='performance-no-baseline-') as directory:
 clone=json.loads(json.dumps(report));finalize_performance(Path(directory),clone)
 assert not clone['performanceComparison']['available'] and 'before' not in clone['performanceComparison']
print('PERFORMANCE_RELOAD_GESTURE_SAFETY_AND_MISSING_BASELINE_PASSED')
