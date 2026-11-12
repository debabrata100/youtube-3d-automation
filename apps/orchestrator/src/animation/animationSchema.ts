import {z} from 'zod';
const position=z.tuple([z.number().min(-10).max(10),z.number().min(-10).max(10),z.literal(0)]);
const timing={start:z.number().min(0),end:z.number().positive()};
export const ControllerSchema=z.object({
  characterId:z.literal('wolf-warrior-native'),fps:z.literal(24),durationSeconds:z.number().int().min(1).max(30),
  startPosition:position,headingDegrees:z.number().finite(),cameraPreset:z.enum(['full_body','medium','close_up']),
  polish:z.boolean().optional(),
  cameraShots:z.array(z.object({start:z.number().min(0),end:z.number().positive(),preset:z.enum(['wide','medium']),target:z.literal('wolf-warrior-native'),transition:z.enum(['cut','smooth']),transitionFrames:z.number().int().min(0).max(48)}).strict()).optional(),
  actions:z.array(z.discriminatedUnion('type',[
    z.object({...timing,type:z.literal('idle')}).strict(),
    z.object({...timing,type:z.literal('turn'),mode:z.enum(['relative','absolute']),degrees:z.number().finite()}).strict(),
    z.object({...timing,type:z.literal('faceTarget'),target:position}).strict(),
    z.object({...timing,type:z.literal('walk'),destination:position,speedMetersPerSecond:z.number().positive().max(3)}).strict(),
    z.object({...timing,type:z.literal('turnToCamera')}).strict(),
    z.object({...timing,type:z.literal('wave')}).strict(),
  ])).min(1),
}).strict().superRefine((plan,ctx)=>{
  let end=0;let position:number[]=[...plan.startPosition];
  for(const action of plan.actions){
    if(action.start!==end||action.end<=action.start||action.end>plan.durationSeconds||![action.start,action.end].every(t=>Math.abs(t*plan.fps-Math.round(t*plan.fps))<1e-7))
      ctx.addIssue({code:'custom',message:'Timeline must be contiguous, frame-aligned, nonoverlapping and fit scene duration'});
    if(action.type==='walk') {
      const distance=Math.hypot(...action.destination.map((v,i)=>v-position[i]!));
      if(distance<.01 || Math.abs(distance/(action.end-action.start)-action.speedMetersPerSecond)>.02)ctx.addIssue({code:'custom',message:'Walking speed must equal distance / duration within 0.02 m/s'});
      position=[...action.destination];
    }
    const minimum=action.type==='wave'?.75:action.type==='walk'?.5:action.type==='idle'?1/plan.fps:2/plan.fps;
    if(action.end-action.start<minimum)ctx.addIssue({code:'custom',message:'Action is too short for a stable controller transition'});
    end=action.end;
  }
  if(plan.cameraShots){
    let cameraEnd=0;
    for(const shot of plan.cameraShots){
      if(cameraEnd===0&&shot.transition!=='cut')ctx.addIssue({code:'custom',message:'First camera shot must start with an explicit cut'});
      if(shot.start!==cameraEnd||shot.end<=shot.start||shot.end>plan.durationSeconds||![shot.start,shot.end].every(t=>Number.isInteger(t*plan.fps))||shot.transitionFrames>(shot.end-shot.start)*plan.fps||shot.transition==='cut'&&shot.transitionFrames!==0||shot.transition==='smooth'&&shot.transitionFrames<2)ctx.addIssue({code:'custom',message:'Camera shots must be contiguous, frame-aligned, with valid cut/smooth transition lengths'});
      cameraEnd=shot.end;
    }
    if(cameraEnd!==plan.durationSeconds)ctx.addIssue({code:'custom',message:'Camera shots must cover the scene'});
  }
  if(plan.polish && !plan.cameraShots)ctx.addIssue({code:'custom',message:'Polish requires an explicit camera schedule'});
  if(end!==plan.durationSeconds)ctx.addIssue({code:'custom',message:'Actions must fill the scene duration'});
});
export type ControllerPlan=z.infer<typeof ControllerSchema>;
export const ControllerSceneSchema=z.object({
  durationSeconds:z.number().int().min(1).max(30),fps:z.literal(24),resolution:z.object({width:z.literal(1280),height:z.literal(720)}).strict(),
  character:z.object({assetId:z.literal('wolf-warrior-native'),actions:z.array(z.object({name:z.enum(['idle','walk']),startFrame:z.number().int(),endFrame:z.number().int()}).strict())}).strict(),
  environment:z.object({type:z.literal('simple-ground'),color:z.literal('gray')}).strict(),controller:ControllerSchema,
}).strict().superRefine((p,c)=>{
 if(p.durationSeconds!==p.controller.durationSeconds)c.addIssue({code:'custom',message:'Controller and scene durations differ'});
 const expected=p.controller.actions.map(a=>({name:a.type==='walk'?'walk':'idle',startFrame:Math.round(a.start*p.fps)+1,endFrame:Math.round(a.end*p.fps)}));
 if(p.character.actions.length!==expected.length||p.character.actions.some((a,i)=>a.name!==expected[i]?.name||a.startFrame!==expected[i]?.startFrame||a.endFrame!==expected[i]?.endFrame))c.addIssue({code:'custom',message:'Compiled body schedule differs from controller instructions'});
});
