"""Reusable saved-scene wave diagnostics and calibrated views for both actors."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from wave_diagnostics import measure,calibrate,evaluated_controls
from scene_composition import instances
from bpy_extras.anim_utils import action_get_channelbag_for_slot

def diagnose(job):
    execution=json.loads((job/'scene-plan.json').read_text());chars=instances(execution['scene']);scene=bpy.context.scene;results={};headings=[]
    for entry in execution['controllers']:
        name=entry['id'];ch=chars[name];wave=next(a for a in entry['controller']['actions'] if a['type']=='wave');start=round(wave['start']*24)+1;end=round(wave['end']*24)
        strips=[s for t in ch['rig'].animation_data.nla_tracks if t.name.startswith('Controller.Wave') for s in t.strips]
        for strip in strips:
            if not strip.action.name.startswith('Wolf.Controller.Wave.v4') or not strip.action_slot:raise ValueError('Corrected wave/slot not assigned')
            for curve in action_get_channelbag_for_slot(strip.action,strip.action_slot).fcurves:
                if not any(control in curve.data_path for control in ['FK_UpperArm.R','FK_Forearm.R','FK_Hand.R','FK_Spine_02']):raise ValueError('Wave changed unsupported rig channels')
                if abs(curve.keyframe_points[0].co.y)>1e-7 or abs(curve.keyframe_points[-1].co.y)>1e-7:raise ValueError('Wave layer does not start/end at native idle')
        results[name]=measure(ch['rig'],ch['body'],start,end,scene.camera,enforce=False)
        motion=ch['motion'];action=motion.animation_data.action;slot=motion.animation_data.action_slot
        scene.frame_set(start);position=motion.location.copy();rotation=motion.rotation_euler.copy()
        try:
            motion.animation_data.action=None
            for degrees in (0,90,180,270):
                motion.location=position;motion.rotation_euler=(0,0,math.radians(degrees))
                result=measure(ch['rig'],ch['body'],start,end,enforce=False)
                headings.append({'actor':name,'headingDegrees':degrees,**result})
        finally:
            motion.animation_data.action=action;motion.animation_data.action_slot=slot;motion.rotation_euler=rotation;scene.frame_set(start)
    def curves(action):
        return [(c.data_path,c.array_index,[tuple(k.co) for k in c.keyframe_points]) for slot in action.slots for c in action_get_channelbag_for_slot(action,slot).fcurves]
    source=json.loads((job/'footprint/animation-report.json').read_text())['source']
    names=['01-Idle(60)','02-Walk (42)'];existing={n:[curves(a) for a in bpy.data.actions if a.name==n or a.name.startswith(n+'.')] for n in names}
    with bpy.data.libraries.load(source,link=False) as (_,loaded):loaded.actions=list(names)
    native_unchanged=all(all(candidate==curves(original) for candidate in existing[name]) for name,original in zip(names,loaded.actions))
    if not native_unchanged:raise ValueError('Native source action curves changed')
    report={'schemaVersion':'1.0','gesture':'Wolf.Controller.Wave.v4','characters':results,'headingTests':headings,'nativeActionsUnchanged':native_unchanged,'passed':all(r['passed'] for r in [*results.values(),*headings]),'humanVisualApproval':'pending'}
    (job/'wave-diagnostics.json').write_text(json.dumps(report,indent=2))
    if not report['passed']:raise ValueError('Wave diagnostics failed; inspect wave-diagnostics.json')
    return report

def previews(job):
    execution=json.loads((job/'scene-plan.json').read_text());chars=instances(execution['scene']);scene=bpy.context.scene;camera=scene.camera
    directory=job/'previews'/'wave';directory.mkdir(parents=True,exist_ok=True);manifest=[]
    original_camera=scene.camera
    bpy.ops.object.camera_add();view=bpy.context.object;view.data.type='ORTHO';view.data.ortho_scale=3.8
    try:
        for entry in execution['controllers']:
            name=entry['id'];ch=chars[name];wave=next(a for a in entry['controller']['actions'] if a['type']=='wave');start=round(wave['start']*24)+1;end=round(wave['end']*24)
            cal=calibrate(ch['rig'],ch['body'],start)
            for phase,u in [('preparation',.22),('peak',.54),('recovery',.88)]:
                frame=round(start+(end-start)*u);scene.frame_set(frame);e,p=evaluated_controls(ch['rig']);forward=e.matrix_world.to_3x3()@Vector(cal['localForward']);forward.normalize();right=forward.cross(Vector((0,0,1)))
                target=p['chest']+Vector((0,0,.25))
                for label,direction in [('front',forward),('side',right),('three-quarter',(forward+right).normalized())]:
                    scene.camera=view;view.location=target+direction*9+Vector((0,0,.35));view.rotation_euler=(target-view.location).to_track_quat('-Z','Y').to_euler()
                    hidden={n:c['body'].hide_render for n,c in chars.items()}
                    for n,c in chars.items():c['body'].hide_render=n!=name
                    filename=directory/f'{name}-{label}-{phase}.png';scene.render.filepath=str(filename);bpy.ops.render.render(write_still=True)
                    for n,c in chars.items():c['body'].hide_render=hidden[n]
                    manifest.append({'actor':name,'view':label,'phase':phase,'frame':frame,'path':str(filename)})
                scene.camera=original_camera;filename=directory/f'{name}-greeting-{phase}.png';scene.render.filepath=str(filename);bpy.ops.render.render(write_still=True);manifest.append({'actor':name,'view':'greeting','phase':phase,'frame':frame,'path':str(filename)})
    finally:scene.camera=original_camera;bpy.data.objects.remove(view,do_unlink=True)
    for index,row in enumerate(manifest,1):
        import shutil
        shutil.copyfile(row['path'],directory/f'sheet-{index:02d}.png')
    (directory/'index.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':
    mode,folder=sys.argv[sys.argv.index('--')+1:];job=Path(folder)
    diagnose(job) if mode=='diagnose' else previews(job)
