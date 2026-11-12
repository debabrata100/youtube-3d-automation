"""Original rigid-segment test rig and reusable slotted Actions (Blender 5.x)."""
import bpy
import math
from pathlib import Path
from bpy_extras.anim_utils import action_get_channelbag_for_slot

BONES = {
    'root': ((0,0,0),(0,0,.3),None),
    'torso': ((0,0,1),(0,0,1.9),'root'),
    'head': ((0,0,1.9),(0,0,2.5),'torso'),
    'arm.L': ((-.48,0,1.85),(-.48,0,.95),'torso'),
    'arm.R': ((.48,0,1.85),(.48,0,.95),'torso'),
    'leg.L': ((-.24,0,1),(-.24,0,.08),'root'),
    'leg.R': ((.24,0,1),(.24,0,.08),'root'),
}

def curves(action, slot):
    bag = action_get_channelbag_for_slot(action, slot)
    return bag.fcurves if bag else []

def generate(destination):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.object.armature_add()
    rig = bpy.context.object
    rig.name = 'DemoRig'
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in list(rig.data.edit_bones):
        rig.data.edit_bones.remove(bone)
    for name,(head,tail,parent) in BONES.items():
        b = rig.data.edit_bones.new(name)
        b.head, b.tail = head, tail
        if parent: b.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for name,(head,tail,_) in BONES.items():
        if name == 'root': continue
        center = tuple((a+b)/2 for a,b in zip(head,tail))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=center)
        obj = bpy.context.object
        obj.name = 'Demo.'+name
        obj.scale = (.34,.24,.45) if name == 'torso' else ((.32,.3,.34) if name == 'head' else (.13,.14,.46))
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mat = bpy.data.materials.new(name)
        color = (1,.55,.22,1) if name == 'head' else (.08,.3,.8,1)
        mat.diffuse_color = color
        mat.use_nodes = True
        mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color
        obj.data.materials.append(mat)
        # Rigid weights give every segment a real armature deformation modifier.
        obj.vertex_groups.new(name=name).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        obj.modifiers.new('Rig','ARMATURE').object = rig
        obj.parent = rig
    rig.animation_data_create()
    for kind in ('idle','walk','run','jump','wave'):
        action = bpy.data.actions.new('demo.'+kind+'.v1')
        action.use_fake_user = True
        rig.animation_data.action = action
        for frame in range(1,26):
            phase = (frame-1)/24*2*math.pi
            for name in BONES:
                bone = rig.pose.bones[name]
                bone.rotation_mode = 'XYZ'
                bone.rotation_euler = (0,0,0)
                bone.location = (0,0,0)
                if kind in ('walk','run'):
                    amplitude = .5 if kind == 'walk' else .85
                    if name.startswith('leg'): bone.rotation_euler.x = amplitude*math.sin(phase)*(1 if name.endswith('L') else -1)
                    if name.startswith('arm'): bone.rotation_euler.x = -amplitude*math.sin(phase)*(1 if name.endswith('L') else -1)
                elif kind == 'wave' and name == 'arm.R':
                    # Smoothly raise and lower the arm, wave above the shoulder.
                    envelope = min(1,(frame-1)/5,(25-frame)/5)
                    bone.rotation_euler.z = envelope*(2.4+.3*math.sin(phase*3))
                elif kind == 'jump' and name == 'root': bone.location.y = .7*math.sin(phase/2)
                elif kind == 'idle' and name == 'torso': bone.rotation_euler.x = .025*math.sin(phase)
                bone.keyframe_insert('rotation_euler',frame=frame)
                bone.keyframe_insert('location',frame=frame)
        for curve in curves(action,rig.animation_data.action_slot):
            for key in curve.keyframe_points: key.interpolation = 'LINEAR'
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.rotation_euler = (0,0,0)
        bone.location = (0,0,0)
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))


def load(asset):
    filename = asset['absolutePath']
    before = set(bpy.data.objects)
    suffix = Path(filename).suffix.lower()
    if suffix == '.blend':
        with bpy.data.libraries.load(filename, link=False) as (source,target):
            target.objects = source.objects
            target.actions = source.actions
        for action in target.actions:
            if action: action.use_fake_user = True
        for obj in target.objects:
            if obj: bpy.context.collection.objects.link(obj)
    elif suffix == '.glb': bpy.ops.import_scene.gltf(filepath=filename)
    elif suffix == '.fbx': bpy.ops.import_scene.fbx(filepath=filename)
    else: raise ValueError('Unsupported character format')
    objects = set(bpy.data.objects)-before
    rigs = [o for o in objects if o.type == 'ARMATURE' and o.name == asset['armature']]
    if len(rigs) != 1: raise ValueError('Expected registered armature: '+asset['armature'])
    rig = rigs[0]
    if set(asset['bones'])-set(rig.data.bones.keys()): raise ValueError('Required bones missing')
    root = bpy.data.objects.new('CharacterRoot',None)
    bpy.context.collection.objects.link(root)
    for obj in objects:
        if obj.parent is None:
            obj.parent = root
    for obj in objects:
        obj.animation_data_clear()
    return rig, root


def sequence(plan,asset):
    rig, root = load(asset)
    rig.animation_data_create()
    track = rig.animation_data.nla_tracks.new()
    track.name = 'CharacterSequence'
    position = (0,0,0)
    previous_end = 1
    for item in plan['character']['actions']:
        action = bpy.data.actions.get(asset['actions'][item['name']])
        if not action: raise ValueError('Missing registered action: '+item['name'])
        slots = [s for s in action.slots if s.target_id_type == 'OBJECT']
        if len(slots) != 1: raise ValueError('Actions must have one OBJECT slot; normalize asset before registration')
        channels = list(curves(action,slots[0]))
        if not channels or any(not c.data_path.startswith('pose.bones[') for c in channels):
            raise ValueError('Actions must contain local pose channels only')
        for c in channels:
            rig.path_resolve(c.data_path)
        start,end = item['startFrame'],item['endFrame']
        strip = track.strips.new(item['name'],start,action)
        strip.action_slot = slots[0]
        strip.action_frame_start,strip.action_frame_end = action.frame_range
        length = strip.action_frame_end-strip.action_frame_start
        if length <= 0: raise ValueError('Action has no duration')
        strip.scale = (end-start)/length
        strip.frame_end = end
        strip.extrapolation = 'NOTHING'
        strip.blend_type = 'REPLACE'
        strip.blend_in = strip.blend_out = min(4,(end-start)/3)
        # Fade to rest inside each range; no overlapping strips or held poses.
        if 'startPosition' in item and tuple(item['startPosition']) != tuple(position) and start != 1:
            raise ValueError('Root movement must be continuous between actions')
        root.location = position
        root.keyframe_insert('location',frame=previous_end)
        position = item.get('startPosition',position)
        root.location = position
        root.keyframe_insert('location',frame=start)
        position = item.get('endPosition',position)
        root.location = position
        root.keyframe_insert('location',frame=end)
        previous_end = end
    for c in curves(root.animation_data.action,root.animation_data.action_slot):
        for key in c.keyframe_points: key.interpolation = 'LINEAR'
    return rig

if __name__ == '__main__':
    import sys
    generate(sys.argv[sys.argv.index('--')+1])
