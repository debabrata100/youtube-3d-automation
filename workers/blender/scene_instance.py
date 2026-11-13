"""Isolated adapter entry point; names/bones stay inside the wolf adapter."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import wolf_native as native
import character_controller
mode,folder=sys.argv[sys.argv.index('--')+1:];job=Path(folder)
asset=json.loads((job/'asset.json').read_text())
if mode=='probe':
    native.build({},asset,job)
    body=bpy.data.objects['Body']
    radius=max(p.xy.length for frame in range(1,241) for p in native.points(body,frame))+.15
    (job/'footprint.json').write_text(json.dumps({'radiusMeters':radius,'method':'max evaluated radial Body extent across native idle/walk, plus 15 cm; final scene independently rechecks every pose','sourceSha256':json.loads((job/'animation-report.json').read_text())['sourceSha256']}))
else:
    character_controller.build(json.loads((job/'plan.json').read_text()),asset,job,instance=True)
