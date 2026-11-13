import {z} from 'zod';
import {ControllerSchema} from '../animation/animationSchema.js';
export const Position=z.tuple([z.number().min(-10).max(10),z.number().min(-10).max(10),z.literal(0)]);
const id=z.string().regex(/^[a-z][a-z0-9-]{0,63}$/);
const timing={start:z.number().nonnegative(),end:z.number().positive()};
const target=z.discriminatedUnion('kind',[
 z.object({kind:z.literal('character'),id}).strict(),
 z.object({kind:z.literal('point'),position:Position}).strict(),
 z.object({kind:z.literal('camera'),position:Position}).strict(),
]);
export const SceneInstructionSchema=z.object({
 schemaVersion:z.literal('1.0'),sceneId:id,fps:z.literal(24),durationSeconds:z.number().int().min(1).max(30),
 resolution:z.object({width:z.literal(1280),height:z.literal(720)}).strict(),
 minimumGapMeters:z.number().min(.1).max(3),
 characters:z.array(z.object({id,assetId:z.string().min(1),initialPosition:Position,initialHeadingDegrees:z.number().finite(),
  timeline:z.array(ControllerSchema.shape.actions.element)}).strict()).min(2).max(8),
 interactions:z.array(z.discriminatedUnion('type',[
  z.object({id,type:z.literal('faceTarget'),actor:id,target,...timing}).strict(),
  z.object({id,type:z.literal('approach'),actor:id,target:id,stoppingDistanceMeters:z.number().positive(),...timing}).strict(),
  z.object({id,type:z.literal('greeting'),initiator:id,receiver:id,start:z.number().nonnegative(),responseSeconds:z.number().nonnegative(),waveDuration:z.number().min(.75),faceDuration:z.number().min(2/24)}).strict(),
  z.object({id,type:z.literal('response'),actor:id,target:id,...timing}).strict(),
 ])),
 cameraShots:z.array(z.object({...timing,type:z.enum(['establishing','tracking','two_character','medium']),subjects:z.array(id).min(1),transition:z.literal('cut')}).strict()).min(1),
}).strict().superRefine((p,c)=>{
 const issue=(message:string)=>c.addIssue({code:'custom',message});
 const ids=new Set(p.characters.map(x=>x.id));
 if(ids.size!==p.characters.length)issue('Character IDs must be unique');
 const eventIds=new Set(p.interactions.map(x=>x.id));if(eventIds.size!==p.interactions.length)issue('Interaction IDs must be unique');
 const ref=(v:string)=>{if(!ids.has(v))issue(`Unknown character reference: ${v}`)};
 const interval=(start:number,end:number)=>{if(end<=start||end>p.durationSeconds||![start,end].every(t=>Number.isInteger(t*p.fps)))issue('Intervals must be positive, frame-aligned and fit scene duration')};
 for(const ch of p.characters){let end=0;for(const a of ch.timeline){interval(a.start,a.end);if(a.start<end)issue(`Overlapping timeline for ${ch.id}`);end=a.end;}}
 for(const e of p.interactions){
  if(e.type==='greeting'){
   ref(e.initiator);ref(e.receiver);if(e.initiator===e.receiver)issue('Greeting requires different characters');
   interval(e.start-e.faceDuration,e.start);interval(e.start,e.start+e.waveDuration);interval(e.responseSeconds,e.responseSeconds+e.waveDuration);
   if(e.start<e.faceDuration||e.responseSeconds<e.start+e.waveDuration)issue('Response must follow greeting and face interval must start inside scene');
  }else{ref(e.actor);if(e.type==='faceTarget'){if(e.target.kind==='character'){ref(e.target.id);if(e.target.id===e.actor)issue('Cannot face self');}}else{ref(e.target);if(e.target===e.actor)issue('Interaction requires different characters');}interval(e.start,e.end);}
 }
 let end=0;for(const s of p.cameraShots){interval(s.start,s.end);if(s.start!==end)issue('Camera shots must cover scene contiguously');end=s.end;s.subjects.forEach(ref);if(new Set(s.subjects).size!==s.subjects.length)issue('Camera subjects must be unique');if(['establishing','two_character'].includes(s.type)&&s.subjects.length<2)issue('Wide/two-character shots require at least two subjects');}if(end!==p.durationSeconds)issue('Camera shots must cover scene duration');
});
export type SceneInstructions=z.infer<typeof SceneInstructionSchema>;
