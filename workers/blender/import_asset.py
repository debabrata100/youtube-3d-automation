"""Validate and normalize a registered, trusted asset into an isolated job."""
import bpy
import json
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character import load, curves

def inspect_asset(asset):
    rig, root = load(asset)
    objects = list(root.children_recursive)
    meshes = [o for o in objects if o.type == 'MESH']
    if not meshes: raise ValueError('Imported asset has no meshes')
    expected = set(asset.get('meshes', []))
    missing = expected - {o.name for o in meshes}
    if missing: raise ValueError('Missing registered meshes: '+str(sorted(missing)))
    for obj in objects:
        if any(not math.isfinite(v) or v <= 0 for v in obj.scale):
            raise ValueError('Invalid scale on '+obj.name)
    for name, identifier in asset['actions'].items():
        action = bpy.data.actions.get(identifier)
        slots = [s for s in action.slots if s.target_id_type == 'OBJECT'] if action else []
        if len(slots) != 1: raise ValueError('Missing action or incompatible slots: '+name)
        channels = list(curves(action,slots[0]))
        if not channels: raise ValueError('Empty action: '+name)
        for channel in channels:
            if not channel.data_path.startswith('pose.bones['): raise ValueError('Action must use local bone channels: '+name)
            try: rig.path_resolve(channel.data_path)
            except Exception as exc: raise ValueError('Action incompatible with rig: '+name) from exc
    for name, bone in asset.get('facialControls',{}).items():
        if bone not in rig.pose.bones: raise ValueError('Unsupported facial control: '+name+' -> '+bone)
    normalization = asset.get('normalization', {'scale':1,'rotationDegrees':[0,0,0]})
    scale = normalization['scale']
    if not math.isfinite(scale) or scale <= 0: raise ValueError('Invalid normalization scale')
    root.scale = (scale,)*3
    root.rotation_euler = tuple(math.radians(v) for v in normalization['rotationDegrees'])
    return {'valid':True,'assetId':asset['id'],'version':asset['version'],
            'rig':rig.name,'rigDefinition':asset.get('rigDefinition','custom'),
            'meshes':[o.name for o in meshes],'actions':asset['actions'],
            'facialControls':asset.get('facialControls',{}),'license':asset['license'],
            'source':asset.get('source',asset['license']['source']), 'normalization':normalization}

if __name__ == '__main__':
    source, output = sys.argv[sys.argv.index('--')+1:]
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    asset = json.loads(Path(source).read_text())
    try:
        report = inspect_asset(asset)
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'normalized.blend'))
    except Exception as error:
        (output/'validation.json').write_text(json.dumps({'valid':False,'error':str(error)},indent=2))
        raise
    (output/'validation.json').write_text(json.dumps(report,indent=2))
