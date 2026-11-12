import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {ControllerSchema} from '../src/animation/animationSchema.js';
import {controllerScene} from '../src/animation/characterController.js';
import {ROOT} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
const plan=JSON.parse(await readFile(path.join(ROOT,'assets/plans/wolf-polish.json'),'utf8'));
test('camera shots validate explicit cuts, smooth transitions, contiguous coverage and targets',()=>{
 ControllerSchema.parse(plan);controllerScene(plan);
 for(const edit of [(p:any)=>p.cameraShots[1].start=7,(p:any)=>p.cameraShots[1].transitionFrames=6,(p:any)=>p.cameraShots[2].transitionFrames=0,(p:any)=>p.cameraShots[0].target='another-character',(p:any)=>p.cameraShots[1].preset='portrait',(p:any)=>delete p.cameraShots,(p:any)=>p.cameraShots[2].end=14]){
  const p=structuredClone(plan);edit(p);assert.equal(ControllerSchema.safeParse(p).success,false);
 }
});
test('contact detection, correction release envelope and paired statistics',async()=>{
 await runCommand('python3',[path.join(ROOT,'workers/blender/test_foot_contact_unit.py')],ROOT);
});
