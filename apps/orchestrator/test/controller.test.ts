import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {ROOT} from '../src/utils/paths.js';
import {ControllerSchema} from '../src/animation/animationSchema.js';
import {planMotion,shortestHeading,interpolateHeading,interpolatePosition} from '../src/animation/motionPlanner.js';
import {controllerScene} from '../src/animation/characterController.js';
import {SceneSchema} from '../src/schemas/scene.js';
const fixture=JSON.parse(await readFile(path.join(ROOT,'assets/plans/wolf-motion.json'),'utf8'));
test('controller scheduling and existing scene validation',()=>{
 const motion=planMotion(fixture);assert.equal(motion.timeline[2]!.startFrame,73);assert.equal(motion.timeline.at(-1)!.endFrame,360);
 SceneSchema.parse(controllerScene(fixture));
 for(const edit of [(p:any)=>p.actions[1].start=1,(p:any)=>p.actions[0].end=.03,(p:any)=>p.actions[2].type='fly',(p:any)=>p.durationSeconds=16]){
  const p=structuredClone(fixture);edit(p);assert.equal(ControllerSchema.safeParse(p).success,false);
 }
 const bad=structuredClone(fixture);bad.actions[2].speedMetersPerSecond=2;assert.throws(()=>planMotion(bad),/speed/);
});
test('shortest headings and endpoint-clamped position interpolation',()=>{
 assert.equal(shortestHeading(350,10),370);assert.equal(shortestHeading(10,350),-10);
 assert.equal(interpolateHeading(350,10,.5),360);
 assert.deepEqual(interpolatePosition([0,0,0],[3,0,0],0),[0,0,0]);
 assert.deepEqual(interpolatePosition([0,0,0],[3,0,0],1),[3,0,0]);
 assert.deepEqual(interpolatePosition([0,0,0],[3,0,0],2),[3,0,0]);
});
