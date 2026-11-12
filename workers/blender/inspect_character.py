"""Read-only character inspection. Mapping checks are not animation retargeting."""
import bpy
import json
import sys
import math
import hashlib
import re
from pathlib import Path
from mathutils import Vector
from bpy_extras.anim_utils import action_get_channelbag_for_slot

PARENTS={'root':None,'torso':'root','head':'torso','arm.L':'torso','arm.R':'torso','leg.L':'root','leg.R':'root'}
FACIAL=['face.mouth','face.brow.L','face.brow.R','face.eye.L','face.eye.R','face.pupil.L','face.pupil.R']

def import_file(source):
    """Import only data; preserve Actions, NLA, drivers and shape keys for inventory."""
    before=set(bpy.data.objects)
    suffix=Path(source).suffix.lower()
    if suffix=='.blend':
        with bpy.data.libraries.load(str(source),link=False) as (origin,result):
            result.objects=origin.objects
            result.actions=origin.actions
        for obj in result.objects:
            if obj: bpy.context.collection.objects.link(obj)
    elif suffix=='.glb': bpy.ops.import_scene.gltf(filepath=str(source))
    elif suffix=='.fbx': bpy.ops.import_scene.fbx(filepath=str(source),use_anim=True)
    else: raise ValueError('Unsupported character format')
    return sorted(set(bpy.data.objects)-before,key=lambda o:o.name)

def vector(v): return [round(float(n),6) for n in v]
def axis(name):
    v=Vector((0,0,0));v['XYZ'.index(name[-1])]=-1 if name.startswith('-') else 1
    return v

def inspect(source, config):
    objects=import_file(source)
    meshes=[o for o in objects if o.type=='MESH']
    rigs=[o for o in objects if o.type=='ARMATURE']
    issues=[]
    def issue(code,detail,fix,severity='error'):
        issues.append({'code':code,'severity':severity,'detail':detail,'recommendedFix':fix})
    digest=hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    report={'schemaVersion':'1.0','source':{'path':str(source),'format':source.suffix.lower(),'sha256':digest.hexdigest()},
            'character':config.get('character',{'id':source.stem,'name':source.stem,'version':'unregistered','source':'User-supplied local file','license':{'name':'unknown','commercialUse':None,'attribution':''}}),
            'targetRig':config['targetRig'],'blenderVersion':bpy.app.version_string,'meshes':[],'armatures':[],
            'materials':[],'animations':[],'facialControls':{'shapeKeys':[],'boneCandidates':[],'customProperties':[],'semanticCompatibility':'unverified'},
            'issues':issues,'retargeting':{'implemented':False,'tested':False,'mappingApplied':False},'registrationModified':False}
    license=report['character']['license']
    if license['commercialUse'] is not True or license['name'] in ('','unknown'):
        issue('LICENSE_REVIEW','Commercial use is not established by the supplied metadata','Obtain and review the actual license; inspection grants no usage rights','warning')
    if not meshes: issue('NO_MESHES','No meshes imported','Supply a character mesh with skin weights')
    if not rigs: issue('NO_ARMATURE','No armature imported','Rig the mesh before using body animations')
    selected=[r for r in rigs if r.name==config.get('armature')] if config.get('armature') else rigs
    rig=selected[0] if len(selected)==1 else None
    if rigs and not rig: issue('ARMATURE_SELECTION','Requested armature missing or selection is ambiguous','Set armature to one exact name in the configuration')
    for obj in objects:
        if any(not math.isfinite(v) or v<=0 for v in obj.scale): issue('INVALID_SCALE',obj.name+' has nonpositive or nonfinite scale','Apply transforms in Blender, correct mirrored geometry and re-export')
        for key in obj.keys():
            if key!='_RNA_UI': report['facialControls']['customProperties'].append({'owner':obj.name,'property':key,'value':str(obj[key]),'semanticMeaning':'unverified'})
        if obj.constraints: issue('CONSTRAINTS',obj.name+' uses constraints','Bake and verify constraints for the pipeline','warning')
        if obj.animation_data and obj.animation_data.drivers: issue('DRIVERS',obj.name+' has drivers; execution is disabled','Bake driven controls; never enable untrusted scripts','warning')
    corners=[]
    for mesh in meshes:
        bindings=[m.object.name for m in mesh.modifiers if m.type=='ARMATURE' and m.object]
        corners.extend(mesh.matrix_world@Vector(corner) for corner in mesh.bound_box)
        report['meshes'].append({'name':mesh.name,'vertices':len(mesh.data.vertices),'polygons':len(mesh.data.polygons),
            'armatureModifiers':bindings,'parent':mesh.parent.name if mesh.parent else None,'parentType':mesh.parent_type,
            'vertexGroups':[g.name for g in mesh.vertex_groups],'materials':[m.name if m else None for m in mesh.data.materials],
            'scale':vector(mesh.scale),'rotationEuler':vector(mesh.rotation_euler)})
        if mesh.data.shape_keys:
            for key in mesh.data.shape_keys.key_blocks:
                report['facialControls']['shapeKeys'].append({'mesh':mesh.name,'name':key.name,'value':key.value,'min':key.slider_min,'max':key.slider_max,'relativeTo':key.relative_key.name if key.relative_key else None})
    for material in sorted({m for o in meshes for m in o.data.materials if m},key=lambda m:m.name):
        images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if material.use_nodes else []
        report['materials'].append({'name':material.name,'useNodes':material.use_nodes,'textures':[{'name':i.name,'path':i.filepath,'packed':bool(i.packed_file)} for i in images]})
        for image in images:
            if not image.packed_file: issue('EXTERNAL_TEXTURE',image.name+' is not packed','Pack or verify the texture path before rendering','warning')
    for armature in rigs:
        report['armatures'].append({'name':armature.name,'scale':vector(armature.scale),'matrixWorld':[vector(row) for row in armature.matrix_world],
            'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'deform':b.use_deform,'length':b.length,'head':vector(b.head_local),'tail':vector(b.tail_local),'matrixLocal':[vector(row) for row in b.matrix_local]} for b in armature.data.bones],
            'activeAction':armature.animation_data.action.name if armature.animation_data and armature.animation_data.action else None,
            'nlaTracks':[{'name':t.name,'strips':[{'name':s.name,'action':s.action.name if s.action else None,'start':s.frame_start,'end':s.frame_end} for s in t.strips]} for t in armature.animation_data.nla_tracks] if armature.animation_data else []})
        for bone in armature.pose.bones:
            if re.search('face|eye|mouth|brow|jaw|lip|blink',bone.name,re.I): report['facialControls']['boneCandidates'].append({'armature':armature.name,'bone':bone.name})
            for key in bone.keys():
                if key!='_RNA_UI': report['facialControls']['customProperties'].append({'owner':armature.name,'bone':bone.name,'property':key,'value':str(bone[key])})
    if rig and not any(rig.name in m['armatureModifiers'] or (m['parent']==rig.name and m['parentType']=='BONE') for m in report['meshes']):
        issue('UNBOUND_MESH','No mesh is bound to the selected rig','Add appropriate skin weights and armature modifiers')
    if corners:
        low=Vector(tuple(min(p[i] for p in corners) for i in range(3)));high=Vector(tuple(max(p[i] for p in corners) for i in range(3)))
        height=(high.z-low.z)*bpy.context.scene.unit_settings.scale_length
        report['scale']={'boundsMin':vector(low),'boundsMax':vector(high),'heightMeters':height,'measurement':'Imported mesh bounding boxes, not guaranteed evaluated rest pose','unitScale':bpy.context.scene.unit_settings.scale_length}
        if not config['heightMeters']['min']<=height<=config['heightMeters']['max']: issue('HEIGHT_OUT_OF_RANGE','Measured height is '+str(height)+' meters','Normalize units/scale and reinspect; customize heightMeters only intentionally')
    orientation=config.get('orientation')
    report['orientation']={'declared':orientation,'verified':False,'expectedWorldUp':'Z','expectedWorldForward':'-Y','limitation':'Geometric front cannot be inferred reliably; axes require an explicit user declaration'}
    if rig and orientation:
        matrix=rig.matrix_world.to_3x3()
        up=(matrix@axis(orientation['up'])).normalized();forward=(matrix@axis(orientation['forward'])).normalized()
        report['orientation'].update({'worldUp':vector(up),'worldForward':vector(forward),'verified':up.dot(axis('Z'))>.98 and forward.dot(axis('-Y'))>.98})
        if not report['orientation']['verified']: issue('ORIENTATION_MISMATCH','Declared axes do not align with pipeline world axes','Normalize orientation to Z up and -Y forward')
    else: issue('ORIENTATION_UNVERIFIED','Character facing direction is unverified','Declare up and forward axes after confirming the model convention','warning')
    required=list(PARENTS)+(FACIAL if config['targetRig']=='mascot-v2' else [])
    mappings=config['boneMap'];resolved={};mapping_report=[]
    for semantic in required:
        actual=mappings.get(semantic)
        exists=bool(rig and actual in rig.data.bones) if actual else False
        mapping_report.append({'requiredBone':semantic,'mappedBone':actual,'exists':exists,'suggestions':[semantic] if rig and semantic in rig.data.bones else []})
        if not actual: issue('MAPPING_REQUIRED','No explicit mapping for '+semantic,'Map the semantic bone to an inspected source bone; suggestions are not applied','warning')
        elif not exists: issue('MISSING_MAPPED_BONE',semantic+' -> '+actual+' does not exist','Correct the mapping or rig the missing bone')
        else: resolved[semantic]=actual
    if len(set(mappings.values()))!=len(mappings): issue('DUPLICATE_MAPPING','Multiple semantic bones map to one source bone','Use distinct source bones or a different rig adapter')
    for name in set(mappings)-set(required): issue('UNKNOWN_MAPPING',name+' is not part of the target rig','Remove unsupported semantic mappings')
    if rig:
        for child,parent in {**PARENTS,**({n:'head' for n in FACIAL} if config['targetRig']=='mascot-v2' else {})}.items():
            if parent and child in resolved and parent in resolved:
                ancestors={b.name for b in rig.data.bones[resolved[child]].parent_recursive}
                if resolved[parent] not in ancestors: issue('HIERARCHY_MISMATCH',child+' is not a descendant of '+parent,'Correct the rig or plan a tested retargeting adapter')
    if rig and 'root' in resolved and 'head' in resolved:
        upright=rig.matrix_world.to_3x3()@(rig.data.bones[resolved['head']].head_local-rig.data.bones[resolved['root']].head_local)
        if upright.length<.001 or upright.normalized().z<.8: issue('SKELETON_UPRIGHT','Mapped root-to-head direction is not upright','Check mapping and normalize the skeleton orientation')
    report['requiredBoneMappings']=mapping_report
    for action in bpy.data.actions:
        channels=[];slots=[]
        for slot in action.slots:
            bags=[strip.channelbag(slot) for layer in action.layers for strip in layer.strips if hasattr(strip,'channelbag')]
            slot_channels=[]
            for curve in [c for bag in bags if bag for c in bag.fcurves]:
                valid=False
                if rig and slot.target_id_type=='OBJECT':
                    try:
                        value=rig.path_resolve(curve.data_path)
                        valid=curve.data_path.startswith('pose.bones[') and 0<=curve.array_index<len(value)
                    except (ValueError,AttributeError,TypeError): pass
                slot_channels.append({'path':curve.data_path,'index':curve.array_index,'keys':len(curve.keyframe_points),'resolvesOnSelectedRig':valid})
            channels.extend(slot_channels)
            slots.append({'identifier':slot.identifier,'targetType':slot.target_id_type,'channels':slot_channels})
        object_slots=[s for s in slots if s['targetType']=='OBJECT']
        compatible=bool(rig and len(action.layers)==1 and len(action.layers[0].strips)==1 and len(object_slots)==1 and channels and all(c['resolvesOnSelectedRig'] and c['keys'] for c in channels) and action.frame_range[1]>action.frame_range[0])
        report['animations'].append({'name':action.name,'frameRange':vector(action.frame_range),'slots':slots,'pipelineLocalBoneChannelsCompatible':compatible,'visualMotionVerified':False})
    by_name={a['name']:a for a in report['animations']}
    report['requestedActions']=[]
    for semantic,name in config['actionMap'].items():
        available=by_name.get(name)
        compatible=bool(available and available['pipelineLocalBoneChannelsCompatible'])
        report['requestedActions'].append({'action':semantic,'sourceAction':name,'compatible':compatible})
        if not compatible: issue('INCOMPATIBLE_ACTION',semantic+' -> '+name+' missing or contains unsupported/mismatched channels','Supply a compatible in-place Action or implement and test retargeting')
    report['animationCompatibility']={'existingLocalActionChannelChecksPassed':bool(config['actionMap']) and all(a['compatible'] for a in report['requestedActions']),
        'projectLibraryTransferVerified':False,'restPoseAndBoneAxesTransferVerified':False,'note':'A bone map and matching paths do not retarget rotations, rest poses, axes, proportions, or skinning. No animation has been transferred.'}
    if config['targetRig']=='mascot-v2':
        exact=bool(rig and all(n in rig.data.bones and mappings.get(n)==n for n in FACIAL))
        report['facialControls']['semanticCompatibility']='exact_bone_names_only_unverified_motion' if exact else 'adapter_required'
        if not exact: issue('FACIAL_ADAPTER_REQUIRED','Current facial worker requires exact mascot-v2 bones','Implement and test a facial adapter; shape keys are inventory only','warning')
    if not config['actionMap']: issue('ACTIONS_UNVERIFIED','No source Actions were selected for pipeline checks','Set actionMap to existing Action names after inspecting the inventory','warning')
    issue('RETARGETING_NOT_IMPLEMENTED','Project library transfer is not implemented in Phase 1','Use source-specific Actions or implement and test retargeting in a later phase','info')
    if any(i['severity']=='error' for i in issues): report['status']='incompatible'
    elif any(not b['mappedBone'] for b in mapping_report): report['status']='needs_mapping'
    elif any(i['severity']=='warning' for i in issues): report['status']='needs_review'
    else: report['status']='structural_checks_passed'
    report['animationReady']=False
    report['recommendedFixes']=list(dict.fromkeys(i['recommendedFix'] for i in issues))
    return report

def main():
    request_path,output=sys.argv[sys.argv.index('--')+1:]
    request=json.loads(Path(request_path).read_text());destination=Path(output)/'compatibility.json'
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    try:
        report=inspect(Path(request['source']),request['config'])
        encoded=json.dumps(report,indent=2,allow_nan=False)
    except Exception as error:
        destination.write_text(json.dumps({'schemaVersion':'1.0','status':'import_failed','source':{'path':request['source']},'character':request['config'].get('character'),'targetRig':request['config']['targetRig'],'error':str(error),'meshes':[],'armatures':[],'animations':[],'facialControls':{},'requiredBoneMappings':[],'issues':[{'code':'IMPORT_FAILED','severity':'error','detail':str(error),'recommendedFix':'Verify the file is valid and supported by the installed Blender importer'}],'recommendedFixes':['Verify source format and Blender importer availability; re-export a valid file'],'animationReady':False,'retargeting':{'implemented':False,'tested':False,'mappingApplied':False}},indent=2))
        raise
    destination.write_text(encoded)
    print('CHARACTER_INSPECTION_REPORT',destination,report['status'])
if __name__=='__main__': main()
