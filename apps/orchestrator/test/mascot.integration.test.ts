import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {ROOT,BLENDER} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
import {SceneSchema} from '../src/schemas/scene.js';
import {createWorkflow} from '../src/graph/workflow.js';
test('10-second final mascot, expressions, import failures and visual review', {timeout:1200000},async()=>{
  const plan=SceneSchema.parse(JSON.parse(await readFile(path.join(ROOT,'assets/plans/mascot-v2.json'),'utf8')));
  const jobId='mascot-review-'+randomUUID(),jobDir=path.join(ROOT,'jobs',jobId);
  await createWorkflow(async()=>plan).invoke({prompt:'deterministic mascot integration',jobId,jobDir,plan:null,asset:null,videoPath:null});
  for(const script of ['verify_mascot.py','review_mascot.py'])
    await runCommand(BLENDER,['--background','--disable-autoexec',path.join(jobDir,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender',script),'--',jobDir],ROOT);
  await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',path.join(ROOT,'workers/blender/test_import.py'),'--',path.join(jobDir,'asset.json')],ROOT);
  console.log('MASCOT_REVIEW_JOB',jobDir);
});
