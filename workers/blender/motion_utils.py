import math
from mathutils import Vector

def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)
def shortest(a,b): return a+(b-a+math.pi)%(2*math.pi)-math.pi
def heading_to(origin,target):
    d=Vector(target)-Vector(origin)
    if d.xy.length<1e-6: raise ValueError('Facing target equals current position')
    return math.atan2(d.x,-d.y)
def interpolate(a,b,t): return Vector(a).lerp(Vector(b),smooth(t))
def camera_preset(scene,bounds,preset):
    low,high=map(Vector,bounds);height=high.z-low.z
    center=(low+high)/2
    if preset=='medium': center.z=low.z+height*.68;height*=.68
    if preset=='close_up': center.z=low.z+height*.86;height*=.36
    camera=scene.camera;camera.location=Vector((0,-10,center.z+1.1))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=max((high.x-low.x)*1.2,height*scene.render.resolution_x/scene.render.resolution_y*1.22)
    return camera


def transition_camera(camera,location,rotation,ortho_scale,start,end):
    """Deterministic camera helper; demo deliberately uses a fixed camera."""
    original=camera.location.copy();q=camera.rotation_euler.to_quaternion();scale=camera.data.ortho_scale
    for frame in range(start,end+1):
        t=smooth((frame-start)/max(1,end-start))
        camera.location=original.lerp(Vector(location),t)
        camera.rotation_euler=q.slerp(rotation,t).to_euler()
        camera.data.ortho_scale=scale+(ortho_scale-scale)*t
        camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_euler',frame=frame);camera.data.keyframe_insert('ortho_scale',frame=frame)
