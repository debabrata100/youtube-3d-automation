"""Scene-level composition/verification. Character rig details remain in adapters."""
import bpy,sys,json,math,hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from bpy_extras.anim_utils import action_get_channelbag_for_slot
sys.path.insert(0,str(Path(__file__).resolve().parent))
import wolf_native as native
from cinematic_camera import schedule_multi,frame_projector
from motion_utils import heading_to,shortest

def instances(scene_plan):
    return {c['id']:{role:bpy.data.objects['Character.'+c['id']+'.'+role] for role in ('rig','body','motion')} for c in scene_plan['characters']}

def verify(job,execution,reload=False,write_report=True):
    plan=execution['scene'];scene=bpy.context.scene;chars=instances(plan);ids=list(chars)
    if bpy.context.preferences.filepaths.use_scripts_auto_execute:raise ValueError('Auto-run must remain disabled')
    if scene.frame_start!=1 or scene.frame_end!=execution['frameCount'] or scene.render.fps!=plan['fps'] or scene.render.resolution_x!=plan['resolution']['width'] or scene.render.resolution_y!=plan['resolution']['height'] or scene.render.resolution_percentage!=100:raise ValueError('Saved scene output settings differ from plan')
    if reload and scene.render.filepath!=str(job/'frames'/'frame_'):raise ValueError('Saved frame output path differs from job')
    rigs=[c['rig'] for c in chars.values()]
    if len({r.as_pointer() for r in rigs})!=len(rigs) or len({r.data.as_pointer() for r in rigs})!=len(rigs):raise ValueError('Armatures are not independent')
    actions=[{s.action.as_pointer() for t in r.animation_data.nla_tracks for s in t.strips} for r in rigs]
    if any(actions[i]&actions[j] for i in range(len(rigs)) for j in range(i+1,len(rigs))):raise ValueError('Instances share mutable Action data')
    result={'characterCount':len(chars),'uniqueCharacterIds':True,'independentArmatures':True,'independentAnimationState':True,'interactions':execution['events'],'collisionWarnings':[],'cameraCoverage':[],'timelineContinuity':[],'humanVisualReviewRequired':True,'targetSampling':execution['targetSampling'],'isolationProbes':[],'locomotionProbes':[],'transforms':[]}
    minimum=float('inf');previous={};maxstep={k:0 for k in ids}
    for frame in range(1,scene.frame_end+1):
        bounds={};points={}
        for name,c in chars.items():
            points[name]=native.points(c['body'],frame);bounds[name]=native.bounds(points[name])
            if bounds[name][0][2]<.014:raise ValueError('Floor penetration '+name+' '+str(frame))
            now=c['motion'].location.copy()
            if name in previous:maxstep[name]=max(maxstep[name],(now-previous[name]).length)
            previous[name]=now
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                # Conservative planar AABB distance on actual deformed vertices, not mesh collision proof.
                gap=math.hypot(*(max(0,bounds[a][0][k]-bounds[b][1][k],bounds[b][0][k]-bounds[a][1][k]) for k in (0,1)))
                minimum=min(minimum,gap)
                if gap<plan['minimumGapMeters']:raise ValueError('Evaluated spacing failed at frame '+str(frame)+': '+str(gap))
        shot=next(s for s in plan['cameraShots'] if s['start']*24<frame<=s['end']*24)
        allpts=[p for n in shot['subjects'] for p in points[n]];crop=min(p.z for p in allpts)+.9 if shot['type']=='medium' else -math.inf
        scene.view_layers[0].update()
        project=frame_projector(scene,scene.camera)
        for p in allpts:
            if p.z<crop:continue
            uv=project(p)
            if not (.015<uv.x<.985 and .015<uv.y<.985 and uv.z>0):raise ValueError('Camera coverage failed at '+str(frame))
    result['minimumSeparationMeters']=minimum
    result['separationMethod']='evaluated planar Body AABB gap every frame; conservative proxy, not complete mesh collision freedom'
    for shot in plan['cameraShots']:result['cameraCoverage'].append({**shot,'framesChecked':round((shot['end']-shot['start'])*24),'passed':True})
    for entry in execution['controllers']:
        name=entry['id'];c=chars[name];controller=entry['controller'];motion=c['motion'];rig=c['rig']
        native.blocked_drivers([rig,c['body']]);scene.frame_set(1)
        if (motion.location-Vector(controller['startPosition'])).length>1e-5 or abs(motion.rotation_euler.z-math.radians(controller['headingDegrees']))>1e-5:raise ValueError('Initial transform mismatch')
        idle_tracks=[t for t in rig.animation_data.nla_tracks if t.name=='Controller.Idle']
        if len(idle_tracks)!=1 or any(not s.action_slot for t in idle_tracks for s in t.strips):raise ValueError('Native idle bed/slot missing')
        position=Vector(controller['startPosition']);heading=math.radians(controller['headingDegrees'])
        for a in controller['actions']:
            end=round(a['end']*24);scene.frame_set(end)
            if a['type']=='walk':position=Vector(a['destination'])
            if a['type']=='faceTarget':heading=shortest(heading,heading_to(position,a['target']))
            if a['type']=='turn':heading=shortest(heading,math.radians(a['degrees'])+(heading if a['mode']=='relative' else 0))
            if (motion.location-position).length>1e-5 or abs(motion.rotation_euler.z-heading)>1e-5:raise ValueError('Action endpoint mismatch: '+name+' '+a['type'])
            if a['type']=='walk':
                frame=round((a['start']+a['end'])*12)
                before={n:native.points(ch['body'],frame) for n,ch in chars.items()}
                tracks=[t for t in rig.animation_data.nla_tracks if t.name.startswith('Controller.Walk')]
                if not tracks or any(not s.action_slot for t in tracks for s in t.strips):raise ValueError('Native walk assignment/slot missing')
                for t in tracks:t.mute=True
                after={n:native.points(ch['body'],frame) for n,ch in chars.items()}
                delta={n:native.mesh_delta(before[n],after[n])['max'] for n in ids}
                for t in tracks:t.mute=False
                if delta[name]<.01 or any(delta[n]>1e-6 for n in ids if n!=name):raise ValueError('Native walk cross-character interference')
                native.points(c['body'],frame)
                root_action=motion.animation_data.action;root_slot=motion.animation_data.action_slot
                motion.animation_data.action=None;motion.location=Vector(controller['startPosition'])
                translated={n:native.points(ch['body'],frame) for n,ch in chars.items()}
                motion.animation_data.action=root_action;motion.animation_data.action_slot=root_slot
                root_delta={n:native.mesh_delta(before[n],translated[n])['max'] for n in ids}
                if root_delta[name]<.1 or any(root_delta[n]>1e-6 for n in ids if n!=name):raise ValueError('Root motion cross-character interference')
                result['locomotionProbes'].append({'actor':name,'frame':frame,'poseDeltas':delta,'rootDeltas':root_delta})
            if a['type']=='wave':
                frame=round((a['start']+a['end'])*12);before={n:native.points(ch['body'],frame) for n,ch in chars.items()}
                tracks=[t for t in rig.animation_data.nla_tracks if t.name.startswith('Controller.Wave')]
                for t in tracks:t.mute=True
                after={n:native.points(ch['body'],frame) for n,ch in chars.items()}
                delta={n:native.mesh_delta(before[n],after[n])['max'] for n in ids}
                if delta[name]<.05 or any(delta[n]>1e-6 for n in ids if n!=name):raise ValueError('Wave cross-character interference')
                for t in tracks:t.mute=False
                return_frame=min(scene.frame_end,end+1);active=native.points(c['body'],return_frame)
                for t in tracks:t.mute=True
                inactive=native.points(c['body'],return_frame)
                for t in tracks:t.mute=False
                if native.mesh_delta(active,inactive)['max']>1e-5:raise ValueError('Wave idle restoration failed')
                strips=[s for t in tracks for s in t.strips if abs(s.frame_start-(a['start']*24+1))<.01]
                expected_wave='Wolf.Controller.Wave.v4' if controller.get('performance',{}).get('forwardWave') else 'Wolf.Controller.Wave.v3'
                if len(strips)!=1 or not strips[0].action_slot or not strips[0].action.name.startswith(expected_wave) or abs(strips[0].frame_end-end)>.01:raise ValueError('Wave slot/timing mismatch')
                result['isolationProbes'].append({'actor':name,'frame':frame,'meshDeltas':delta,'returnToIdle':True})
        scene.frame_set(scene.frame_end)
        result['transforms'].append({'id':name,'initialPosition':controller['startPosition'],'finalPosition':list(motion.location),'finalHeadingRadians':motion.rotation_euler.z,'worldTravelMeters':(motion.location-Vector(controller['startPosition'])).length})
        result['timelineContinuity'].append({'id':name,'maximumRootStepMeters':maxstep[name]})
        if maxstep[name]>.1:raise ValueError('Root discontinuity')
    source=json.loads((job/'footprint'/'animation-report.json').read_text())
    if hashlib.sha256(Path(source['source']).read_bytes()).hexdigest()!=source['sourceSha256']:raise ValueError('Source asset changed')
    report={'status':'scene_verified_pending_render','frames':scene.frame_end,'source':source['source'],'sourceSha256':source['sourceSha256'],'license':source['license'],'reviewOnly':True,'productionPublishingAllowed':False,'autoRunEnabled':False,'sourceAssetUnchanged':True,'savedSceneReloadVerified':reload,'multiCharacter':result,'animationQuality':{entry['id']:json.loads((job/'characters'/entry['id']/'animation-report.json').read_text()).get('animationQuality') for entry in execution['controllers']}}
    if write_report:(job/'animation-report.json').write_text(json.dumps(report,indent=2))
    return report

def build(job,execution):
    bpy.ops.wm.open_mainfile(filepath=str(job/'footprint'/'scene.blend'),use_scripts=False)
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):
        if obj.type not in ('CAMERA','LIGHT') and obj.name!='WolfFloor':bpy.data.objects.remove(obj,do_unlink=True)
    for entry in execution['controllers']:
        name=entry['id'];file=job/'characters'/name/'scene.blend'
        with bpy.data.libraries.load(str(file),link=False) as (source,result):result.collections=['CharacterInstance']
        collection=result.collections[0];scene.collection.children.link(collection);collection.name='Character.'+name
        for obj in collection.all_objects:
            role=obj.get('sceneRole')
            obj.name='Character.'+name+'.'+(role or obj.name)
        # Local append preserves/remaps the complete hierarchy, modifiers, constraints and driver targets.
    scene.frame_end=execution['frameCount'];scene.render.fps=execution['scene']['fps']
    chars=instances(execution['scene']);schedule_multi(scene,{n:c['body'] for n,c in chars.items()},execution['scene']['cameraShots'],execution.get('cameraAnchor'))
    verify(job,execution)
    (job/'frames').mkdir(exist_ok=True);scene.render.filepath=str(job/'frames'/'frame_');scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(job/'scene.blend'))

if __name__=='__main__':
    mode,folder=sys.argv[sys.argv.index('--')+1:];job=Path(folder);execution=json.loads((job/'scene-plan.json').read_text())
    if mode=='build':build(job,execution)
    else:verify(job,execution,True)
