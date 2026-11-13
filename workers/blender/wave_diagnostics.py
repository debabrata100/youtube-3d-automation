"""Wolf adapter diagnostics in calibrated character coordinates, independent of yaw."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
import wolf_native as native

CONFIG=json.loads((Path(__file__).resolve().parents[2]/'assets/characters/wolf-warrior/animation-config.json').read_text())['forwardWave']
CONTROLS=CONFIG['controls']

def evaluated_controls(rig):
    e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return e,{k:e.matrix_world@e.pose.bones[n].matrix.translation for k,n in CONTROLS.items()}

def regions(body):
    if any(m.type not in ('ARMATURE','TRIANGULATE') for m in body.modifiers):raise ValueError('Wave diagnostics require verified evaluated vertex correspondence')
    names={g.index:g.name for g in body.vertex_groups};result={k:[] for k in ('torso','chest','hand','forearm')}
    def matches(k,n):
        if k=='torso':return n.startswith(('DEF_Chest','DEF_Spine'))
        if k=='chest':return n.startswith('DEF_Chest')
        if k=='forearm':return n.startswith('DEF_Forearm') and n.endswith('.R')
        return n.startswith('DEF_') and n.endswith('.R') and ('Hand' in n or 'Finger' in n)
    for vertex in body.data.vertices:
        for k in result:
            if sum(g.weight for g in vertex.groups if matches(k,names[g.group]))>=.3:result[k].append(vertex.index)
    if any(not ids for ids in result.values()):raise ValueError('Missing calibrated mesh region')
    return result

def calibrate(rig,body,frame):
    bpy.context.scene.frame_set(frame);e,p=evaluated_controls(rig)
    # Derive anatomical forward from this rig, then transport it through the rig matrix.
    rest=rig.data.bones[CONTROLS['nose']].head_local-rig.data.bones[CONTROLS['head']].head_local
    up=e.matrix_world.to_3x3().inverted()@Vector((0,0,1));up.normalize();rest-=up*rest.dot(up);rest.normalize()
    forward=e.matrix_world.to_3x3()@rest;forward.normalize()
    observed=p['nose']-p['head'];observed.z=0;observed.normalize()
    if forward.dot(observed)<.98:raise ValueError('Rest/evaluated anatomical forward disagree; recalibrate adapter')
    ids=regions(body);pts=native.points(body,frame)
    length=(p['shoulder']-p['elbow']).length+(p['elbow']-p['wrist']).length
    front=max((pts[i]-p['chest']).dot(forward) for i in ids['chest'])
    return {'localForward':list(rest),'observedWorldForward':list(observed),'armLengthMeters':length,'chestFrontExtentMeters':front,'marginMeters':length*.05,'requiredWristForwardMeters':front+length*.05,'method':'Head-to-nose anatomical direction; idle evaluated >=30% chest-weighted front extent plus 5% arm-length clearance','palmNormalLocal':CONFIG['palmNormalLocal'],'palmCalibrationRevision':CONFIG['palmCalibrationRevision'],'palmCalibrationEvidence':CONFIG['palmCalibration'],'regions':ids}

def measure(rig,body,start,end,camera=None,enforce=True):
    scene=bpy.context.scene;cal=calibrate(rig,body,start);ids=cal.pop('regions');rows=[];intersections=[];projection_failures=[];last=None;maxstep=0
    body.data.calc_loop_triangles();sets={k:set(v) for k,v in ids.items()}
    faces={k:[tuple(t.vertices) for t in body.data.loop_triangles if all(i in sets[k] for i in t.vertices)] for k in ('torso','hand','forearm')}
    minimum_gap=float('inf');rotation_previous={};rotation_step=0
    for frame in range(start,end+1):
        pts=native.points(body,frame);e,p=evaluated_controls(rig);forward=e.matrix_world.to_3x3()@Vector(cal['localForward']);forward.normalize()
        for control in ('shoulder','elbow','wrist'):
            q=e.pose.bones[CONTROLS[control]].matrix.to_quaternion()
            if control in rotation_previous:
                angle=rotation_previous[control].rotation_difference(q).angle
                rotation_step=max(rotation_step,min(angle,2*math.pi-angle))
            rotation_previous[control]=q.copy()
        offset=p['wrist']-p['chest'];a=p['shoulder']-p['elbow'];b=p['wrist']-p['elbow'];angle=math.degrees(a.angle(b))
        t=(frame-start)/max(1,end-start);active=.44<=t<=.70
        row={'frame':frame,'phase':t,'activeGreeting':active,'wristForwardMeters':offset.dot(forward),'wristAboveChestMeters':offset.z,'wristAboveHeadMeters':p['wrist'].z-p['head'].z,'elbowForwardMeters':(p['elbow']-p['chest']).dot(forward),'elbowAngleDegrees':angle,'characterForwardWorld':list(forward)}
        row['wristWorld']=list(p['wrist'])
        row['elbowWorld']=list(p['elbow'])
        hand_matrix=e.matrix_world.to_3x3()@e.pose.bones[CONTROLS['wrist']].matrix.to_3x3()
        palm=(hand_matrix@Vector(CONFIG['palmNormalLocal'])).normalized();fingers=(hand_matrix@Vector((0,1,0))).normalized()
        row['palmForwardAlignment']=palm.dot(forward);row['fingersUpAlignment']=fingers.dot(Vector((0,0,1)))
        rows.append(row)
        if last is not None:maxstep=max(maxstep,(p['wrist']-last).length)
        last=p['wrist'].copy()
        torso=native.bounds([pts[i] for i in ids['torso']])
        for region in ('hand','forearm'):
            box=native.bounds([pts[i] for i in ids[region]])
            gap=math.sqrt(sum(max(0,torso[0][i]-box[1][i],box[0][i]-torso[1][i])**2 for i in range(3)))
            minimum_gap=min(minimum_gap,gap)
            if gap<1e-6:
                overlap=BVHTree.FromPolygons(pts,faces['torso'],all_triangles=True).overlap(BVHTree.FromPolygons(pts,faces[region],all_triangles=True))
                if overlap:intersections.append({'frame':frame,'region':region,'trianglePairs':len(overlap)})
        if camera and active:
            scene.view_layers[0].update()
            projected=[world_to_camera_view(scene,camera,pts[i]) for i in ids['hand']]
            if any(not(.015<uv.x<.985 and .015<uv.y<.985 and uv.z>0) for uv in projected):projection_failures.append(frame)
            chest_uv=world_to_camera_view(scene,camera,p['chest']);wrist_uv=world_to_camera_view(scene,camera,p['wrist']);row['cameraWristChestSeparationNormalized']=math.hypot(wrist_uv.x-chest_uv.x,wrist_uv.y-chest_uv.y)
    active=[r for r in rows if r['activeGreeting']]
    elbow_step=max((Vector(b['elbowWorld'])-Vector(a['elbowWorld'])).length for a,b in zip(rows,rows[1:]))
    failures=[]
    if min(r['wristForwardMeters'] for r in active)<cal['requiredWristForwardMeters']:failures.append('Raised wrist is not beyond calibrated chest-front clearance')
    if any(not(.25*cal['armLengthMeters']<r['wristAboveChestMeters']<1.05*cal['armLengthMeters']) or r['wristAboveHeadMeters']>.5*cal['armLengthMeters'] for r in active):failures.append('Raised wrist lies outside calibrated upper-chest/head silhouette band')
    if any(not 45<r['elbowAngleDegrees']<175 for r in active):failures.append('Elbow bend outside anatomical review range')
    if maxstep>.12*cal['armLengthMeters']:failures.append('Wrist frame step exceeds 12% arm length; possible snap')
    if elbow_step>.12*cal['armLengthMeters']:failures.append('Elbow frame step exceeds 12% arm length; possible snap')
    if rotation_step>.35:failures.append('Arm joint rotates over 0.35 radians in one frame; possible snap')
    if any(r['palmForwardAlignment']<.8 or r['fingersUpAlignment']<.8 for r in active):failures.append('Raised palm/fingers are not oriented toward partner/upright')
    if any(not 20<r['elbowAngleDegrees']<175 for r in rows):failures.append('Elbow straightens or reverses during transition')
    if intersections:failures.append('Weighted hand/forearm intersects weighted torso triangles')
    if projection_failures:failures.append('Raised hand is clipped by intended camera')
    if camera and any(r.get('cameraWristChestSeparationNormalized',1)<.05 for r in active):failures.append('Wrist overlaps chest control silhouette in intended camera')
    report={'calibration':cal,'samples':rows,'activeForwardMinimumMeters':min(r['wristForwardMeters'] for r in active),'activeForwardMaximumMeters':max(r['wristForwardMeters'] for r in active),'maximumWristStepMeters':maxstep,'minimumRegionAabbGapMeters':minimum_gap,'torsoTriangleIntersections':intersections,'cameraClippedFrames':projection_failures,'failures':failures,'passed':not failures,'collisionScope':'>=30% weighted torso, hand and forearm surface triangles; AABB broad phase then BVH overlap. Region seams/weak weights/fur still require visual review.','humanVisualApproval':'pending'}
    report['maximumElbowStepMeters']=elbow_step
    report['maximumJointRotationStepRadians']=rotation_step
    if enforce and failures:raise ValueError('Forward-wave diagnostics failed: '+str(failures))
    return report
