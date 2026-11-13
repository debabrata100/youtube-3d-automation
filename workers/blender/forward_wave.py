"""Bake a forward hand path onto native FK controls, without adding rig constraints."""
from copy import deepcopy
import bpy,math
from mathutils import Vector,Matrix,Quaternion
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from performance_refinement import wave_v3
from performance_math import smoother

def wave_v4(rig,config,parameters,start,end):
    definition=config['forwardWave'];calibrated=deepcopy(config)
    calibrated['waveOffsetsRadians']['upperArmXYZ']=[v/(.95*definition['referenceHandHeight']) for v in definition['shoulderOffsetRadians']]
    calibrated['waveOffsetsRadians']['forearmX']=definition['elbowOffsetRadians']
    action,slot=wave_v3(rig,calibrated,parameters,action_name='Wolf.Controller.Wave.v4')
    names=[definition['controls'][k] for k in ('shoulder','elbow')]
    curves=[c for c in action_get_channelbag_for_slot(action,slot).fcurves if any(n in c.data_path for n in names)]
    previous_tracks=[(t,t.mute) for t in rig.animation_data.nla_tracks if t.name.startswith('Controller.Wave')]
    for track,_ in previous_tracks:track.mute=True
    probe=bpy.data.actions.new('Wave.Calibration.Temporary');rig.animation_data.action=probe
    for name in names:
        rig.pose.bones[name].rotation_euler=(0,0,0)
        for frame in (0,1000):rig.pose.bones[name].keyframe_insert('rotation_euler',frame=frame)
    probe_slot=rig.animation_data.action_slot;rig.animation_data.action=None
    probe_curves=action_get_channelbag_for_slot(probe,probe_slot).fcurves
    track=rig.animation_data.nla_tracks.new();track.name='Wave.Calibration.Temporary'
    strip=track.strips.new('probe',0,probe);strip.action_slot=probe_slot;strip.blend_type='ADD';strip.extrapolation='NOTHING'
    scene=bpy.context.scene;old=(scene.frame_current,scene.frame_subframe)
    def wrist(values,time):
        for c in probe_curves:
            value=values[c.array_index] if names[0] in c.data_path else values[3] if c.array_index==0 else 0
            for key in c.keyframe_points:key.co.y=value;key.interpolation='LINEAR'
            c.update()
        probe.update_tag();rig.update_tag(refresh={'OBJECT'});scene.frame_set(math.floor(time),subframe=time%1)
        bpy.context.view_layer.update()
        e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return e.matrix_world@e.pose.bones[definition['controls']['wrist']].matrix.translation
    values=Vector((0,0,0,0));target_pose=Vector((*[v*parameters['handHeight']/definition['referenceHandHeight'] for v in definition['shoulderOffsetRadians']],definition['elbowOffsetRadians']))
    try:
        for frame in range(73):
            t=frame/72;time=start+(end-start)*t
            idle=wrist(Vector((0,0,0,0)),time);peak=wrist(target_pose,time)
            amount=smoother(t/.40)*(1-smoother((t-.64)/.36));target=idle.lerp(peak,amount)
            e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            forward=e.matrix_world@(rig.data.bones[definition['controls']['nose']].head_local)-e.matrix_world@(rig.data.bones[definition['controls']['head']].head_local)
            forward.z=0;forward.normalize();right=forward.cross(Vector((0,0,1)))
            target+=right*(.35*math.sin(math.pi*amount))
            if frame in (0,72):values=Vector((0,0,0,0))
            else:
                for iteration in range(60):
                    current=wrist(values,time);error=target-current
                    if error.length<.0002:break
                    columns=[]
                    for axis in range(4):
                        test=values.copy();test[axis]+=.01
                        columns.append((wrist(test,time)-current)/.01)
                    normal=Matrix([[sum(c[row]*c[col] for c in columns) for col in range(3)] for row in range(3)])
                    for axis in range(3):normal[axis][axis]+=.0001
                    solved=normal.inverted()@error
                    delta=Vector(tuple(c.dot(solved) for c in columns))
                    if delta.length>.18:delta*=.18/delta.length
                    accepted=False
                    for gain in (1,.5,.25,.1,-.1):
                        trial=values+delta*gain;trial[3]=max(-2.1,min(2.1,trial[3]))
                        if (wrist(trial,time)-target).length<error.length:
                            values=trial;accepted=True;break
                    if not accepted:break
                if (wrist(values,time)-target).length>.008:raise ValueError('Forward-wave FK target unreachable at key '+str(frame)+' values '+str(list(values))+' error '+str(list(target-wrist(values,time)))+' target '+str(list(target)))
            for c in curves:c.keyframe_points[frame].co.y=values[c.array_index] if names[0] in c.data_path else values[3] if c.array_index==0 else 0
        action.update_tag()
    finally:
        rig.animation_data.nla_tracks.remove(track);bpy.data.actions.remove(probe)
        for track,mute in previous_tracks:track.mute=mute
        scene.frame_set(old[0],subframe=old[1])
    return action,slot

def orient_palm(rig,action,slot,config,parameters,start,end):
    """Aim palm toward anatomical forward with fingers upright, then add wrist oscillation."""
    definition=config['forwardWave'];name=definition['controls']['wrist'];bone=rig.data.bones[name]
    curves=[c for c in action_get_channelbag_for_slot(action,slot).fcurves if name in c.data_path]
    tracks=[(t,t.mute) for t in rig.animation_data.nla_tracks if t.name.startswith('Controller.Wave')]
    scene=bpy.context.scene;old=(scene.frame_current,scene.frame_subframe);previous=None
    for key in range(73):
        t=key/72;time=start+(end-start)*t
        for track,_ in tracks:track.mute=True
        scene.frame_set(math.floor(time),subframe=time%1)
        base=rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones[name].rotation_euler.copy()
        for track,mute in tracks:track.mute=mute
        scene.frame_set(math.floor(time),subframe=time%1);e=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        forward=e.matrix_world@(rig.data.bones[definition['controls']['nose']].head_local)-e.matrix_world@(rig.data.bones[definition['controls']['head']].head_local)
        forward.z=0;forward.normalize();up=Vector((0,0,1))
        normal=forward*definition['palmNormalLocal'][2];side=up.cross(normal)
        target=Matrix((side,up,normal)).transposed().to_quaternion()
        parent=e.matrix_world@e.pose.bones[bone.parent.name].matrix@bone.parent.matrix_local.inverted()@bone.matrix_local
        parent_q=parent.to_quaternion();current=parent_q@base.to_quaternion()
        amount=smoother(t/.40)*(1-smoother((t-.64)/.36))
        progress=max(0,min(1,(t-.38)/.38));phase=progress+.025*math.sin(2*math.pi*progress)
        envelope=smoother((t-.34)/.10)*(1-smoother((t-.74)/.19))
        oscillation=envelope*parameters['wristAmplitude']*(1-.15*progress)*math.sin(4*math.pi*phase)
        target=target@Quaternion((0,0,1),oscillation)
        local=(parent_q.inverted()@current.slerp(target,amount)).to_euler('XYZ',previous or base);previous=local.copy()
        for c in curves:c.keyframe_points[key].co.y=0 if key in (0,72) else local[c.array_index]-base[c.array_index]
        action.update_tag()
    scene.frame_set(old[0],subframe=old[1])
