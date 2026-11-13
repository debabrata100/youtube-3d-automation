import bpy,json,math
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from foot_contact import stance_pairs,intervals,statistics,release_weight
import wolf_native as native
from motion_utils import smooth

FOOT_NAMES=('Foot.L','Foot.R')

def wave_v2(rig,config):
    names=config['rightArmControls'];offset=config['waveOffsetsRadians']
    action=bpy.data.actions.new('Wolf.Controller.Wave.v2');action.use_fake_user=True;rig.animation_data.action=action
    def envelope(t,raise_start,raise_end,lower_start,lower_end):
        return smooth((t-raise_start)/(raise_end-raise_start))*(1-smooth((t-lower_start)/(lower_end-lower_start)))
    for frame in range(73):
        t=frame/72
        shoulder=envelope(t,.05,.34,.75,1);elbow=envelope(t,.09,.40,.78,1);wrist=envelope(t,.27,.43,.74,.94)
        anticipation=-.055*math.sin(math.pi*min(1,t/.14)) if t<.14 else 0
        phase=max(0,min(1,(t-.34)/.43))
        for i,name in enumerate(names):
            b=rig.pose.bones[name]
            if b.constraints or b.rotation_mode!='XYZ':raise ValueError('Unsafe wave v2 control: '+name)
            b.rotation_euler=(0,0,0)
            if i==0:
                b.rotation_euler=tuple(shoulder*v*.95 for v in offset['upperArmXYZ']);b.rotation_euler.x+=anticipation
            elif i==1:b.rotation_euler.x=elbow*offset['forearmX']+wrist*.045*math.sin(4*math.pi*phase-.5)
            else:
                b.rotation_euler.z=wrist*.24*math.sin(4*math.pi*phase)
                b.rotation_euler.x=wrist*.07*math.sin(4*math.pi*phase-.65)
            b.keyframe_insert('rotation_euler',frame=frame)
    slot=rig.animation_data.action_slot
    for c in action_get_channelbag_for_slot(action,slot).fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    rig.animation_data.action=None
    for n in names:rig.pose.bones[n].rotation_euler=(0,0,0)
    return action,slot

def capture_feet(rig,frames):
    values=[]
    for frame in frames:
        bpy.context.scene.frame_set(frame);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        values.append({n:e.matrix_world@e.pose.bones[n].matrix.translation for n in FOOT_NAMES})
    return values

def stabilize(rig,motion,walking,job,performance=None):
    if any(rig.pose.bones[n].constraints for n in FOOT_NAMES):raise ValueError('Foot controllers are constrained; safe locking adapter unavailable')
    if any(abs(rig.pose.bones['Option']['IK-FK_Leg.'+side]-1)>.001 for side in ('L','R')):raise ValueError('Expected native IK leg mode; refusing to switch rig configuration silently')
    start,end=walking['startFrame'],walking['endFrame'];frames=list(range(start,end+1));raw=capture_feet(rig,frames)
    masks={n:stance_pairs(raw,n,24) for n in FOOT_NAMES};before=statistics(raw,masks,24)
    release_frames=performance['releaseFrames'] if performance else 12
    corrections={f:{n:Vector((0,0,0)) for n in FOOT_NAMES} for f in range(start,end+release_frames+1)};segments={};limit=.35
    for name in FOOT_NAMES:
        runs=intervals(masks[name]);segments[name]=[[start+a,start+b] for a,b in runs]
        for a,b in runs:
            anchor=raw[a][name].copy();last=Vector((0,0,0))
            for index in range(a,b+1):
                delta=anchor-raw[index][name];delta.z=0
                if delta.length>limit:delta*=limit/delta.length
                # A short onset taper avoids an abrupt velocity change at touchdown.
                if performance:
                    from performance_math import smoother
                    delta*=smoother(min(1,(index-a)/4))
                else:delta*=smooth(min(1,(index-a)/2))
                corrections[start+index][name]=delta;last=delta
            for k in range(1,release_frames+1):
                f=start+b+k
                if f in corrections and corrections[f][name].length==0:
                    if performance:
                        from performance_math import release
                        corrections[f][name]=last*release(k,release_frames)
                    else:corrections[f][name]=last*release_weight(k,12)
    # Convert world correction vectors into native bone location channels without changing constraints.
    local={};native_lengths={}
    for frame,values in corrections.items():
        bpy.context.scene.frame_set(frame);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());local[frame]={}
        native_lengths[frame]={n:(e.pose.bones[n].tail-e.pose.bones[n].head).length for n in ('DEF_Thigh.L','DEF_Thigh.R','DEF_Shin.L','DEF_Shin.R')}
        for name,delta in values.items():
            current=e.matrix_world@e.pose.bones[name].matrix
            target=current.copy();target.translation+=delta
            a=rig.convert_space(pose_bone=rig.pose.bones[name],matrix=current,from_space='WORLD',to_space='LOCAL')
            b=rig.convert_space(pose_bone=rig.pose.bones[name],matrix=target,from_space='WORLD',to_space='LOCAL')
            local[frame][name]=b.translation-a.translation
    action=bpy.data.actions.new('Wolf.Controller.StanceCorrection.v2' if performance else 'Wolf.Controller.StanceCorrection.v1');action.use_fake_user=True;rig.animation_data.action=action
    for frame,values in local.items():
        for name,value in values.items():rig.pose.bones[name].location=value;rig.pose.bones[name].keyframe_insert('location',frame=frame)
    slot=rig.animation_data.action_slot
    for c in action_get_channelbag_for_slot(action,slot).fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    rig.animation_data.action=None
    for name in FOOT_NAMES:rig.pose.bones[name].location=(0,0,0)
    track=rig.animation_data.nla_tracks.new();track.name='Controller.StanceCorrection'
    strip=track.strips.new('Bounded native IK stance offsets',start,action);strip.action_slot=slot;strip.extrapolation='NOTHING';strip.blend_type='ADD'
    curves=list(action_get_channelbag_for_slot(action,slot).fcurves)
    originals=[[k.co.y for k in c.keyframe_points] for c in curves]
    allowed=[];safety_limit=1.05
    def set_gain(index,gain):
        for c,values in zip(curves,originals):c.keyframe_points[index].co.y=values[index]*gain;c.update()
        action.update_tag();rig.update_tag()
    def ratio(frame):
        bpy.context.scene.frame_set(frame);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return max((e.pose.bones[n].tail-e.pose.bones[n].head).length/max(length,1e-6) for n,length in native_lengths[frame].items())
    correction_frames=list(local)
    for index,frame in enumerate(correction_frames):
        if ratio(frame)<=safety_limit:allowed.append(1);continue
        low,high=0.,1.
        for _ in range(7):
            mid=(low+high)/2;set_gain(index,mid)
            if ratio(frame)<=safety_limit:low=mid
            else:high=mid
        allowed.append(low)
    # Anticipate safety limits without a one-frame gain discontinuity; never exceed a safe per-frame gain.
    if performance:
        from performance_math import safety_envelope
        gains=safety_envelope(allowed,.045)
    else:gains=[min(allowed[max(0,i-3):min(len(allowed),i+4)]) for i in range(len(allowed))]
    for index,gain in enumerate(gains):set_gain(index,gain)
    verified_max=max(ratio(frame) for frame in correction_frames)
    if verified_max>safety_limit+.001:raise ValueError('Foot stabilization exceeded native leg stretch safety limit')
    after_samples=capture_feet(rig,frames);after=statistics(after_samples,masks,24)
    # Identical baseline-defined masks are used before and after; no cherry-picking corrected contacts.
    compare_frames=list(range(start+5,end-5))
    # Baseline original Phase 3 samples, same frame interval, supplied by a read-only capture.
    baseline_path=job/'baseline-feet.json';comparison=None
    if baseline_path.exists():
        baseline=json.loads(baseline_path.read_text());samples=baseline['samples'];base_masks={n:stance_pairs(samples,n,24) for n in FOOT_NAMES}
        # Report both shared temporal masks and independently detected masks for transparency.
        current=after_samples[5:5+len(samples)]
        legacy_masks={n:[max(a[n][2],b[n][2])<min(p[n][2] for p in samples)+.045 for a,b in zip(samples,samples[1:])] for n in FOOT_NAMES}
        comparison={'baselineJob':baseline['job'],'frames':[compare_frames[0],compare_frames[-1]],'before':statistics(samples,base_masks,24),'afterSameBaselineMasks':statistics(current,base_masks,24),'legacyHeightOnly':{'before':statistics(samples,legacy_masks,24),'afterSameBaselineMasks':statistics(current,legacy_masks,24),'definition':'Original Phase 3 height-only 4.5cm proxy, identical saved-baseline masks'},'definition':'height <= per-foot minimum + 4.5cm AND absolute vertical speed <= 0.16m/s; identical baseline masks for paired comparison'}
    return {'implemented':True,'legStretchSafetyLimitRatio':safety_limit,'verifiedMaxLegLengthRatio':verified_max,'safetyGainRange':[min(gains),max(gains)],'method':'bounded ADD offsets on original Foot IK controls; no constraints disabled','maxCorrectionMeters':max(v.length for row in corrections.values() for v in row.values()),'correctionLimitMeters':limit,'releaseFrames':release_frames,'maxSafetyGainStep':max(abs(b-a) for a,b in zip(gains,gains[1:])),'contactGapBridgeFrames':3,'stanceIntervals':segments,'before':before,'afterSameMasks':after,'pairedPhase3Comparison':comparison,'contactDefinition':'height and vertical velocity; control-origin proxy, not a sole/pressure sensor','humanVisualReviewRequired':True}

def finalize_quality(job,report):
    rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body'];scene=bpy.context.scene
    if (job/'baseline-feet.json').exists():
        baseline=json.loads((job/'baseline-feet.json').read_text());samples=baseline['samples'];frames=list(range(78,187));current=capture_feet(rig,frames)
        masks={n:stance_pairs(samples,n,24) for n in FOOT_NAMES}
        legacy_masks={n:[max(a[n][2],b[n][2])<min(p[n][2] for p in samples)+.045 for a,b in zip(samples,samples[1:])] for n in FOOT_NAMES}
        paired=report['animationQuality']['footContact']['pairedPhase3Comparison']
        paired.update(before=statistics(samples,masks,24),afterSameBaselineMasks=statistics(current,masks,24),legacyHeightOnly={'before':statistics(samples,legacy_masks,24),'afterSameBaselineMasks':statistics(current,legacy_masks,24),'definition':'Original Phase 3 height-only mask, unchanged baseline frames 78..186'})
        paired['meanReductionFraction']=1-paired['afterSameBaselineMasks']['meanMetersPerSecond']/paired['before']['meanMetersPerSecond']
    track=next(t for t in rig.animation_data.nla_tracks if t.name=='Controller.StanceCorrection')
    lengths={};foot_motion={};foot_peaks={}
    for enabled in [False,True]:
        track.mute=not enabled;records=[];feet=[]
        for f in range(73,193+report['animationQuality']['footContact'].get('releaseFrames',12)):
            bpy.context.scene.frame_set(f);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());records.append({n:(e.pose.bones[n].tail-e.pose.bones[n].head).length for n in ('DEF_Thigh.L','DEF_Thigh.R','DEF_Shin.L','DEF_Shin.R')})
            feet.append({n:e.matrix_world@e.pose.bones[n].matrix.translation for n in FOOT_NAMES})
        lengths[enabled]=records
        candidates=[{'frameFrom':73+i,'frameTo':74+i,'bone':n,'distanceMeters':(b[n]-a[n]).length} for i,(a,b) in enumerate(zip(feet,feet[1:])) for n in FOOT_NAMES]
        foot_peaks[enabled]=max(candidates,key=lambda v:v['distanceMeters']);foot_motion[enabled]=foot_peaks[enabled]['distanceMeters']
    track.mute=False
    max_ratio=max(b[n]/max(a[n],1e-6) for a,b in zip(lengths[False],lengths[True]) for n in a)
    report['animationQuality']['footContact'].update(maxAdjacentFootStepBeforeMeters=foot_motion[False],maxAdjacentFootStepAfterMeters=foot_motion[True],maxLegSegmentLengthRatio=max_ratio,peakFootStepBefore=foot_peaks[False],peakFootStepAfter=foot_peaks[True],legStretchVisualReviewRequired=max_ratio>1.1,measurementCaveat='Control origins and bone lengths are proxies; sole contact/collision is not mathematically established')
    report['animationQuality']['transitions']['boundaries']=[]
    for a,b in zip(report['schedule'],report['schedule'][1:]):
        delta=native.mesh_delta(native.points(body,a['endFrame']),native.points(body,b['startFrame']))
        report['animationQuality']['transitions']['boundaries'].append({'from':a['type'],'to':b['type'],'frame':b['startFrame'],'meshDelta':delta,'unusual':delta['rms']>.15})
    wave=next(i for i in report['schedule'] if i['type']=='wave')
    distances=[];angles=[]
    for f in range(wave['startFrame'],wave['endFrame']+1):
        bpy.context.scene.frame_set(f);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        def point(n):return e.matrix_world@e.pose.bones[n].matrix.translation
        wrist=point('FK_Hand.R');head=point('Head');distances.append((wrist-head).length)
        if wave['startFrame']+24<=f<=wave['endFrame']-16:
            elbow=point('FK_Forearm.R');shoulder=point('FK_UpperArm.R');a=(shoulder-elbow).normalized();b=(wrist-elbow).normalized();angles.append(math.degrees(math.acos(max(-1,min(1,a.dot(b))))))
    report['animationQuality']['wave'].update(minWristHeadControlDistanceMeters=min(distances),elbowInteriorDegreesDuringWave=[min(angles),max(angles)],collisionCheckScope='Control distances only; mesh self-intersection requires visual review',closeApproachVisualReviewRequired=min(distances)<.35)
    report['facialExperiments']={'status':'not_run_in_polish_scope','includedInDemo':False}
    report['animationQuality']['knownLimitations']=['Contact/control-origin proxies rather than sole-pressure measurements','Corrections bounded to 35cm; residual toe-off drift remains','Turn-in-place contacts are not locked','No mesh self-collision solver; gesture deformation needs human approval','Medium shots intentionally crop the lower body','Commercial use remains unverified']


def render_foot_diagnostics(job):
    scene=bpy.context.scene;original=scene.camera;camera=original.copy();camera.data=original.data.copy();camera.animation_data_clear();camera.data.animation_data_clear();scene.collection.objects.link(camera);scene.camera=camera
    camera.data.ortho_scale=6.2;paths=[]
    motion=bpy.data.objects['CharacterMotion']
    for frame in (126,188,196,204):
        scene.frame_set(frame);target=motion.location+Vector((0,0,1.4));camera.location=target+Vector((2,-10,1.2));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.stamp_note_text='Full-body foot-motion diagnostic | frame '+str(frame);filename=job/'previews'/('foot-stop-%03d.png'%frame);scene.render.filepath=str(filename);bpy.ops.render.render(write_still=True);paths.append(str(filename))
    scene.camera=original
    report=json.loads((job/'animation-report.json').read_text());report['footStopDiagnosticPreviews']=paths;(job/'animation-report.json').write_text(json.dumps(report,indent=2))
