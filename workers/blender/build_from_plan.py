import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character import sequence


def get_args():
    if "--" not in sys.argv:
        raise RuntimeError("Missing script arguments")

    args = sys.argv[sys.argv.index("--") + 1 :]

    if len(args) != 2:
        raise RuntimeError("Expected: plan.json job_directory")

    return Path(args[0]).resolve(), Path(args[1]).resolve()


COLORS = {
    "red": (0.8, 0.02, 0.02, 1),
    "blue": (0.02, 0.15, 0.9, 1),
    "green": (0.08, 0.5, 0.12, 1),
    "yellow": (0.9, 0.7, 0.02, 1),
    "purple": (0.5, 0.1, 0.7, 1),
    "gray": (0.4, 0.4, 0.4, 1),
}


def make_material(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True

    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = COLORS[color]

    return material


def build_scene(plan, job_dir):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene

    # Blender 5.3 compatibility
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 16
    scene.render.resolution_x = plan["resolution"]["width"]
    scene.render.resolution_y = plan["resolution"]["height"]
    scene.render.resolution_percentage = 100
    scene.render.fps = plan["fps"]
    scene.frame_start = 1
    scene.frame_end = plan["durationSeconds"] * plan["fps"]

    # Ground
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(make_material("FloorMaterial", (plan["environment"] if "character" in plan else plan["floor"])["color"]))

    if 'character' in plan:
        with open(job_dir / 'asset.json', encoding='utf-8') as f:
            sequence(plan, json.load(f))
    else:
        # Ball
        radius = plan["ball"]["radius"]
    
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=64,
            ring_count=32,
            radius=radius,
            location=(plan["ball"]["startX"], 0, radius),
        )
    
        ball = bpy.context.object
        ball.name = "AnimatedBall"
        ball.data.materials.append(make_material("BallMaterial", plan["ball"]["color"]))
    
        bpy.ops.object.shade_smooth()
    
        # Animate
        ball.location.x = plan["ball"]["startX"]
        ball.keyframe_insert(data_path="location", frame=1)
    
        ball.location.x = plan["ball"]["endX"]
        ball.keyframe_insert(data_path="location", frame=scene.frame_end)
    
    # Light
    bpy.ops.object.light_add(type="AREA", location=(-3, -4, 8))
    light = bpy.context.object
    light.data.energy = 1500
    light.data.shape = "DISK"
    light.data.size = 6

    # Camera
    bpy.ops.object.camera_add(location=(0, -12, 5))
    camera = bpy.context.object

    target = Vector((0, 0, 1))
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 11
    scene.camera = camera

    # World lighting
    world = bpy.data.worlds.new("SceneWorld")
    world.use_nodes = True
    scene.world = world
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.55, 0.7, 0.9, 1)
    background.inputs["Strength"].default_value = 0.8

    # IMPORTANT: Configure output BEFORE saving
    frames_dir = job_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(frames_dir / "frame_")

    scene.frame_set(1)

    bpy.ops.wm.save_as_mainfile(filepath=str(job_dir / "scene.blend"))

    print("Scene built successfully")


if __name__ == "__main__":
    plan_path, job_dir = get_args()

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    job_dir.mkdir(parents=True, exist_ok=True)
    build_scene(plan, job_dir)
