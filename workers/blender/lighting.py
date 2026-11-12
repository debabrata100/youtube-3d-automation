import bpy
from mathutils import Vector

def configure(plan):
    preset=plan['lighting']
    for obj in list(bpy.data.objects):
        if obj.type=='LIGHT': bpy.data.objects.remove(obj,do_unlink=True)
    definitions={
        'soft_studio':[((-3,-5,6),800,5,(1,.88,.76)),((4,-3,4),500,4,(.75,.87,1)),((1,3,5),1000,3,(1,1,1))],
        'sunny_outdoor':[((-4,-3,7),1400,3,(1,.9,.68)),((4,-2,5),350,6,(.7,.85,1))],
        'neutral_preview':[((0,-4,6),900,6,(1,1,1))],
    }
    for i,(position,energy,size,color) in enumerate(definitions[preset]):
        bpy.ops.object.light_add(type='AREA',location=position)
        light=bpy.context.object;light.name='PresetLight.%d'%i
        light.data.energy=energy;light.data.size=size;light.data.color=color
        light.rotation_euler=(Vector((0,0,1.3))-light.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.35
    scene.view_settings.view_transform='AgX'
    scene.eevee.taa_render_samples=8 if plan['renderMode']=='preview' else 32
    scene.camera.location=(0,-12,4)
    scene.camera.rotation_euler=(Vector((0,0,1.45))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.ortho_scale=9.5
