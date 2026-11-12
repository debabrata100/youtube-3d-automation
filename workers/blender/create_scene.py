import bpy
import math
import sys
from pathlib import Path
from mathutils import Vector

# ----------------------------------
# 1. Resolve project directory
# ----------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOB_DIR = PROJECT_ROOT / "jobs" / "demo-001"
FRAMES_DIR = JOB_DIR / "frames"
OUTPUT_DIR = JOB_DIR / "output"

FRAMES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------
# 2. Reset Blender scene
# ----------------------------------

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene

# Detect compatible EEVEE render engine
available_engines = scene.render.bl_rna.properties["engine"].enum_items.keys()

if "BLENDER_EEVEE" in available_engines:
    scene.render.engine = "BLENDER_EEVEE"
elif "BLENDER_EEVEE_NEXT" in available_engines:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
else:
    raise RuntimeError("No compatible EEVEE engine found")

scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100

scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 120

# ----------------------------------
# 3. Material helper
# ----------------------------------


def create_material(name, color, roughness=0.4):
    material = bpy.data.materials.new(name)
    material.use_nodes = True

    bsdf = material.node_tree.nodes.get("Principled BSDF")

    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness

    return material


red_material = create_material("Glossy Red", (0.8, 0.02, 0.02, 1), 0.2)

green_material = create_material("Green Floor", (0.12, 0.45, 0.12, 1), 0.8)

# ----------------------------------
# 4. Create ground
# ----------------------------------

bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))

ground = bpy.context.object
ground.name = "Ground"
ground.data.materials.append(green_material)

# ----------------------------------
# 5. Create red ball
# ----------------------------------

bpy.ops.mesh.primitive_uv_sphere_add(
    segments=64, ring_count=32, radius=1, location=(-3, 0, 1)
)

ball = bpy.context.object
ball.name = "AnimatedBall"
ball.data.materials.append(red_material)

bpy.ops.object.shade_smooth()

# ----------------------------------
# 6. Animate ball
# ----------------------------------

# Initial position
ball.location = (-3, 0, 1)
ball.keyframe_insert(data_path="location", frame=1)

# Middle position
ball.location = (0, 0, 1)
ball.keyframe_insert(data_path="location", frame=60)

# Final position
ball.location = (3, 0, 1)
ball.keyframe_insert(data_path="location", frame=120)

# Rotate while moving
ball.rotation_euler = (0, 0, 0)
ball.keyframe_insert(data_path="rotation_euler", frame=1)

ball.rotation_euler = (0, 6, 0)
ball.keyframe_insert(data_path="rotation_euler", frame=120)

# Use linear movement
if ball.animation_data and ball.animation_data.action:
    action = ball.animation_data.action

    # Compatible with newer Blender action slots
    for fc in getattr(action, "fcurves", []):
        for point in fc.keyframe_points:
            point.interpolation = "LINEAR"

# ----------------------------------
# 7. Create lighting
# ----------------------------------

bpy.ops.object.light_add(type="AREA", location=(-3, -4, 8))

light = bpy.context.object
light.name = "MainLight"
light.data.energy = 1500
light.data.shape = "DISK"
light.data.size = 6

# ----------------------------------
# 8. Create camera
# ----------------------------------

bpy.ops.object.camera_add(location=(0, -12, 5))

camera = bpy.context.object
camera.name = "MainCamera"

target = Vector((0, 0, 1))
direction = target - camera.location

camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

camera.data.type = "ORTHO"
camera.data.ortho_scale = 11

scene.camera = camera

# ----------------------------------
# 9. World background
# ----------------------------------

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True

background = world.node_tree.nodes.get("Background")
background.inputs["Color"].default_value = (0.55, 0.7, 0.9, 1)
background.inputs["Strength"].default_value = 0.8

# ----------------------------------
# 10. Save Blender project
# ----------------------------------

scene.frame_set(1)

blend_file = JOB_DIR / "scene.blend"

bpy.ops.wm.save_as_mainfile(filepath=str(blend_file))

# ----------------------------------
# 11. Configure frame rendering
# ----------------------------------

scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(FRAMES_DIR / "frame_")

print("Scene created successfully")
print(f"Blend file: {blend_file}")
print(f"Frames directory: {FRAMES_DIR}")

# ----------------------------------
# 12. Render animation
# ----------------------------------

if "--render" in sys.argv:
    print("Starting animation render...")
    bpy.ops.render.render(animation=True)
    print("Rendering completed!")
