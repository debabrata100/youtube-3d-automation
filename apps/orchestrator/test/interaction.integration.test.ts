import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {ROOT,BLENDER} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
import {verifyVideo} from '../src/utils/verifyVideo.js';
test('two controller instances, isolated waves/root motion, camera, saved scene and final video',{timeout:600000},async()=>{
 const job=process.env.WOLF_INTERACTION_JOB;assert.ok(job,'Run wolf:interaction-review and set WOLF_INTERACTION_JOB');
 const report=JSON.parse(await readFile(path.join(job,'animation-report.json'),'utf8')),execution=JSON.parse(await readFile(path.join(job,'scene-plan.json'),'utf8'));
 assert.equal(report.status,'verified_pending_human_visual_review');assert.equal(report.savedSceneReloadVerified,true);assert.equal(report.reviewOnly,true);assert.equal(report.productionPublishingAllowed,false);assert.equal(report.frames,480);
 const m=report.multiCharacter;assert.equal(m.characterCount,2);assert.equal(m.independentArmatures,true);assert.equal(m.independentAnimationState,true);assert.equal(m.isolationProbes.length,2);assert.equal(m.locomotionProbes.length,1);assert.equal(m.collisionWarnings.length,0);assert.ok(m.minimumSeparationMeters>=.5);assert.equal(m.cameraCoverage.reduce((n:number,s:any)=>n+s.framesChecked,0),480);
 assert.ok(Math.abs(m.transforms[0].worldTravelMeters-3)<1e-5);assert.equal(m.transforms[1].worldTravelMeters,0);
 assert.equal(createHash('sha256').update(await readFile(report.source)).digest('hex'),report.sourceSha256);
 for(const f of ['contact-sheet.png','implementation-report.md','scene.blend'])assert.ok((await stat(path.join(job,f))).size>0);
 await verifyVideo(path.join(job,'output/animation.mp4'),execution.scene);
 // The same numerical assertions run again in a fresh Blender process, with scripts disabled.
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(job,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/test_scene_composition.py'),'--',job],ROOT);
});
