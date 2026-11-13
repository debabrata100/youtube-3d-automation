import bpy,sys,json,runpy,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
job=Path(sys.argv[sys.argv.index('--')+1])
runpy.run_path(str(Path(__file__).with_name('polish_previews.py')),run_name='__main__')
report=json.loads((job/'animation-report.json').read_text());scene=bpy.context.scene;paths={}
selections={'foot-contact':[80,110,118,126,166,188,196,204,216],'wave':[244,258,report['wave']['peakFrame'],276,285,306,313],'camera':[72,73,132,192,193,194,240,241]}
for kind,frames in selections.items():
    folder=job/'previews'/kind;folder.mkdir(exist_ok=True);paths[kind]=[]
    for frame in sorted(set(frames)):
        destination=folder/('%03d.png'%frame)
        source=next((p for p in (job/'previews').glob('%03d-*.png'%frame) if p.name[4:8]!='stop'),None)
        if source:shutil.copyfile(source,destination)
        else:
            scene.frame_set(frame);scene.render.stamp_note_text=f'{kind} | frame {frame}';scene.render.filepath=str(destination);bpy.ops.render.render(write_still=True)
        paths[kind].append(str(destination))
# Separate full-body diagnostics remain available even when the scheduled medium shot crops legs.
for p in (job/'previews').glob('foot-stop-*.png'):shutil.copyfile(p,job/'previews/foot-contact'/p.name)
baseline_file=job/'performance-baseline.json'
if baseline_file.exists():
    baseline=json.loads(baseline_file.read_text())
    if baseline.get('available'):
        paths['comparisonBeforeFeet']=[]
        for before in (Path(baseline['job'])/'previews').glob('foot-stop-*.png'):
            target=job/'previews/foot-contact'/('before-phase31-'+before.name);shutil.copyfile(before,target);paths['comparisonBeforeFeet'].append(str(target))
        before=Path(baseline['job'])/'previews/276-wave.png'
        if before.exists():
            target=job/'previews/wave/before-phase31-276.png';shutil.copyfile(before,target);paths['comparisonBeforeWave']=str(target)
report['performancePreviews']=paths;(job/'animation-report.json').write_text(json.dumps(report,indent=2))
