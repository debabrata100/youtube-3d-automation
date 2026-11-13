import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {ROOT,BLENDER} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
import {SceneSchema} from '../src/schemas/scene.js';
import {verifyVideo} from '../src/utils/verifyVideo.js';
test('performance artifacts, transparent comparative metrics and rig reload',{timeout:180000},async()=>{
 const job=process.env.WOLF_PERFORMANCE_JOB;assert.ok(job,'Run wolf:performance-review then set WOLF_PERFORMANCE_JOB');
 const report=JSON.parse(await readFile(path.join(job,'animation-report.json'),'utf8'));
 assert.equal(report.status,'verified_pending_human_visual_review');assert.equal(report.reviewOnly,true);assert.equal(report.productionPublishingAllowed,false);
 assert.equal(report.wave.action,'Wolf.Controller.Wave.v3');assert.equal(report.wave.cycles,2);assert.ok(report.wave.returnToIdleVerifiedDelta.max<1e-5);
 assert.equal(report.motion.displacementMeters,3);assert.ok(report.floor.minimum>=.014);
 for(const kind of ['foot-contact','wave','camera'])assert.ok(report.performancePreviews[kind].length>0);
 for(const filename of ['contact-sheet.png','comparison-report.json','visual-review-checklist.md'])assert.ok((await stat(path.join(job,filename))).size>0);
 assert.equal(createHash('sha256').update(await readFile(report.source)).digest('hex'),report.sourceSha256);
 if(report.performanceComparison.available){
  const c=report.performanceComparison;assert.equal(c.before.stancePairs,c.after.stancePairs);
  assert.ok(c.before.p95StanceVelocity<=c.before.maxStanceVelocity && c.after.p95StanceVelocity<=c.after.maxStanceVelocity);
  assert.ok(Array.isArray(c.metricRegressions));
 }
 await verifyVideo(path.join(job,'output/animation.mp4'),SceneSchema.parse(JSON.parse(await readFile(path.join(job,'plan.json'),'utf8'))));
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(job,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/test_performance.py'),'--',job],ROOT);
});
