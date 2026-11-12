"""Independent bone channels for Pebble expressions; never key body channels."""
import bpy

def apply_expressions(rig, expressions, frame_end):
    action=bpy.data.actions.new('PebbleFacialSequence')
    rig.animation_data.action=action
    names=[b.name for b in rig.pose.bones if b.name.startswith('face.')]
    def reset():
        for name in names:
            b=rig.pose.bones[name];b.scale=(1,1,1);b.location=(0,0,0);b.rotation_euler=(0,0,0)
    def key(frame, selected, properties=('scale','location','rotation_euler')):
        for name in selected:
            b=rig.pose.bones[name]
            for data in properties: b.keyframe_insert(data,frame=frame)
    reset();key(1,names);key(frame_end,names)
    for expression in sorted(expressions,key=lambda e:e['startFrame']):
        name=expression['name'];start=expression['startFrame'];end=expression['endFrame'];value=expression['intensity']
        selected=([n for n in names if '.eye.' in n or '.pupil.' in n] if name=='blink' else
                  [n for n in names if '.pupil.' in n] if name.startswith('look_') else
                  [n for n in names if '.mouth' in n or '.brow.' in n])
        properties=('scale',) if name=='blink' else ('location',) if name.startswith('look_') else ('scale','location','rotation_euler')
        reset();key(start,selected,properties)
        if name=='blink':
            for n in selected: rig.pose.bones[n].scale.y=1-.96*value
        elif name.startswith('look_'):
            for n in selected: rig.pose.bones[n].location.x=(.05 if name=='look_right' else -.05)*value
        elif name=='smile':
            rig.pose.bones['face.mouth'].scale.y=1+3*value
            for n in selected:
                if '.brow.' in n: rig.pose.bones[n].location.y=.025*value
        elif name=='sad': rig.pose.bones['face.mouth'].scale.y=1-3*value
        elif name=='surprised':
            rig.pose.bones['face.mouth'].scale=(1-.6*value,1+4*value,1)
            for n in selected:
                if '.brow.' in n: rig.pose.bones[n].location.y=.08*value
        if name=='blink':
            key((start+end)/2,selected,properties)
        else:
            fade=min(5,(end-start)/3)
            key(start+fade,selected,properties);key(end-fade,selected,properties)
        reset();key(end,selected,properties)
    slot=rig.animation_data.action_slot
    rig.animation_data.action=None
    track=rig.animation_data.nla_tracks.new();track.name='IndependentFacialControls'
    strip=track.strips.new('Facial expressions',1,action);strip.action_slot=slot
    strip.extrapolation='HOLD';strip.blend_type='REPLACE'
