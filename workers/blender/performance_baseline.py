import bpy,json,sys
from pathlib import Path
job=Path(sys.argv[sys.argv.index('--')+1]);baseline=Path(bpy.data.filepath).parent
sys.path.insert(0,str(Path(__file__).resolve().parent))
from animation_polish import capture_feet
samples=capture_feet(bpy.data.objects['Armature'],range(1,361));report=json.loads((baseline/'animation-report.json').read_text())
(job/'performance-baseline.json').write_text(json.dumps({'available':True,'job':str(baseline),'samples':[{n:list(v) for n,v in row.items()} for row in samples],'report':report},indent=2))
