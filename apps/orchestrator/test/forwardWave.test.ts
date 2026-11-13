import {test} from 'node:test';
import assert from 'node:assert/strict';
import {ControllerSchema} from '../src/animation/animationSchema.js';
import {SceneDirector,greetingDemo} from '../src/scene/sceneDirector.js';
test('scene greetings opt into corrected wave while legacy controller plans retain v3',()=>{
 const result=new SceneDirector({'wolf-warrior-native':{radiusMeters:1}}).plan(greetingDemo(1));
 for(const c of result.controllers)assert.equal(c.controller.performance?.forwardWave,true);
 const legacy=structuredClone(result.controllers[0]!.controller);delete legacy.performance!.forwardWave;
 assert.equal(ControllerSchema.parse(legacy).performance?.forwardWave,undefined);
 assert.equal(ControllerSchema.safeParse({...legacy,performance:{...legacy.performance,forwardWave:false}}).success,false);
});
