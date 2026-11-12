import bpy,sys,json
from pathlib import Path
job=Path(sys.argv[sys.argv.index('--')+1]);rig=bpy.data.objects['Armature'];samples=[]
for f in range(78,187):
    bpy.context.scene.frame_set(f);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());samples.append({n:list(e.matrix_world@e.pose.bones[n].matrix.translation) for n in ('Foot.L','Foot.R')})
(job/'baseline-feet.json').write_text(json.dumps({'job':bpy.data.filepath,'samples':samples,'frames':[78,186]},indent=2))
