import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {ROOT} from '../src/utils/paths.js';
import {SceneSchema} from '../src/schemas/scene.js';
import {WolfAssetSchema} from '../src/assets/wolfAsset.js';
import {validateAnimations,resolveAsset} from '../src/assets/registry.js';
test('wolf review uses only authorized native idle/walk/idle with license pending',async()=>{
  const plan=SceneSchema.parse(JSON.parse(await readFile(path.join(ROOT,'assets/plans/wolf-native.json'),'utf8')));
  const asset={...WolfAssetSchema.parse(JSON.parse(await readFile(path.join(ROOT,'assets/characters/wolf-warrior/asset.json'),'utf8'))),absolutePath:'/not-opened-by-unit-tests'};assert.equal(asset.license.commercialUse,false);assert.equal(asset.reviewOnly,true);
  validateAnimations(plan,asset);
  await assert.rejects(resolveAsset('wolf-warrior-native'),/Unknown character/);
  if(!('character' in plan))throw new Error('Expected character');
  for(const patch of [{name:'wave'},{startFrame:2},{startPosition:[0,0,0],endPosition:[1,0,0]}]){
    const bad=structuredClone(plan);Object.assign(bad.character.actions[0]!,patch);assert.throws(()=>validateAnimations(bad,asset),/Wolf Phase 2/);
  }
});
