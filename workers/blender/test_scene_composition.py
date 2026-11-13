import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scene_composition import verify
job=Path(sys.argv[sys.argv.index('--')+1]);execution=json.loads((job/'scene-plan.json').read_text())
result=verify(job,execution,True,write_report=False)
assert result['multiCharacter']['independentArmatures']
assert result['multiCharacter']['independentAnimationState']
assert len(result['multiCharacter']['isolationProbes'])==2
# Camera selection is independent from whole-scene coverage; these changes stay in memory.
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from cinematic_camera import schedule_multi
from cinematic_camera import frame_projector
from scene_composition import instances
scene=bpy.context.scene;characters=instances(execution['scene']);bodies={n:c['body'] for n,c in characters.items()}
for frame in [1,144,324,396,480]:
 scene.frame_set(frame);scene.view_layers[0].update();project=frame_projector(scene,scene.camera)
 for point in [Vector((-3,0,0)),Vector((1,1,3)),Vector((0,-2,1))]:
  assert (project(point)-world_to_camera_view(scene,scene.camera,point)).length<1e-6
shot={'start':0,'end':1,'type':'medium','subjects':['wolf-a'],'transition':'cut'}
schedule_multi(scene,bodies,[shot]);scene.frame_set(12);scene.view_layers[0].update()
other=characters['wolf-b']['motion'].location+Vector((0,0,1.5))
assert world_to_camera_view(scene,scene.camera,other).x>1,'Focused shot should not require the other character in frame'
schedule_multi(scene,bodies,[shot],[0,-15,0]);scene.frame_set(12)
assert abs(scene.camera.location.x)<1e-6 and abs(scene.camera.location.y+15)<1e-6
print('MULTI_CHARACTER_RELOAD_ISOLATION_AND_CAMERA_TESTS_PASSED')
