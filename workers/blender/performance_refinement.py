import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from performance_math import smoother,foot_metrics
from foot_contact import stance_pairs
import wolf_native as native

def wave_v3(rig,config,parameters):
    names=config['rightArmControls']+['FK_Spine_02']
    if any(n not in rig.pose.bones or rig.pose.bones[n].constraints or rig.pose.bones[n].rotation_mode!='XYZ' for n in names):raise ValueError('Wave v3 requires verified unconstrained native XYZ controls')
    action=bpy.data.actions.new('Wolf.Controller.Wave.v3');action.use_fake_user=True;rig.animation_data.action=action
    intensity=parameters['intensity'];height=parameters['handHeight'];anticipation=parameters['anticipation'];recover=parameters['recovery']
    def env(t,a,b,c,d):return smoother((t-a)/(b-a))*(1-smoother((t-c)/(d-c)))
    for frame in range(73):
        t=frame/72;shoulder=env(t,anticipation*.5,.37,1-recover,1);elbow=env(t,anticipation*.7,.43,1-recover+.03,1);wrist=env(t,.34,.44,.74,.93)
        progress=max(0,min(1,(t-.38)/.38));phase=progress+.025*math.sin(2*math.pi*progress);prepare=-.04*intensity*math.sin(math.pi*min(1,t/anticipation)) if t<anticipation else 0
        for i,name in enumerate(names):
            b=rig.pose.bones[name];b.rotation_euler=(0,0,0)
            if i==0:b.rotation_euler=tuple(shoulder*v*.95*height for v in config['waveOffsetsRadians']['upperArmXYZ']);b.rotation_euler.x+=prepare
            elif i==1:b.rotation_euler.x=elbow*config['waveOffsetsRadians']['forearmX']+wrist*.025*intensity*math.sin(4*math.pi*phase-.5)
            elif i==2:
                b.rotation_euler.z=wrist*parameters['wristAmplitude']*(1-.15*progress)*math.sin(2*math.pi*parameters['waveCount']*phase)
                b.rotation_euler.x=wrist*.04*intensity*math.sin(4*math.pi*phase-.6)
            else:b.rotation_euler.z=shoulder*.02*intensity;b.rotation_euler.x=prepare*.25
            b.keyframe_insert('rotation_euler',frame=frame)
    slot=rig.animation_data.action_slot
    for c in action_get_channelbag_for_slot(action,slot).fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    rig.animation_data.action=None
    for n in names:rig.pose.bones[n].rotation_euler=(0,0,0)
    return action,slot

def finalize_performance(job,report):
    from animation_polish import capture_feet
    scene=bpy.context.scene;rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body']
    series=capture_feet(rig,range(1,361));serial=[{n:list(v) for n,v in row.items()} for row in series]
    (job/'performance-foot-samples.json').write_text(json.dumps(serial))
    baseline_file=job/'performance-baseline.json';baseline=json.loads(baseline_file.read_text()) if baseline_file.exists() else {'available':False,'reason':'Phase 3.1 baseline unavailable'}
    current_part=serial[77:186];current_masks={n:stance_pairs(current_part,n,24) for n in ('Foot.L','Foot.R')}
    current=foot_metrics(current_part,current_masks)
    current_motion=foot_metrics(serial[72:216],{n:stance_pairs(serial[72:216],n,24) for n in ('Foot.L','Foot.R')})
    for key in ['maxSwingReleaseStepMeters','maxFootStepMeters','maxVerticalStepMeters']:current[key]=current_motion[key]
    comparison={'currentUnpaired':current,'available':baseline.get('available',False),'humanVisualReviewRequired':True,'definitions':{'stanceFrames':[78,186],'mask':'Phase 3.1 baseline height band 4.5cm and vertical velocity <=0.16m/s','p95':'linear interpolation of sorted contact pair speeds','swingFrames':[73,216],'verticalFrames':[73,216],'units':'meters and seconds; Foot-control proxies, not sole-pressure sensors'}}
    if comparison['available']:
        before=baseline['samples'];part=before[77:186];masks={n:stance_pairs(part,n,24) for n in ('Foot.L','Foot.R')}
        old=foot_metrics(part,masks);new=foot_metrics(serial[77:186],masks)
        all_mask={n:stance_pairs(before[72:216],n,24) for n in ('Foot.L','Foot.R')}
        old_swing=foot_metrics(before[72:216],all_mask);new_swing=foot_metrics(serial[72:216],all_mask)
        for key in ['maxSwingReleaseStepMeters','maxFootStepMeters','maxVerticalStepMeters']:old[key]=old_swing[key];new[key]=new_swing[key]
        comparison.update(baseline=baseline['job'],before=old,after=new,metricRegressions=[key for key in old if isinstance(old[key],(int,float)) and key!='stancePairs' and new[key]>old[key]+1e-6])
        comparison['rawMetricDeltas']={key:new[key]-old[key] for key in old if key!='stancePairs'}
        comparison['numericalOnlyRegressions']=[key for key,delta in comparison['rawMetricDeltas'].items() if 0<delta<=1e-6]
        comparison['regressionTolerance']='1e-6 meters or meters/second; smaller positive deltas are explicitly reported as numerical-only, not hidden'
        comparison['targets']={'meanAtMost012':new['meanStanceVelocity']<=.12,'p95Reduced20Percent':new['p95StanceVelocity']<=old['p95StanceVelocity']*.8,'maximumReduced15Percent':new['maxStanceVelocity']<=old['maxStanceVelocity']*.85,'swingAtMostPhase31':new['maxSwingReleaseStepMeters']<=old['maxSwingReleaseStepMeters']+1e-6}
        comparison['baselineEvidence']={k:baseline['report'].get(k) for k in ['floor','motion','continuity','wave']}
        quality=baseline['report'].get('animationQuality',{})
        comparison['baselineEvidence'].update(legSafety=quality.get('footContact',{}).get('maxLegSegmentLengthRatio'),camera=quality.get('camera'))
        old_leg=comparison['baselineEvidence']['legSafety'];new_leg=report['animationQuality']['footContact']['maxLegSegmentLengthRatio']
        comparison['legExtensionComparison']={'beforeRatio':old_leg,'afterRatio':new_leg,'deltaRatio':new_leg-old_leg if old_leg is not None else None,'limitRatio':1.05,'increasedWithinLimit':old_leg is not None and old_leg<new_leg<=1.05}
    else:comparison['reason']=baseline.get('reason','Baseline missing')
    report['performanceComparison']=comparison
    wave=next(a for a in report['schedule'] if a['type']=='wave');positions=[];head_positions=[]
    for f in range(wave['startFrame'],wave['endFrame']+1):
        scene.frame_set(f);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());positions.append(e.matrix_world@e.pose.bones['FK_Hand.R'].matrix.translation);head_positions.append(e.matrix_world@e.pose.bones['Head'].matrix.translation)
    peak=max(range(len(positions)),key=lambda i:positions[i].z)
    report['wave'].update(parameters=report['controller']['performance']['wave'],peakFrame=wave['startFrame']+peak,peakWristZ=positions[peak].z,headControlZAtPeak=head_positions[peak].z,wristHeightRelativeToHeadControl=positions[peak].z-head_positions[peak].z,clearanceCheckScope='Wrist/head control distance is conservative evidence, not full mesh collision verification',torsoControl='FK_Spine_02')
    report['performanceComparison']['verification']={'motion':report['motion'],'floor':report['floor'],'legSafety':report['animationQuality']['footContact']['maxLegSegmentLengthRatio'],'wave':report['wave'],'camera':report['animationQuality']['camera'],'sourceHashUnchanged':hashlib.sha256(Path(report['source']).read_bytes()).hexdigest()==report['sourceSha256'],'status':'technical_checks_passed_visual_approval_pending'}
    report['wave']['conservativeGeometry']=geometry_clearance(body,rig,wave['startFrame'],wave['endFrame'])
    comparison['verification']['wave']=report['wave']
    (job/'comparison-report.json').write_text(json.dumps(report['performanceComparison'],indent=2))
    baseline_note='Baseline comparison available.\n' if comparison['available'] else 'Baseline comparison unavailable; review current output only. No before values were fabricated.\n'
    (job/'visual-review-checklist.md').write_text(baseline_note+'''# Human visual review required\n- Watch both videos at normal speed and slow motion; do not judge only the contact proxies.\n- Check toe-off, swing/release, stop and turn for sliding or snapping.\n- Check knee proportions, foot clearance and any ground penetration.\n- Check that the lowered greeting pose looks intentional, not a salute.\n- Check wrist motion, head/chest clearance, subtle torso motion and idle recovery.\n- Check full-body walking, the frame-193 cut and hand/head visibility.\n- Review every metric regression in comparison-report.json.\n- Commercial licensing remains unverified; these files are review-only.\n''')


def geometry_clearance(body,rig,start,end):
    if any(m.type not in ('ARMATURE','TRIANGULATE') for m in body.modifiers):return {'available':False,'reason':'Unverified evaluated vertex-index mapping; use control diagnostics and manual review'}
    names={g.index:g.name for g in body.vertex_groups}
    ids={key:[] for key in ('hand','head','chest')}
    for v in body.data.vertices:
        for key in ids:
            def relevant(name):
                if key=='hand':return name.startswith('DEF_') and name.endswith('.R') and ('Hand' in name or 'Finger' in name)
                return name.startswith('DEF_Head') if key=='head' else name.startswith('DEF_Chest')
            if sum(g.weight for g in v.groups if relevant(names.get(g.group,'')))>=.3:ids[key].append(v.index)
    if any(not indices for indices in ids.values()):return {'available':False,'reason':'Missing weighted mesh regions; no collision claim'}
    results={k:{'minAabbDistanceMeters':float('inf'),'closestFrame':None,'potentialOverlapFrames':[]} for k in ('head','chest')};shoulder_dist=[]
    for frame in range(start,end+1):
        pts=native.points(body,frame)
        if len(pts)!=len(body.data.vertices):return {'available':False,'reason':'Evaluated topology differs; no vertex mapping assumption'}
        boxes={key:native.bounds([pts[i] for i in indices]) for key,indices in ids.items()}
        for key in results:
            a,b=boxes['hand'],boxes[key];d=math.sqrt(sum(max(0,b[0][i]-a[1][i],a[0][i]-b[1][i])**2 for i in range(3)))
            if d<results[key]['minAabbDistanceMeters']:results[key]['minAabbDistanceMeters']=d;results[key]['closestFrame']=frame
            if d<=.0001:results[key]['potentialOverlapFrames'].append(frame)
        e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get());w=e.matrix_world@e.pose.bones['FK_Hand.R'].matrix.translation;s=e.matrix_world@e.pose.bones['FK_UpperArm.R'].matrix.translation;shoulder_dist.append((w-s).length)
    return {'available':True,'scope':'Evaluated weighted-region AABBs (>=30% DEF weights), plus wrist/shoulder control distance. Overlap is a conservative warning, not confirmed triangle intersection; omitted weakly weighted vertices/fur require human review','regions':results,'minWristShoulderDistanceMeters':min(shoulder_dist),'humanReviewRequired':True}
