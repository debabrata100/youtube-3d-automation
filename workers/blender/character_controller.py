"""Validated controller execution with a wolf-specific native/gesture adapter."""
import bpy
import sys
import json
import math
import hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from bpy_extras.anim_utils import action_get_channelbag_for_slot
sys.path.insert(0,str(Path(__file__).resolve().parent))
import wolf_native as native
from motion_utils import smooth,shortest,heading_to,interpolate,camera_preset

def wave_action(rig,config):
    names=config['rightArmControls'];offset=config['waveOffsetsRadians']
    if any(n not in rig.pose.bones or rig.pose.bones[n].constraints for n in names): raise ValueError('Wave FK controls missing/constrained; a targeted rig adapter is required')
    rig.animation_data.action=None
    action=bpy.data.actions.new('Wolf.Controller.Wave.v1');action.use_fake_user=True
    rig.animation_data.action=action
    for frame in range(73):
        t=frame/72;envelope=smooth(min(1,t/.22))*smooth(min(1,(1-t)/.22))
        for i,name in enumerate(names):
            b=rig.pose.bones[name]
            if b.rotation_mode!='XYZ': raise ValueError('Wave adapter requires native XYZ controls')
            b.rotation_euler=(0,0,0)
            if i==0:b.rotation_euler=tuple(envelope*v for v in offset['upperArmXYZ'])
            if i==1:b.rotation_euler.x=envelope*offset['forearmX']
            if i==2:b.rotation_euler.z=envelope*offset['handZAmplitude']*math.sin(6*math.pi*t)
            b.keyframe_insert('rotation_euler',frame=frame)
    slot=rig.animation_data.action_slot
    for c in action_get_channelbag_for_slot(action,slot).fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    rig.animation_data.action=None
    # Clear just the temporary offset values: underlying native NLA supplies the pose.
    for name in names:rig.pose.bones[name].rotation_euler=(0,0,0)
    return action,slot

def evaluate_feet(rig,frames):
    result=[]
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        result.append({n:e.matrix_world@e.pose.bones[n].matrix.translation for n in ('Foot.L','Foot.R')})
    return result

def foot_sliding(samples,fps):
    values=[];contacts=0
    for name in ('Foot.L','Foot.R'):
        minimum=min(p[name].z for p in samples)
        for a,b in zip(samples,samples[1:]):
            if max(a[name].z,b[name].z)<minimum+.045:
                values.append((b[name].xy-a[name].xy).length*fps);contacts+=1
    return {'contactSamples':contacts,'meanHorizontalSpeedMetersPerSecond':sum(values)/len(values) if values else None,'contactDefinition':'Foot control origin within 4.5 cm of its sequence minimum; proxy, not a sole sensor'}

def build(plan,asset,job):
    controller=plan['controller'];polish=controller.get('polish',False);config=json.loads((Path(__file__).resolve().parents[2]/'assets/characters/wolf-warrior/animation-config.json').read_text())
    native.build(plan,asset,job) # Reuse safe native loading, deformation checks, materials, placement and studio.
    report=json.loads((job/'animation-report.json').read_text());report['baseNativePreflight']=report.pop('checks')
    scene=bpy.context.scene;rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];placement=bpy.data.objects['WolfPlacement']
    for track in list(rig.animation_data.nla_tracks):
        if track.name.startswith('WolfNative.'):rig.animation_data.nla_tracks.remove(track)
    total=controller['fps']*controller['durationSeconds'];scene.frame_end=total;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    schedule=[]
    for item in controller['actions']:
        start=round(item['start']*24)+1;end=round(item['end']*24)
        schedule.append({**item,'startFrame':start,'endFrame':end})
    # One continuous idle bed; walk replaces it only during locomotion.
    idle=bpy.data.actions[asset['actions']['idle']];walk=bpy.data.actions[asset['actions']['walk']]
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new();track.name='Controller.Idle'
    strip=track.strips.new('Idle bed',1,idle);strip.action_slot=idle.slots[0];strip.repeat=(total-1)/(idle.frame_range[1]-idle.frame_range[0]);strip.frame_end=total;strip.extrapolation='HOLD_FORWARD'
    # Native root-motion audit: no object channels, Root local channels, or drifting evaluated Root.
    bag=action_get_channelbag_for_slot(walk,walk.slots[0]);root_paths=[c.data_path for c in bag.fcurves if not c.data_path.startswith('pose.bones[') or c.data_path.startswith('pose.bones["Root"]')]
    if root_paths:raise ValueError('Native walk has root channels; refusing potential double root motion: '+str(root_paths))
    # Estimate stride from the low-foot backward velocity in native scaled space.
    rig.animation_data.action=walk;rig.animation_data.action_slot=walk.slots[0]
    for t in rig.animation_data.nla_tracks:t.mute=True
    cycle=config['nativeWalkCycleFrames']
    if abs((walk.frame_range[1]-walk.frame_range[0])-cycle)>.001:raise ValueError('Configured native cycle length differs from source Action')
    native_feet=evaluate_feet(rig,range(cycle+1));velocities=[]
    for n in config['footControls']:
        low=min(p[n].z for p in native_feet)
        for a,b in zip(native_feet,native_feet[1:]):
            # Forward is -Y, so a grounded foot moving +Y cancels world forward motion.
            if max(a[n].z,b[n].z)<low+.045 and b[n].y>a[n].y:velocities.append((b[n].y-a[n].y)*24)
    if not velocities:raise ValueError('No reliable native stance samples; cadence requires manual calibration')
    stance_speed=sorted(velocities)[len(velocities)//2]
    rig.animation_data.action=None
    for t in rig.animation_data.nla_tracks:t.mute=False
    report['rootMotionAudit']={'unexpectedChannels':root_paths,'mode':'world-space dedicated parent; native clip remains in place'}
    report['cadence']={'nativeContactSpeedMetersPerSecond':stance_speed,'nativeCycleFrames':cycle,'method':'median backwards velocity of low native Foot controls'}
    for item in schedule:
        if item['type']=='walk':
            track=rig.animation_data.nla_tracks.new();track.name='Controller.Walk'
            strip=track.strips.new('Walk',item['startFrame']-4,walk);strip.action_slot=walk.slots[0]
            speed=item['speedMetersPerSecond'];rate=speed/stance_speed
            strip.repeat=(item['endFrame']-strip.frame_start)*rate/cycle;strip.scale=1/rate;strip.frame_end=item['endFrame'];strip.blend_in=8 if polish else 4;strip.blend_out=12 if polish else 4;strip.extrapolation='NOTHING'
            report['cadence']['playbackRate']=rate
        if item['type']=='wave':
            action,slot=wave_action(rig,config)
            if polish:
                from animation_polish import wave_v2
                action,slot=wave_v2(rig,config)
            track=rig.animation_data.nla_tracks.new();track.name='Controller.Wave'
            strip=track.strips.new('Layered right arm wave',item['startFrame'],action);strip.action_slot=slot
            strip.scale=(item['endFrame']-item['startFrame'])/72;strip.frame_end=item['endFrame'];strip.blend_type='ADD';strip.extrapolation='NOTHING'
    # The placement parent owns normalization only; motion lives one level above it.
    motion=bpy.data.objects.new('CharacterMotion',None);scene.collection.objects.link(motion);placement.parent=motion
    position=Vector(controller['startPosition']);heading=math.radians(controller['headingDegrees']);camera_position=Vector((0,-10,2.5));states=[]
    if controller.get('cameraShots'):
        last_destination=next(a['destination'] for a in reversed(schedule) if a['type']=='walk')
        camera_position=Vector((last_destination[0]*(.65 if controller['cameraShots'][-1]['preset']=='wide' else 1),last_destination[1]-10,2.5))
    for item in schedule:
        start,end=item['startFrame'],item['endFrame'];destination=position.copy();new_heading=heading
        if item['type']=='walk':
            destination=Vector(item['destination']);new_heading=shortest(heading,heading_to(position,destination))
            if abs(new_heading-heading)>.05:raise ValueError('Turn toward destination before walking; refusing sideways locomotion')
        elif item['type']=='turn':new_heading=shortest(heading,heading+math.radians(item['degrees'])) if item['mode']=='relative' else shortest(heading,math.radians(item['degrees']))
        elif item['type']=='faceTarget':new_heading=shortest(heading,heading_to(position,item['target']))
        elif item['type']=='turnToCamera':new_heading=shortest(heading,heading_to(position,camera_position))
        for frame in range(start,end+1):
            t=(frame-start)/max(1,end-start)
            # Cadence-matched near-linear travel with short acceleration/deceleration ramps.
            if item['type']=='walk':
                ramp=.12
                # Integral of a linear speed ramp, normalized for exact endpoints.
                if t<ramp:u=t*t/(2*ramp*(1-ramp))
                elif t>1-ramp:u=1-(1-t)**2/(2*ramp*(1-ramp))
                else:u=(t-ramp/2)/(1-ramp)
                motion.location=position.lerp(destination,u)
            else:motion.location=position
            motion.rotation_euler.z=heading+(new_heading-heading)*smooth(t)
            motion.keyframe_insert('location',frame=frame);motion.keyframe_insert('rotation_euler',frame=frame)
            states.append({'frame':frame,'position':list(motion.location),'headingRadians':motion.rotation_euler.z})
        position=destination;heading=new_heading
    if motion.animation_data:
        for c in action_get_channelbag_for_slot(motion.animation_data.action,motion.animation_data.action_slot).fcurves:
            for k in c.keyframe_points:k.interpolation='LINEAR'
    polish_foot=None
    if polish:
        from animation_polish import stabilize
        polish_foot=stabilize(rig,motion,next(a for a in schedule if a['type']=='walk'),job)
    # Measure foot sliding in-place vs translating under the same cadence and orientation.
    walking=next((i for i in schedule if i['type']=='walk'),None)
    if not walking:raise ValueError('This Phase 3 wolf adapter currently requires a walk segment')
    frames=range(walking['startFrame']+5,walking['endFrame']-5)
    moving_feet=evaluate_feet(rig,frames)
    baseline=[]
    for frame,sample in zip(frames,moving_feet):
        scene.frame_set(frame);baseline.append({n:p-motion.location for n,p in sample.items()})
    before=foot_sliding(baseline,24);after=foot_sliding(moving_feet,24)
    report['footContact']={'inPlaceProxy':before,'translatedProxy':after,'footLockingImplemented':False,'correction':'cadence matching only','improved':after['meanHorizontalSpeedMetersPerSecond']<before['meanHorizontalSpeedMetersPerSecond']}
    if polish:
        report['footContact']['footLockingImplemented']=True
        report['footContact']['correction']='bounded contact-aware native IK offsets plus cadence; not unlimited locking'
    # Normalize floor contact across the complete new sequence without altering IK controls.
    all_bounds=[native.bounds(native.points(body,f)) for f in range(1,total+1)]
    min_z=min(b[0][2] for b in all_bounds);placement.location.z+=.015-min_z
    all_bounds=[native.bounds(native.points(body,f)) for f in range(1,total+1)]
    lo=[min(b[0][i] for b in all_bounds) for i in range(3)];hi=[max(b[1][i] for b in all_bounds) for i in range(3)]
    # Fixed demo camera. Preset bounds are motion-aware; target heading uses its actual XY position.
    camera=scene.camera;camera.location=camera_position
    target=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,(lo[2]+hi[2])/2));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    height=hi[2]-lo[2];camera.data.ortho_scale=max((hi[0]-lo[0])*1.3,height*16/9*1.3)
    if controller['cameraPreset']!='full_body':camera_preset(scene,native.bounds(native.points(body,total)),controller['cameraPreset'])
    scheduled_camera=None
    if controller.get('cameraShots'):
        from cinematic_camera import schedule as schedule_camera
        scheduled_camera=schedule_camera(scene,body,motion,controller['cameraShots'])
    for f in range(1,total+1):
        pts=native.points(body,f)
        if min(p.z for p in pts)<.014:raise ValueError('Ground penetration at '+str(f))
        if controller['cameraPreset']=='full_body' and not scheduled_camera:
            for p in pts:
                uv=world_to_camera_view(scene,camera,p)
                if not (.02<uv.x<.98 and .02<uv.y<.98 and uv.z>0):raise ValueError('Controller framing failed at '+str(f))
    # Verify gesture evaluation on the real rig, including opposite-arm independence.
    wave=next((i for i in schedule if i['type']=='wave'),None)
    if not wave:raise ValueError('This Phase 3 verification adapter currently requires a wave segment')
    sample=(wave['startFrame']+wave['endFrame'])//2
    scene.frame_set(sample);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());raised=(e.matrix_world@e.pose.bones['FK_Hand.R'].matrix.translation).copy();left=e.pose.bones['FK_Hand.L'].matrix.copy();posed=native.points(body,sample)
    wave_track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.Wave');wave_track.mute=True
    native.points(body,sample);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());rest=e.matrix_world@e.pose.bones['FK_Hand.R'].matrix.translation;opposite=e.pose.bones['FK_Hand.L'].matrix.copy();unposed=native.points(body,sample)
    if raised.z-rest.z<.3 or left!=opposite:raise ValueError('Wave failed to raise right hand independently; do not force deformation bones')
    wave_track.mute=False
    scene.frame_set(total);final_position=motion.location.copy();final_heading=motion.rotation_euler.z
    if (final_position-position).length>.001:raise ValueError('Destination not reached')
    report.update({'controller':controller,'schedule':schedule,'timeline':states,'status':'controller_scene_verified_pending_render','frames':total,
        'wave':{'action':'Wolf.Controller.Wave.v2' if polish else 'Wolf.Controller.Wave.v1','controls':config['rightArmControls'],'handLiftMeters':raised.z-rest.z,'oppositeArmUnchanged':True,'meshDifference':native.mesh_delta(posed,unposed),'cycles':2 if polish else 3,'returnToIdle':True},
        'motion':{'displacementMeters':(final_position-Vector(controller['startPosition'])).length,'finalPosition':list(final_position),'finalHeadingRadians':final_heading,'destinationToleranceMeters':.001},
        'camera':{'preset':controller['cameraPreset'],'location':list(camera.location),'fullBodyAllFramesChecked':controller['cameraPreset']=='full_body' and not scheduled_camera},
        'floor':{'minimum':min(b[0][2] for b in all_bounds),'maximumLowerBound':max(b[0][2] for b in all_bounds)},
        'drivers':native.blocked_drivers([rig,body]),'facialExperiments':{'status':'pending_isolated_probes','includedInDemo':False}})
    if polish:
        report['animationQuality']={'footContact':polish_foot,'wave':report['wave'].copy(),'camera':scheduled_camera,'transitions':{'walkBlendInFrames':8,'walkBlendOutFrames':12,'humanVisualReviewRequired':True},'humanVisualReviewRequired':True}
    scene.render.filepath=str(job/'frames'/'frame_');scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(job/'scene.blend'))
    (job/'animation-report.json').write_text(json.dumps(report,indent=2))

def review(job):
    report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene;body=bpy.data.objects['Body'];motion=bpy.data.objects['CharacterMotion'];rig=bpy.data.objects['Armature']
    scene.frame_set(scene.frame_end)
    if (motion.location-Vector(report['motion']['finalPosition'])).length>.001:raise ValueError('Saved motion changed')
    native.blocked_drivers([rig,body])
    track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.Wave')
    return_frame=min(scene.frame_end,round(next(a['end'] for a in report['controller']['actions'] if a['type']=='wave')*24)+1)
    active=native.points(body,return_frame);track.mute=True;inactive=native.points(body,return_frame);track.mute=False
    return_delta=native.mesh_delta(active,inactive)
    if return_delta['max']>1e-5:raise ValueError('Wave does not return to underlying native idle')
    report['wave']['returnToIdleVerifiedDelta']=return_delta
    max_root_step=0;max_heading_step=0;max_mesh_rms=0;previous=None
    for f in range(1,scene.frame_end+1):
        pts=native.points(body,f);sample=pts[::max(1,len(pts)//128)]
        now=(motion.location.copy(),motion.rotation_euler.z,sample)
        if previous:
            max_root_step=max(max_root_step,(now[0]-previous[0]).length)
            max_heading_step=max(max_heading_step,abs(now[1]-previous[1]))
            max_mesh_rms=max(max_mesh_rms,math.sqrt(sum((a-b).length_squared for a,b in zip(sample,previous[2]))/len(sample)))
        previous=now
    report['continuity']={'maxRootStepMeters':max_root_step,'maxHeadingStepRadians':max_heading_step,'maxSampledMeshFrameRmsMeters':max_mesh_rms,'note':'Sampled vertex changes include intended pose/turn motion; not proof of artistic quality'}
    if report['controller'].get('polish'):
        report['footContact']['footLockingImplemented']=True
        report['footContact']['correction']='bounded contact-aware native IK offsets plus cadence; not unlimited locking'
        report['animationQuality']['transitions'].update(report['continuity'])
        report['animationQuality']['transitions']['unusualMeshChangeWarning']=max_mesh_rms>.15
    if max_root_step>.05 or max_heading_step>.2:raise ValueError('Unexpected motion discontinuity')
    if report['controller'].get('polish'):
        from animation_polish import finalize_quality
        finalize_quality(job,report)
    images=[];folder=job/'previews';folder.mkdir(exist_ok=True)
    for item in report['schedule']:
        for f in sorted({item['startFrame'],(item['startFrame']+item['endFrame'])//2,item['endFrame']}):
            scene.frame_set(f);filename=folder/('%03d-%s.png'%(f,item['type']));scene.render.filepath=str(filename);bpy.ops.render.render(write_still=True);images.append(str(filename))
    report['previews']=images;report['status']='verified_pending_human_visual_review';report['savedSceneReloadVerified']=True
    if hashlib.sha256(Path(report['source']).read_bytes()).hexdigest()!=report['sourceSha256']:raise ValueError('Original asset hash changed')
    (job/'animation-report.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if args[0]=='review':review(Path(args[1]))
    else:
        file,folder=args;job=Path(folder)
        try:build(json.loads(Path(file).read_text()),json.loads((job/'asset.json').read_text()),job)
        except Exception as error:
            report=json.loads((job/'animation-report.json').read_text()) if (job/'animation-report.json').exists() else {}
            report.update(status='blocked',diagnostic=str(error));(job/'animation-report.json').write_text(json.dumps(report,indent=2));raise
