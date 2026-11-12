import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {ROOT} from '../src/utils/paths.js';
import {SceneSchema} from '../src/schemas/scene.js';
import {AssetSchema,resolveAsset,validateAnimations} from '../src/assets/registry.js';
import {normalizeScenePlan} from '../src/schemas/llmScene.js';
const fixture=JSON.parse(await readFile(path.join(ROOT,'assets/plans/mascot-v2.json'),'utf8'));
test('mascot final/preview schemas, facial independence, transitions and strict normalization',()=>{
  SceneSchema.parse(fixture);
  assert.throws(()=>normalizeScenePlan({scene:{unsupported:'Dancing is not registered'}}),/Unsupported request: Dancing/);
  SceneSchema.parse({...fixture,renderMode:'preview',resolution:{width:640,height:360}});
  const llm=structuredClone(fixture);
  for(const action of llm.character.actions) for(const key of ['startPosition','endPosition']) {
    const p=action[key];action[key]=p?{x:p[0],y:p[1],z:p[2]}:null;
  }
  assert.deepEqual(normalizeScenePlan({scene:llm}),fixture);
  for(const mutate of [
    (p:any)=>p.character.actions[0].blendInFrames=100,
    (p:any)=>p.character.actions[0].endFrame=100,
    (p:any)=>p.character.expressions[0].intensity=2,
    (p:any)=>p.character.expressions[0].name='angry',
    (p:any)=>p.character.expressions.push({...p.character.expressions[0]}),
    (p:any)=>p.resolution.width=640,
    (p:any)=>p.character.actions[0].endPosition=[5,0,0],
  ]) {const p=structuredClone(fixture);mutate(p);assert.equal(SceneSchema.safeParse(p).success,false)}
});
test('mascot metadata and unsupported facial/animation rejection',async()=>{
  const entries=JSON.parse(await readFile(path.join(ROOT,'assets/characters/registry.json'),'utf8'));
  const metadata=entries.find((a:{id:string})=>a.id==='mascot-v2');
  AssetSchema.parse(metadata);
  assert.equal(AssetSchema.safeParse({...metadata,license:{...metadata.license,commercialUse:false}}).success,false);
  assert.equal(AssetSchema.safeParse({...metadata,license:{...metadata.license,source:''}}).success,false);
  assert.equal(AssetSchema.safeParse({...metadata,normalization:{scale:0,rotationDegrees:[0,0,0]}}).success,false);
  assert.equal(AssetSchema.safeParse({...metadata,license:{name:'unknown'}}).success,false);
  const fake={...metadata,absolutePath:'/unused'};
  const plan=SceneSchema.parse(fixture);validateAnimations(plan,fake);
  assert.throws(()=>validateAnimations(plan,{...fake,facialControls:{}}),/facial/);
  assert.throws(()=>validateAnimations(plan,{...fake,actions:{}}),/animation/);
  assert.throws(()=>validateAnimations(plan,{...fake,rigDefinition:'custom'}),/rig/);
});
