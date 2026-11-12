import {ControllerSchema,ControllerSceneSchema,type ControllerPlan} from './animationSchema.js';
import {planMotion} from './motionPlanner.js';
export function controllerScene(input:ControllerPlan){
 const controller=ControllerSchema.parse(input);const motion=planMotion(controller);
 const actions=motion.timeline.map(a=>({name:a.type==='walk'?'walk' as const:'idle' as const,startFrame:a.startFrame,endFrame:a.endFrame}));
 return ControllerSceneSchema.parse({durationSeconds:controller.durationSeconds,fps:24,resolution:{width:1280,height:720},character:{assetId:controller.characterId,actions},environment:{type:'simple-ground',color:'gray'},controller});
}
