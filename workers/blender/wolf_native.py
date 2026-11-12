"""Narrow native wolf adapter. Never enables auto-execution or modifies source Actions."""
import bpy
import json
import sys
import math
import hashlib
from pathlib import Path
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0,str(Path(__file__).resolve().parent))
from inspect_character import import_file

SEGMENTS=[('idle',1,72),('walk',73,168),('idle',169,240)]

def points(body,frame):
    bpy.context.scene.frame_set(frame)
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    result=[evaluated.matrix_world@v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    if not result or any(not math.isfinite(n) for p in result for n in p): raise ValueError('Invalid evaluated Body geometry')
    return result

def bounds(pts):
    return [min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]

def mesh_delta(a,b):
    if len(a)!=len(b): raise ValueError('Evaluated mesh topology changed')
    landmarks=range(0,len(a),max(1,len(a)//256))
    shape_change=max(abs((a[i]-a[(i+len(a)//3)%len(a)]).length-(b[i]-b[(i+len(b)//3)%len(b)]).length) for i in landmarks)
    return {'max':max((x-y).length for x,y in zip(a,b)),'rms':math.sqrt(sum((x-y).length_squared for x,y in zip(a,b))/len(a)),'maxPairDistanceChange':shape_change}

def blocked_drivers(objects):
    drivers=[]
    for obj in objects:
        if obj.animation_data:
            for curve in obj.animation_data.drivers:
                drivers.append({'owner':obj.name,'path':curve.data_path,'type':curve.driver.type,'expression':curve.driver.expression,'valid':curve.driver.is_valid,'simpleExpression':curve.driver.is_simple_expression})
    if bpy.app.autoexec_fail or any(not d['valid'] or (d['type']=='SCRIPTED' and not d['simpleExpression']) for d in drivers):
        raise ValueError('Driver evaluation blocked or invalid with auto-run disabled. Ask the asset author for baked native clips or a script-free rig. '+bpy.app.autoexec_fail_message)
    return drivers

def build(plan,asset,job):
    report={'status':'checking','source':asset['absolutePath'],'sourceSha256':hashlib.sha256(Path(asset['absolutePath']).read_bytes()).hexdigest(),'license':asset['license'],'reviewOnly':True,'productionPublishingAllowed':False,'retargetingImplemented':False,'autoRunEnabled':False,'segments':SEGMENTS}
    output=job/'animation-report.json'
    try:
        if bpy.context.preferences.filepaths.use_scripts_auto_execute: raise ValueError('Auto-run must be disabled')
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        objects=import_file(Path(asset['absolutePath']))
        rig=bpy.data.objects.get('Armature');body=bpy.data.objects.get('Body')
        if not rig or rig.type!='ARMATURE' or not body or body.type!='MESH': raise ValueError('Expected Armature and Body missing')
        if set(asset['bones'])-set(rig.data.bones.keys()): raise ValueError('Required native wolf bones missing')
        if not any(m.type=='ARMATURE' and m.object==rig for m in body.modifiers): raise ValueError('Body is not bound to Armature')
        report['nativeBoneCount']=len(rig.data.bones)
        for obj in list(objects):
            if obj.type in ('MESH','CURVE') and obj!=body: obj.hide_render=True
            if obj.type in ('LIGHT','CAMERA'):
                objects.remove(obj);bpy.data.objects.remove(obj,do_unlink=True)
        report['materials']=[m.name for m in body.data.materials if m]
        report['textures']=[]
        for material in body.data.materials:
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    if node.type=='TEX_IMAGE' and node.image:
                        image=node.image;filename=Path(asset['absolutePath']).parent/image.filepath[2:] if image.filepath.startswith('//') else Path(image.filepath)
                        report['textures'].append({'name':image.name,'packed':bool(image.packed_file),'path':str(filename)})
                        if not image.packed_file and (not image.filepath or not filename.is_file()): raise ValueError('Missing texture: '+image.name+'; supply or pack the licensed texture before rendering')
        rig.animation_data_create()
        for track in rig.animation_data.nla_tracks: track.mute=True
        actions={}
        report['actions']=[]
        for semantic,name in asset['actions'].items():
            action=bpy.data.actions.get(name)
            if not action: raise ValueError('Native Action missing: '+name)
            slots=[s for s in action.slots if s.target_id_type=='OBJECT']
            if len(slots)!=1: raise ValueError('Native Action slot is ambiguous: '+name)
            bag=action_get_channelbag_for_slot(action,slots[0])
            if not bag or not bag.fcurves: raise ValueError('Native Action has no channels')
            for c in bag.fcurves:
                if not c.data_path.startswith('pose.bones['): raise ValueError('Unexpected native object/root channel: '+c.data_path)
                rig.path_resolve(c.data_path)
            rig.animation_data.action=action;rig.animation_data.action_slot=slots[0]
            first=points(body,1);second=points(body,15)
            delta=mesh_delta(first,second)
            if delta['rms']<.0001: raise ValueError('Native '+semantic+' does not deform evaluated Body; supply baked clips with script-free drivers')
            actions[semantic]=(action,slots[0])
            report['actions'].append({'semantic':semantic,'nativeName':name,'range':list(action.frame_range),'slot':slots[0].identifier,'channelCount':len(bag.fcurves),'channelScope':'native pose bone transforms and control properties','evaluatedMotion':delta})
        # Determine forward from the evaluated head/nose controls instead of assuming file axes.
        rig.animation_data.action=actions['idle'][0];rig.animation_data.action_slot=actions['idle'][1]
        bpy.context.scene.frame_set(1)
        evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        nose=next((evaluated.pose.bones.get(n) for n in ('FK_Noise','Nose','Noise') if evaluated.pose.bones.get(n)),None)
        if not nose: raise ValueError('No known nose control; facing must be verified with an asset-specific adapter')
        forward=(evaluated.matrix_world@nose.matrix.translation)-(evaluated.matrix_world@evaluated.pose.bones['Head'].matrix.translation)
        forward.z=0
        if forward.length<.01: raise ValueError('Head/nose direction is ambiguous')
        forward.normalize();report['facing']={'method':'evaluated Head to '+nose.name,'worldForward':list(forward),'visualReviewRequired':True}
        rig.animation_data.action=None
        for i,(name,start,end) in enumerate(SEGMENTS):
            action,slot=actions[name]
            track=rig.animation_data.nla_tracks.new();track.name='WolfNative.%d.%s'%(i,name)
            fade=6 if i else 0
            strip=track.strips.new(name,start-fade,action);strip.action_slot=slot
            strip.action_frame_start,strip.action_frame_end=action.frame_range
            duration=strip.action_frame_end-strip.action_frame_start
            if duration<=0: raise ValueError('Cannot sequence a zero-length native Action')
            strip.repeat=(end-strip.frame_start)/duration
            strip.frame_end=end;strip.blend_type='REPLACE';strip.blend_in=fade;strip.extrapolation='HOLD_FORWARD'
        scene=bpy.context.scene;scene.frame_start=1;scene.frame_end=240;scene.render.fps=24
        # Preserve all native parents/constraints/drivers. Transform only their common asset root.
        parent=bpy.data.objects.new('WolfPlacement',None);scene.collection.objects.link(parent)
        for obj in objects:
            if obj.name in bpy.data.objects and obj.type not in ('CAMERA','LIGHT') and obj.parent is None:
                world=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=world
        all_bounds=[]
        for frame in range(1,241): all_bounds.append(bounds(points(body,frame)))
        low=[min(b[0][i] for b in all_bounds) for i in range(3)];high=[max(b[1][i] for b in all_bounds) for i in range(3)]
        height=high[2]-low[2]
        if not .1<height<100: raise ValueError('Invalid native evaluated character height')
        scale=2.8/height;parent.scale=(scale,)*3
        parent.location=(-(low[0]+high[0])/2*scale,-(low[1]+high[1])/2*scale,-low[2]*scale+.015)
        final_bounds=[]
        for frame in range(1,241):
            pts=points(body,frame);lo,hi=bounds(pts);final_bounds.append((lo,hi))
            if lo[2]<.014: raise ValueError('Floor penetration detected at '+str(frame))
        report['placement']={'scale':scale,'location':list(parent.location),'nativeBounds':[low,high],'floorClearanceMin':min(b[0][2] for b in final_bounds),'maxLowerBoundHeight':max(b[0][2] for b in final_bounds),'note':'Static placement uses the minimum evaluated vertex height across every frame; inspect foot contact visually'}
        report['drivers']=blocked_drivers([rig,body])
        scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=16
        scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100
        scene.world=bpy.data.worlds.new('WolfStudio');scene.world.use_nodes=True
        scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.16,.2,.27,1)
        scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45
        bpy.ops.mesh.primitive_plane_add(size=200)
        ground=bpy.context.object;ground.name='WolfFloor'
        material=bpy.data.materials.new('StudioFloor');material.use_nodes=True
        material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.17,.2,.24,1)
        material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;ground.data.materials.append(material)
        target=Vector((0,0,1.4));side=Vector((-forward.y,forward.x,0))
        bpy.ops.object.camera_add(location=target+forward*8+side*2+Vector((0,0,1)))
        camera=bpy.context.object;camera.name='WolfReviewCamera';camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=7;scene.camera=camera
        for offset,energy,size in [(forward*4+side*3+Vector((0,0,6)),1000,5),(forward*3-side*4+Vector((0,0,4)),650,4),(-forward*3+Vector((0,0,5)),1100,3)]:
            bpy.ops.object.light_add(type='AREA',location=offset);light=bpy.context.object;light.data.energy=energy;light.data.size=size;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
        for frame in range(1,241):
            for p in points(body,frame):
                uv=world_to_camera_view(scene,camera,p)
                if not (.03<uv.x<.97 and .03<uv.y<.97 and uv.z>0): raise ValueError('Character framing failed at '+str(frame))
        idle=points(body,36);walk=points(body,120)
        report['idleWalkDifference']=mesh_delta(idle,walk)
        if report['idleWalkDifference']['rms']<.01: raise ValueError('Idle and walk evaluated geometry are indistinguishable')
        report['checks']={'evaluatedBodyMotion':True,'all240FramesFramed':True,'all240FramesAboveFloor':True,'invalidDrivers':False,'autoexecFailure':bpy.app.autoexec_fail,'visualDeformationReviewRequired':True}
        report['status']='scene_verified_pending_render'
        frames=job/'frames';frames.mkdir(exist_ok=True)
        scene.render.image_settings.file_format='PNG';scene.render.filepath=str(frames/'frame_')
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(job/'scene.blend'))
        if report['sourceSha256']!=hashlib.sha256(Path(asset['absolutePath']).read_bytes()).hexdigest(): raise ValueError('Source asset changed unexpectedly')
    except Exception as error:
        report['status']='blocked';report['diagnostic']=str(error);report['recommendedFix']='Keep auto-run disabled; obtain baked native Actions/script-free drivers or repair the specific reported asset issue. No retargeting fallback is used.'
        output.write_text(json.dumps(report,indent=2));raise
    output.write_text(json.dumps(report,indent=2))

def review(job):
    report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene
    directory=job/'previews';directory.mkdir(exist_ok=True)
    rig=bpy.data.objects['Armature'];body=bpy.data.objects['Body']
    # Recheck saved-file evaluation under disabled auto-run before declaring video reviewable.
    motion=mesh_delta(points(body,36),points(body,120))
    if motion['rms']<.01 or motion['maxPairDistanceChange']<.001: raise ValueError('Saved scene lost native action deformation')
    report['driversAfterReopen']=blocked_drivers([rig,body])
    images=[]
    for name,start,end in SEGMENTS:
        for label,frame in [('start',start),('middle',(start+end)//2),('end',end)]:
            scene.frame_set(frame);filename=directory/('%03d-%s-%s.png'%(frame,name,label));scene.render.filepath=str(filename);bpy.ops.render.render(write_still=True);images.append(str(filename))
    report['previews']=images;report['savedSceneMotion']=motion;report['status']='verified_pending_human_visual_review';(job/'animation-report.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if args[0]=='review': review(Path(args[1]))
    else:
        planfile,folder=args;job=Path(folder)
        build(json.loads(Path(planfile).read_text()),json.loads((job/'asset.json').read_text()),job)
