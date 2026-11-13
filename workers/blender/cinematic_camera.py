import bpy,math
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from bpy_extras.object_utils import world_to_camera_view
import wolf_native as native
from motion_utils import smooth

def frame_projector(scene,camera):
    """Equivalent orthographic projection with camera constants cached per frame."""
    if camera.data.type!='ORTHO':return lambda point:world_to_camera_view(scene,camera,point)
    inverse=camera.matrix_world.normalized().inverted()
    corners=camera.data.view_frame(scene=scene)
    left=min(p.x for p in corners);bottom=min(p.y for p in corners)
    width=max(p.x for p in corners)-left;height=max(p.y for p in corners)-bottom
    def project(point):
        local=inverse@point
        return Vector(((local.x-left)/width,(local.y-bottom)/height,-local.z))
    return project

def schedule(scene,body,motion,shots):
    camera=scene.camera;fps=scene.render.fps;aspect=scene.render.resolution_x/scene.render.resolution_y
    all_bounds={};positions={}
    for f in range(1,scene.frame_end+1):
        all_bounds[f]=native.bounds(native.points(body,f));positions[f]=motion.location.copy()
    presets={}
    for preset in {s['preset'] for s in shots}:
        frames=[f for shot in shots if shot['preset']==preset for f in range(round(shot['start']*fps)+1,round(shot['end']*fps)+1)]
        low=min(all_bounds[f][0][2] for f in frames);high=max(all_bounds[f][1][2] for f in frames)
        crop=low if preset=='wide' else low+.9 if preset=='medium' else high-.85
        scale=max((high-crop)*aspect*1.2,2 if preset!='wide' else 4.5)
        presets[preset]={'cropZ':crop,'topZ':high,'targetZ':(crop+high)/2,'scale':scale}
    camera.animation_data_clear();camera.data.animation_data_clear()
    previous=None;records=[];cuts=[]
    for shot in shots:
        start=round(shot['start']*fps)+1;end=round(shot['end']*fps);definition=presets[shot['preset']]
        first_previous=previous
        record={'startFrame':start,'endFrame':end,**shot,'intentionalCut':shot['transition']=='cut' and start>1,'framesChecked':0,'framingFailures':[]}
        if record['intentionalCut']:cuts.append(start)
        for frame in range(start,end+1):
            root=positions[frame];target_x=root.x*(.65 if shot['preset']=='wide' else 1)
            target=Vector((target_x,root.y,definition['targetZ']));location=target+Vector((0,-10,1.1))
            rotation=(target-location).to_track_quat('-Z','Y')
            scale=definition['scale']
            if shot['transition']=='smooth' and first_previous and frame<start+shot['transitionFrames']:
                u=smooth((frame-start+1)/shot['transitionFrames']);location=first_previous[0].lerp(location,u);rotation=first_previous[1].slerp(rotation,u);scale=first_previous[2]+(scale-first_previous[2])*u
            camera.location=location;camera.rotation_euler=rotation.to_euler();camera.data.ortho_scale=scale
            camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame);camera.data.keyframe_insert('ortho_scale',frame=frame)
            previous=(location.copy(),rotation.copy(),scale)
        records.append(record)
    for owner in [camera,camera.data]:
        if owner.animation_data:
            for c in action_get_channelbag_for_slot(owner.animation_data.action,owner.animation_data.action_slot).fcurves:
                for key in c.keyframe_points:key.interpolation='LINEAR'
    max_continuous=0;last=None
    for record in records:
        crop=presets[record['preset']]['cropZ']
        for frame in range(record['startFrame'],record['endFrame']+1):
            pts=native.points(body,frame);scene.view_layers[0].update();region=[p for p in pts if p.z>=crop-.015] if record['preset']!='wide' else pts
            for p in region:
                uv=world_to_camera_view(scene,camera,p)
                if not (.015<uv.x<.985 and .015<uv.y<.985 and uv.z>0):record['framingFailures'].append(frame);break
            record['framesChecked']+=1
            if last is not None and frame not in cuts:max_continuous=max(max_continuous,(camera.location-last).length)
            last=camera.location.copy()
        if record['framingFailures']:raise ValueError('Shot framing failed: '+str(record))
    return {'shots':records,'presets':presets,'intentionalCutFrames':cuts,'maxContinuousCameraStepMeters':max_continuous,'fullBodyRequiredOnlyForWide':True,'humanVisualReviewRequired':True}


def schedule_multi(scene, bodies, shots, anchor=None):
    """Fit declared subjects using evaluated bounds; stable lens per shot, explicit cuts."""
    camera=scene.camera;fps=scene.render.fps;aspect=scene.render.resolution_x/scene.render.resolution_y
    camera.animation_data_clear();camera.data.animation_data_clear();records=[]
    for shot in shots:
        start=round(shot['start']*fps)+1;end=round(shot['end']*fps)
        frames={}
        for frame in range(start,end+1):
            pts=[p for name in shot['subjects'] for p in native.points(bodies[name],frame)]
            lo,hi=native.bounds(pts);crop=lo[2]+.9 if shot['type']=='medium' else lo[2]
            frames[frame]=(lo,hi,crop)
        scale=max(max(2*max(abs(lo[0]-anchor[0]),abs(hi[0]-anchor[0])) if anchor else hi[0]-lo[0],(hi[2]-crop)*aspect)*1.22 for lo,hi,crop in frames.values())
        if anchor and any(anchor[1]>=lo[1] for lo,hi,crop in frames.values()):raise ValueError('Fixed camera anchor must lie in front of all intended subjects (-Y side)')
        for frame,(lo,hi,crop) in frames.items():
            scene.frame_set(frame)
            target=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,(crop+hi[2])/2))
            camera.location=Vector((anchor[0],anchor[1],target.z)) if anchor else target+Vector((0,-15,0))
            camera.rotation_euler=Vector((0,1,0)).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
            camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame);camera.data.keyframe_insert('ortho_scale',frame=frame)
        records.append({**shot,'startFrame':start,'endFrame':end,'scale':scale,'framesChecked':end-start+1})
    for owner in [camera,camera.data]:
        for curve in action_get_channelbag_for_slot(owner.animation_data.action,owner.animation_data.action_slot).fcurves:
            for key in curve.keyframe_points:key.interpolation='CONSTANT' if int(key.co.x)+1 in [r['startFrame'] for r in records] else 'LINEAR'
    return records
