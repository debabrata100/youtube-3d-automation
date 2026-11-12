import bpy
import sys
from pathlib import Path
from mathutils import Vector
job=Path(sys.argv[sys.argv.index('--')+1]);output=job/'review';output.mkdir(exist_ok=True)
scene=bpy.context.scene
scene.eevee.taa_render_samples=16
camera=scene.camera
for name,frame,quarter in [('front',1,False),('three-quarter',1,True),('neutral',1,False),('smile',180,False),('blink',143,False),('walking',16,False),('waving',180,False),('beginning',1,False),('middle',120,False),('end',240,False)]:
    scene.frame_set(frame)
    root=bpy.data.objects['CharacterRoot']
    target=Vector((root.location.x,0,1.5))
    camera.location=target+Vector((5,-9,3) if quarter else (0,-10,1.3))
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    # ortho_scale is horizontal span; allow full-body height in a 16:9 image.
    camera.data.ortho_scale=6.5
    scene.render.filepath=str(output/(name+'.png'))
    bpy.ops.render.render(write_still=True)
print('VISUAL_REVIEW_ARTIFACTS',output)
