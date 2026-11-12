import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {SceneSchema} from '../src/schemas/scene.js';
import {resolveAsset,validateAnimations} from '../src/assets/registry.js';
import {character,ball} from './fixtures.js';
test('legacy ball and character plans validate',()=>{SceneSchema.parse(ball);SceneSchema.parse(character)});
test('invalid plans rejected',()=>{
  for (const patch of [{name:'dance'},{startFrame:0},{startFrame:72,endFrame:71},{endFrame:121},{endFrame:73},{startPosition:[1,0,0],endPosition:undefined}]) {
    const p=structuredClone(character);Object.assign(p.character.actions[0]!,patch);assert.equal(SceneSchema.safeParse(p).success,false);
  }
  const p=structuredClone(character);Object.assign(p.character,{path:'/tmp/evil.py'});assert.equal(SceneSchema.safeParse(p).success,false);
  assert.equal(SceneSchema.safeParse({fps:24}).success,false);
});
test('registry resolution, missing assets, paths and unsupported actions',async()=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'character-registry-'));
  try {
    await mkdir(path.join(root,'characters'));
    const entry={id:'test',name:'Test',version:'1',path:'characters/test.blend',armature:'Rig',bones:['root'],actions:{idle:'idle.v1'},license:{name:'test',source:'original',commercialUse:true}};
    const save=()=>writeFile(path.join(root,'characters/registry.json'),JSON.stringify([entry]));
    await save();
    await assert.rejects(resolveAsset('unknown',root),/Unknown/);
    await assert.rejects(resolveAsset('test',root),/Missing/);
    await writeFile(path.join(root,entry.path),'fixture');
    const asset=await resolveAsset('test',root);assert.equal(asset.id,'test');
    const plan=SceneSchema.parse(character);if ('character' in plan) plan.character.assetId='test';
    assert.throws(()=>validateAnimations(plan,asset),/Unsupported/);
    entry.path='../outside.blend';await save();await assert.rejects(resolveAsset('test',root),/escapes/);
    entry.path='characters/file.py';await save();await assert.rejects(resolveAsset('test',root),/Unsupported/);
    entry.path='characters/link.blend';await symlink('/etc/hosts',path.join(root,entry.path));await save();await assert.rejects(resolveAsset('test',root),/Invalid/);
  } finally {await rm(root,{recursive:true,force:true})}
});
test('duration limits, required fields, mixed plans and discontinuous root travel',()=>{
  for (const durationSeconds of [0,11,1.5]) assert.equal(SceneSchema.safeParse({...character,durationSeconds}).success,false);
  assert.equal(SceneSchema.safeParse({...character,...ball}).success,false);
  assert.equal(SceneSchema.safeParse({...character,character:{actions:[]}}).success,false);
  const plan=SceneSchema.parse(character);
  if (!('character' in plan)) throw new Error('Expected character');
  plan.character.actions[1]!.startPosition=[1,0,0];plan.character.actions[1]!.endPosition=[2,0,0];
  assert.throws(()=>validateAnimations(plan,{id:'demo-character-v1',name:'Demo',path:'x.blend',absolutePath:'/x.blend',version:'1',procedural:true,armature:'Rig',bones:['root'],actions:{walk:'walk',wave:'wave'},license:{name:'CC0',source:'original',commercialUse:true}}),/continuous/);
});
