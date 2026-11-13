import {readFile,mkdir,realpath,writeFile} from 'node:fs/promises';
import {createHash,randomUUID} from 'node:crypto';
import path from 'node:path';
import {ROOT,BLENDER} from './utils/paths.js';
import {controllerScene} from './animation/characterController.js';
import {ControllerSchema} from './animation/animationSchema.js';
import {createWorkflow} from './graph/workflow.js';
import {resolveWolfAsset} from './assets/wolfAsset.js';
import {runCommand} from './utils/runCommand.js';
const controller=ControllerSchema.parse(JSON.parse(await readFile(path.join(ROOT,'assets/plans/wolf-performance.json'),'utf8')));
const plan=controllerScene(controller),jobId='wolf-performance-'+randomUUID(),jobDir=path.join(ROOT,'jobs',jobId);
await mkdir(jobDir,{recursive:true});console.log('Performance review job:',jobDir,'— review-only; licensing unverified');
const jobsRoot=await realpath(path.join(ROOT,'jobs'));const asset=await resolveWolfAsset();const hash=createHash('sha256').update(await readFile(asset.absolutePath)).digest('hex');
try{
 const baseline=await realpath(process.env.WOLF_PERFORMANCE_BASELINE ?? path.join(jobsRoot,'wolf-polish-14813eea-226b-4cdf-8e76-ed2bad140de4'));
 if(!baseline.startsWith(jobsRoot+path.sep))throw new Error('Baseline must be inside the approved jobs directory');
 const report=JSON.parse(await readFile(path.join(baseline,'animation-report.json'),'utf8'));
 if(report.frames!==360||report.sourceSha256!==hash||report.controller?.performance||report.wave?.action!=='Wolf.Controller.Wave.v2')throw new Error('Baseline must be a Phase 3.1 run with the identical source asset');
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(baseline,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/performance_baseline.py'),'--',jobDir],ROOT);
}catch(error){
 if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;
 await writeFile(path.join(jobDir,'performance-baseline.json'),JSON.stringify({available:false,reason:'Phase 3.1 baseline unavailable; no comparison values were fabricated'}));
 console.log('Phase 3.1 baseline unavailable; rendering without comparative metrics.');
}
// Preserve the existing Phase 3 comparison when its baseline exists; it is independent of Phase 3.1.
try{
 const legacy=path.join(jobsRoot,'wolf-motion-a81b0258-42d3-4856-9b7d-03af047ac992','scene.blend');await readFile(legacy);
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',legacy,'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/contact_baseline.py'),'--',jobDir],ROOT);
}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
await createWorkflow(async()=>plan,{wolfMotionReview:true}).invoke({prompt:'Deterministic Phase 3.2 performance',jobId,jobDir,plan:null,asset:null,videoPath:null});
await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(jobDir,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/character_controller.py'),'--','review',jobDir],ROOT);
await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(jobDir,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/performance_previews.py'),'--',jobDir],ROOT);
await runCommand('ffmpeg',['-v','error','-i',path.join(jobDir,'previews/sheet-%02d.png'),'-vf','scale=384:216,tile=4x3','-frames:v','1',path.join(jobDir,'contact-sheet.png')],ROOT);
console.log('Performance artifacts:',jobDir);
