import {test} from 'node:test';
import {randomUUID} from 'node:crypto';
import path from 'node:path';
import {createWorkflow} from '../src/graph/workflow.js';
import {SceneSchema} from '../src/schemas/scene.js';
import {ROOT,BLENDER} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
import {character,ball} from './fixtures.js';
test('procedural asset, character and legacy ball through LangGraph, render and FFprobe', {timeout:1200000}, async()=>{
  await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',path.join(ROOT,'workers/blender/character.py'),'--',path.join(ROOT,'assets/characters/demo-character-v1.blend')],ROOT);
  for (const fixture of [character,ball]) {
    const jobId='integration-'+randomUUID();const jobDir=path.join(ROOT,'jobs',jobId);
    await createWorkflow(async()=>SceneSchema.parse(fixture)).invoke({prompt:'deterministic integration fixture',jobId,jobDir,plan:null,asset:null,videoPath:null});
    await runCommand(BLENDER,['--background','--disable-autoexec',path.join(jobDir,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/verify_scene.py'),'--',jobDir],ROOT);
  }
});
