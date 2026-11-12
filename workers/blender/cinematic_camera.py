import bpy,math
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from bpy_extras.object_utils import world_to_camera_view
import wolf_native as native
from motion_utils import smooth

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
