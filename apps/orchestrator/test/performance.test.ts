import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {ROOT} from '../src/utils/paths.js';
import {ControllerSchema,WaveV3Schema} from '../src/animation/animationSchema.js';
import {controllerScene} from '../src/animation/characterController.js';
import {runCommand} from '../src/utils/runCommand.js';
const fixture=JSON.parse(await readFile(path.join(ROOT,'assets/plans/wolf-performance.json'),'utf8'));
test('opt-in performance schema and wave parameters preserve the original timeline',()=>{
 const plan=ControllerSchema.parse(fixture);const scene=controllerScene(plan);
 assert.equal(scene.durationSeconds,15);assert.equal(scene.character.actions.at(-1)!.endFrame,360);
 assert.equal(WaveV3Schema.parse({}).handHeight,.8);
 for(const patch of [{intensity:2},{handHeight:.3},{waveCount:3},{wristAmplitude:1},{anticipation:.9},{recovery:.8},{script:'evil.py'}])assert.equal(WaveV3Schema.safeParse(patch).success,false);
 assert.equal(ControllerSchema.safeParse({...fixture,polish:false}).success,false);
});
test('release, gain continuity, percentile and comparable masks',async()=>{
 await runCommand('python3',[path.join(ROOT,'workers/blender/test_performance_math_unit.py')],ROOT);
});
