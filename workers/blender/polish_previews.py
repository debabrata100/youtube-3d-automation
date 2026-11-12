import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
job=Path(sys.argv[sys.argv.index('--')+1]);scene=bpy.context.scene;folder=job/'previews';folder.mkdir(exist_ok=True)
frames=[(1,'Initial idle'),(60,'First turn'),(112,'Mid-stride'),(166,'Near destination'),(192,'Stopping'),(216,'Facing camera'),(258,'Wave preparation'),(269,'Wave peak'),(287,'Wrist follow-through'),(306,'Wave lowering'),(313,'Wave complete'),(348,'Final idle')]
for prop in ('use_stamp_date','use_stamp_time','use_stamp_render_time','use_stamp_frame','use_stamp_frame_range','use_stamp_memory','use_stamp_hostname','use_stamp_camera','use_stamp_lens','use_stamp_scene','use_stamp_marker','use_stamp_filename','use_stamp_sequencer_strip'):
    if hasattr(scene.render,prop):setattr(scene.render,prop,False)
scene.render.use_stamp=True;scene.render.use_stamp_note=True;scene.render.use_stamp_labels=False;scene.render.stamp_font_size=36
for index,(frame,label) in enumerate(frames):
    scene.frame_set(frame);scene.render.stamp_note_text=f'{label} | frame {frame}';scene.render.filepath=str(folder/('sheet-%02d.png'%index));bpy.ops.render.render(write_still=True)
report=json.loads((job/'animation-report.json').read_text());report['contactSheetFrames']=[{'frame':f,'label':label,'path':str(folder/('sheet-%02d.png'%i))} for i,(f,label) in enumerate(frames)];report['contactSheet']=str(job/'contact-sheet.png');(job/'animation-report.json').write_text(json.dumps(report,indent=2))

from animation_polish import render_foot_diagnostics
render_foot_diagnostics(job)
