import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {ROOT,BLENDER} from '../src/utils/paths.js';
import {runCommand} from '../src/utils/runCommand.js';
test('forward wave clears calibrated chest surface at all four headings on both actors',{timeout:600000},async()=>{
 const job=process.env.WOLF_INTERACTION_JOB;assert.ok(job);
 const r=JSON.parse(await readFile(path.join(job,'wave-diagnostics.json'),'utf8'));
 assert.equal(r.passed,true);assert.equal(r.nativeActionsUnchanged,true);assert.equal(r.headingTests.length,8);
 for(const actor of ['wolf-a','wolf-b'])for(const heading of [0,90,180,270]){
  const row=r.headingTests.find((t:any)=>t.actor===actor&&t.headingDegrees===heading);assert.ok(row?.passed);
  assert.ok(row.activeForwardMinimumMeters>=row.calibration.requiredWristForwardMeters);
  assert.ok(row.maximumJointRotationStepRadians<=.35);
  assert.ok(row.maximumElbowStepMeters<=.12*row.calibration.armLengthMeters);
  assert.ok(row.samples.filter((s:any)=>s.activeGreeting).every((s:any)=>s.palmForwardAlignment>=.8&&s.fingersUpAlignment>=.8));
  assert.equal(row.torsoTriangleIntersections.length,0);assert.equal(row.failures.length,0);
 }
 const previews=JSON.parse(await readFile(path.join(job,'previews/wave/index.json'),'utf8'));
 assert.equal(previews.length,24);for(const p of previews)assert.ok((await stat(p.path)).size>0);
 assert.ok((await stat(path.join(job,'wave-contact-sheet.png'))).size>0);
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(job,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/wave_review.py'),'--','diagnose',job],ROOT);
 await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',path.join(job,'scene.blend'),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender/test_palm_calibration.py'),'--',job],ROOT);
});
