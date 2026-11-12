import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {InspectionConfig,inspectCharacter} from '../src/assets/inspection.js';
test('inspection config rejects executable/unknown metadata and invalid axes/scale',()=>{
  InspectionConfig.parse({boneMap:{root:'Hips'},actionMap:{walk:'Walk'}});
  for(const config of [{script:'evil.py'},{orientation:{up:'Z',forward:'-Z'}},{heightMeters:{min:4,max:1}},{actionMap:{dance:'Dance'}},{boneMap:{root:''}}])
    assert.equal(InspectionConfig.safeParse(config).success,false);
});
test('inspection rejects missing/unsupported sources before spawning Blender',async()=>{
  const dir=await mkdtemp(path.join(os.tmpdir(),'inspect-input-'));
  try {
    await assert.rejects(inspectCharacter(path.join(dir,'missing.blend')),/ENOENT/);
    const file=path.join(dir,'model.py');await writeFile(file,'not executable');
    await assert.rejects(inspectCharacter(file),/Expected a/);
  } finally {await rm(dir,{force:true,recursive:true})}
});
