"""Isolated source-rig experiments; never edits the demo or original asset."""
import bpy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from inspect_character import import_file
from wolf_native import points,mesh_delta,blocked_drivers
job=Path(sys.argv[sys.argv.index('--')+1]);asset=json.loads((job/'asset.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
objects=import_file(Path(asset['absolutePath']));rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body']
rig.animation_data_create();idle=bpy.data.actions[asset['actions']['idle']]
rig.animation_data.action=idle;rig.animation_data.action_slot=idle.slots[0];bpy.context.scene.frame_set(36)
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
folder=job/'experiments';folder.mkdir(exist_ok=True);results={}
for name,bone,amount in [('head_nod','Head',.15),('jaw_open_close','ORG_Jaw',.2)]:
    b=rig.pose.bones.get(bone)
    if not b or b.constraints or b.rotation_mode!='XYZ':
        results[name]={'status':'unsupported','reason':'No verified unconstrained XYZ source control'};continue
    base=b.rotation_euler.copy();action=bpy.data.actions.new('Wolf.Experiment.'+name);action.use_fake_user=True;rig.animation_data.action=action
    for f,offset in [(1,0),(12,amount),(24,0)]:
        b.rotation_euler=base.copy();b.rotation_euler.x+=offset;b.keyframe_insert('rotation_euler',frame=f)
    p=points(body,1);q=points(body,12);delta=mesh_delta(p,q)
    status='experimental_mesh_response' if delta['max']>.001 else 'no_verified_mesh_response'
    results[name]={'status':status,'bone':bone,'action':action.name,'delta':delta,'includedInDemo':False,'authorControlMappingReviewRequired':True}
    bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=24;bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')))
    rig.animation_data.action=None;b.rotation_euler=base
for name,terms in [('blink',['eyelid','blink','lid.']),('eyebrows',['brow'])]:
    candidates=[b.name for b in rig.pose.bones if any(term in b.name.lower() for term in terms)]
    results[name]={'status':'mapping_required' if candidates else 'unsupported_unmapped','candidates':candidates,'reason':'No independently verified authored controller; deformation names alone are insufficient','includedInDemo':False}
results['drivers']=blocked_drivers([rig,body]);(folder/'facial-report.json').write_text(json.dumps(results,indent=2))
report=json.loads((job/'animation-report.json').read_text());report['facialExperiments']={'report':str(folder/'facial-report.json'),'results':results,'includedInDemo':False};(job/'animation-report.json').write_text(json.dumps(report,indent=2))
