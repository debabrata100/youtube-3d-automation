import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { SceneSchema } from './schemas/scene.js';
import { createWorkflow } from './graph/workflow.js';
import { ROOT } from './utils/paths.js';
const args=process.argv.slice(2);
if (!args[0]) throw new Error('Usage: npm run render:plan -- plan.json [--preview]');
const input:unknown=JSON.parse(await readFile(path.resolve(args[0]),'utf8'));
let plan=SceneSchema.parse(input);
if (args.includes('--preview')) {
  if (!('renderMode' in plan)) throw new Error('Preview mode requires a mascot plan');
  plan=SceneSchema.parse({...plan,renderMode:'preview',resolution:{width:640,height:360}});
}
const jobId='mascot-review-'+randomUUID();const jobDir=path.join(ROOT,'jobs',jobId);
const result=await createWorkflow(async()=>plan).invoke({prompt:'Saved deterministic plan',jobId,jobDir,plan:null,asset:null,videoPath:null});
console.log('Review job:',jobDir,'Video:',result.videoPath);
