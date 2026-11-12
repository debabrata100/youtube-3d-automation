"""Read-only saved-scene integration checks; no renders."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from wolf_native import points,mesh_delta,blocked_drivers
from bpy_extras.object_utils import world_to_camera_view
job=Path(sys.argv[sys.argv.index('--')+1]);report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene
assert scene.frame_end==360 and scene.render.fps==24
assert scene.render.filepath==str(job/'frames'/'frame_')
rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];motion=bpy.data.objects['CharacterMotion']
scene.frame_set(1);assert (motion.location-Vector((-1.5,0,0))).length<.001
scene.frame_set(72);assert abs(motion.rotation_euler.z-math.pi/2)<.001
scene.frame_set(192);assert (motion.location-Vector((1.5,0,0))).length<.001
scene.frame_set(360);assert abs(motion.rotation_euler.z-math.atan2(-1.5,10))<.001
assert mesh_delta(points(body,110),points(body,140))['maxPairDistanceChange']>.01
track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.Wave')
# At the same final frame, disabling the completed gesture must not change idle geometry.
a=points(body,330);track.mute=True;b=points(body,330);assert mesh_delta(a,b)['max']<1e-5;track.mute=False
scene.frame_set(277);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());raised=e.pose.bones['FK_Hand.R'].matrix.translation.copy()
track.mute=True;points(body,277);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());rest=e.pose.bones['FK_Hand.R'].matrix.translation
assert (raised-rest).length>.2;track.mute=False
previous=None;max_step=0;roots=[]
for frame in range(1,361):
 pts=points(body,frame)
 assert min(p.z for p in pts)>=.014
 for p in pts[::max(1,len(pts)//128)]:
  uv=world_to_camera_view(scene,scene.camera,p);assert .02<uv.x<.98 and .02<uv.y<.98 and uv.z>0
 evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());roots.append(evaluated.pose.bones['Root'].matrix.translation.copy())
 now=motion.location.copy()
 if previous is not None:max_step=max(max_step,(now-previous).length)
 previous=now
assert max_step<.05,'Unexpected root discontinuity'
assert max((p-roots[0]).length for p in roots)<.0001,'Unexpected native local Root drift'
blocked_drivers([rig,body]);print('CONTROLLER_SAVE_RELOAD_TESTS_PASSED',max_step)
from motion_utils import camera_preset,transition_camera,shortest
from mathutils import Quaternion
assert abs(shortest(math.radians(350),math.radians(10))-math.radians(370))<1e-6
scene.frame_set(360);pts=points(body,360)
box=([min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)])
full=scene.camera.data.ortho_scale
camera_preset(scene,box,'medium');medium=scene.camera.data.ortho_scale
camera_preset(scene,box,'close_up');close=scene.camera.data.ortho_scale
assert close<medium<full
camera=scene.camera;start=camera.location.copy();target=start+Vector((1,0,0))
transition_camera(camera,target,camera.rotation_euler.to_quaternion(),camera.data.ortho_scale,1,25)
scene.frame_set(25);assert (camera.location-target).length<1e-5
print('CAMERA_PRESETS_AND_TRANSITION_HELPER_PASSED')
