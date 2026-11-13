import {test} from 'node:test';
import assert from 'node:assert/strict';
import {SceneInstructionSchema} from '../src/scene/schema.js';
import {SceneDirector,greetingDemo,headingTo,safeDestination,positionAt} from '../src/scene/sceneDirector.js';
const director=new SceneDirector({'wolf-warrior-native':{radiusMeters:1}});
test('scene plan deterministic; separate controllers and greeting response timing',()=>{
 const p=greetingDemo(1),a=director.plan(p),b=director.plan(p);assert.deepEqual(a,b);assert.equal(a.frameCount,480);
 assert.equal(a.controllers[0]!.controller.actions.find(a=>a.type==='wave')!.start,12);assert.equal(a.controllers[1]!.controller.actions.find(a=>a.type==='wave')!.start,15);
 assert.ok(a.minimumSeparationMeters>=.5);a.controllers[0]!.controller.actions[0]!.end=1;assert.equal(a.controllers[1]!.controller.actions[0]!.end,9);
});
test('reject duplicate IDs, missing assets, invalid references and camera targets',()=>{
 for(const mutate of [(p:any)=>p.characters[1].id='wolf-a',(p:any)=>p.characters[0].assetId='missing',(p:any)=>p.interactions[0].target='missing',(p:any)=>p.cameraShots[0].subjects=['missing'],(p:any)=>p.interactions[1].receiver='wolf-a']){const p=greetingDemo(1);mutate(p);assert.throws(()=>director.plan(p));}
});
test('reject invalid intervals, response ordering and explicit/event conflicts',()=>{
 for(const mutate of [(p:any)=>p.interactions[0].end=21,(p:any)=>p.interactions[0].start=3.01,(p:any)=>p.interactions[1].responseSeconds=14,(p:any)=>p.characters[0].timeline=[{type:'idle',start:3,end:9}],(p:any)=>p.cameraShots[1].start=4,(p:any)=>p.interactions.push({...p.interactions[1],id:'duplicate-event'})]){const p=greetingDemo(1);mutate(p);assert.throws(()=>director.plan(p));}
});
test('world -Y heading and safe stopping use adapter conventions',()=>{
 assert.equal(headingTo([0,0],[0,-1]),0);assert.equal(headingTo([0,0],[1,0]),90);assert.equal(headingTo([0,0],[-1,0]),-90);
 assert.throws(()=>headingTo([0,0],[0,0]));assert.deepEqual(safeDestination([-5,0,0],[2,0,0],3),[-1,0,0]);assert.throws(()=>safeDestination([0,0,0],[1,0,0],2));
});
test('reject initial overlap, unsafe approach, crossing trajectories and sideways walking',()=>{
 for(const mutate of [(p:any)=>p.characters[1].initialPosition=p.characters[0].initialPosition,(p:any)=>p.interactions[0].stoppingDistanceMeters=1,(p:any)=>p.characters[0].initialHeadingDegrees=0]){const p=greetingDemo(1);mutate(p);assert.throws(()=>director.plan(p));}
 const p=greetingDemo(1);p.interactions=[];p.characters[0]!.initialPosition=[-3,0,0];p.characters[1]!.initialPosition=[3,0,0];p.characters[1]!.initialHeadingDegrees=-90;
 p.characters[0]!.timeline=[{type:'walk',start:0,end:6,destination:[3,0,0],speedMetersPerSecond:1}];p.characters[1]!.timeline=[{type:'walk',start:0,end:6,destination:[-3,0,0],speedMetersPerSecond:1}];assert.throws(()=>director.plan(p),/Collision warning/);
});
test('facing moving characters samples event start; point/camera targeting and selected subjects',()=>{
 const p=greetingDemo(1);p.interactions=[p.interactions[0]!,{id:'face',type:'faceTarget',actor:'wolf-b',target:{kind:'character',id:'wolf-a'},start:4,end:5}];
 const result=director.plan(p);const a=result.controllers[1]!.controller.actions.find(a=>a.type==='faceTarget');assert.ok(a?.type==='faceTarget');assert.deepEqual(a.target,positionAt(p.characters[0]!.initialPosition,result.controllers[0]!.controller.actions,4));
 p.cameraShots[3]!.subjects=['wolf-a'];SceneInstructionSchema.parse(p);
 p.interactions=[{id:'camera',type:'faceTarget',actor:'wolf-a',target:{kind:'camera',position:[0,-10,0]},start:0,end:1}];assert.ok(director.plan(p));
});
test('greeting reserves receiver idle and wrapped initial headings remain valid',()=>{
 const p=greetingDemo(1);p.characters[1]!.timeline=[{type:'turn',mode:'relative',degrees:20,start:12,end:14}];assert.throws(()=>director.plan(p),/Conflicting/);
 const q=greetingDemo(1);q.characters[0]!.initialHeadingDegrees=810;assert.ok(director.plan(q));
});
