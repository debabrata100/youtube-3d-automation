import {shortestHeading} from '../animation/motionPlanner.js';
import {ControllerSchema,type ControllerPlan,WaveV3Schema} from '../animation/animationSchema.js';
import {SceneInstructionSchema,type SceneInstructions} from './schema.js';
type Position=[number,number,0];
type Action=ControllerPlan['actions'][number];
export type Footprints=Record<string,{radiusMeters:number}>;
export function headingTo(a:number[],b:number[]){if(Math.hypot(b[0]!-a[0]!,b[1]!-a[1]!)<1e-6)throw new Error('Facing target equals current position');return Math.atan2(b[0]!-a[0]!,a[1]!-b[1]!)*180/Math.PI;}
export function safeDestination(origin:Position,target:Position,distance:number):Position{
 const d=Math.hypot(target[0]-origin[0],target[1]-origin[1]);if(d<=distance)throw new Error('Approach starts inside stopping distance');
 return [target[0]+(origin[0]-target[0])*distance/d,target[1]+(origin[1]-target[1])*distance/d,0];
}
// Exact controller ramp, sampled on rendered frames. Swept checks also cover intervals between frames.
export function positionAt(initial:Position,actions:Action[],seconds:number,fps=24):Position{
 let p:Position=[...initial];for(const a of actions){if(a.type!=='walk'||seconds<a.start)continue;if(seconds>=a.end){p=[...a.destination];continue;}
 const t=Math.max(0,Math.min(1,(seconds*fps-(a.start*fps+1))/(a.end*fps-(a.start*fps+1))));const r=.12;
 const u=t<r?t*t/(2*r*(1-r)):t>1-r?1-(1-t)**2/(2*r*(1-r)):(t-r/2)/(1-r);
 p=p.map((v,i)=>v+(a.destination[i]!-v)*u) as Position;break;}return p;
}
export class SceneDirector{
 constructor(private footprints:Footprints){}
 plan(input:unknown){
  const scene=SceneInstructionSchema.parse(input);
  for(const c of scene.characters)if(!this.footprints[c.assetId]||!(this.footprints[c.assetId]!.radiusMeters>0)||!Number.isFinite(this.footprints[c.assetId]!.radiusMeters))throw new Error(`Missing asset reference or measured footprint: ${c.assetId}`);
  const cameraTargets=scene.interactions.flatMap(e=>e.type==='faceTarget'&&e.target.kind==='camera'?[e.target.position]:[]);
  const cameraAnchor=cameraTargets[0]??null;
  if(cameraTargets.some(p=>p.some((v,i)=>v!==cameraAnchor![i])))throw new Error('Camera-facing events must use one fixed camera XY anchor');
  const schedules=new Map(scene.characters.map(c=>[c.id,structuredClone(c.timeline)]));
  const character=(id:string)=>scene.characters.find(c=>c.id===id)!;
  const pos=(id:string,t:number)=>positionAt(character(id).initialPosition,schedules.get(id)!,t);
  const insert=(id:string,a:Action)=>{const list=schedules.get(id)!;if(list.some(b=>a.start<b.end&&a.end>b.start))throw new Error(`Conflicting actions/interactions for ${id} at ${a.start}–${a.end}; remove the explicit action or reschedule the event`);list.push(a);list.sort((a,b)=>a.start-b.start);};
  const events=[...scene.interactions].sort((a,b)=>(a.type==='greeting'?a.start-a.faceDuration:a.start)-(b.type==='greeting'?b.start-b.faceDuration:b.start)||a.id.localeCompare(b.id));
  // Resolve locomotion first, so facing can sample all final trajectories at event start.
  for(const e of events)if(e.type==='approach'){
   const required=this.footprints[character(e.actor).assetId]!.radiusMeters+this.footprints[character(e.target).assetId]!.radiusMeters+scene.minimumGapMeters;
   if(e.stoppingDistanceMeters<required)throw new Error(`Unsafe stopping distance for ${e.id}: require at least ${required} meters`);
   const origin=pos(e.actor,e.start),destination=safeDestination(origin,pos(e.target,e.start),e.stoppingDistanceMeters);
   insert(e.actor,{type:'walk',start:e.start,end:e.end,destination,speedMetersPerSecond:Math.hypot(destination[0]-origin[0],destination[1]-origin[1])/(e.end-e.start)});
  }
  for(const e of events){
   if(e.type==='faceTarget')insert(e.actor,{type:'faceTarget',start:e.start,end:e.end,target:e.target.kind==='character'?pos(e.target.id,e.start):e.target.position});
   if(e.type==='response')insert(e.actor,{type:'wave',start:e.start,end:e.end});
   if(e.type==='greeting'){
    const start=e.start-e.faceDuration;
    for(const [actor,other] of [[e.initiator,e.receiver],[e.receiver,e.initiator]] as const)insert(actor,{type:'faceTarget',start,end:e.start,target:pos(other,start)});
    insert(e.initiator,{type:'wave',start:e.start,end:e.start+e.waveDuration});
    insert(e.receiver,{type:'idle',start:e.start,end:e.responseSeconds});
    insert(e.receiver,{type:'wave',start:e.responseSeconds,end:e.responseSeconds+e.waveDuration});
   }
  }
  const controllers=scene.characters.map(c=>{
   const actions:Action[]=[];let end=0;
   for(const a of schedules.get(c.id)!){if(a.start>end)actions.push({type:'idle',start:end,end:a.start});actions.push(a);end=a.end;}
   if(end<scene.durationSeconds)actions.push({type:'idle',start:end,end:scene.durationSeconds});
   const controller=ControllerSchema.parse({characterId:c.assetId,fps:scene.fps,durationSeconds:scene.durationSeconds,startPosition:c.initialPosition,headingDegrees:c.initialHeadingDegrees,cameraPreset:'full_body',polish:true,performance:{forwardWave:true,wave:WaveV3Schema.parse({}),releaseFrames:24},cameraShots:[{start:0,end:scene.durationSeconds,preset:'wide',target:c.assetId,transition:'cut',transitionFrames:0}],actions});
   // Fail early for sideways walking, matching the adapter's heading convention.
   let p:number[]=[...c.initialPosition],heading=c.initialHeadingDegrees;
   for(const a of actions){if(a.type==='turn')heading=a.mode==='absolute'?a.degrees:heading+a.degrees;if(a.type==='faceTarget')heading=headingTo(p,a.target);if(a.type==='turnToCamera')throw new Error('Use a scene faceTarget camera position instead of turnToCamera');if(a.type==='walk'){const desired=headingTo(p,a.destination);if(Math.abs(shortestHeading(heading,desired)-heading)>2.8)throw new Error(`Turn ${c.id} toward destination before walking`);p=[...a.destination];}}
   return {id:c.id,controller};
  });
  let minimumSeparationMeters=Infinity;
  const samples=controllers.map(c=>Array.from({length:scene.durationSeconds*scene.fps},(_,i)=>positionAt(character(c.id).initialPosition,c.controller.actions,(i+1)/scene.fps)));
  for(let a=0;a<controllers.length;a++)for(let b=a+1;b<controllers.length;b++){
   const radii=this.footprints[scene.characters[a]!.assetId]!.radiusMeters+this.footprints[scene.characters[b]!.assetId]!.radiusMeters;
   for(let f=0;f<samples[a]!.length;f++){
    const d=[0,1].map(i=>samples[a]![f]![i]!-samples[b]![f]![i]!);const next=Math.min(f+1,samples[a]!.length-1);const v=[0,1].map(i=>samples[a]![next]![i]!-samples[b]![next]![i]!-d[i]!);const vv=v[0]!**2+v[1]!**2;const t=vv?Math.max(0,Math.min(1,-(d[0]!*v[0]!+d[1]!*v[1]!)/vv)):0;
    const gap=Math.hypot(d[0]!+v[0]!*t,d[1]!+v[1]!*t)-radii;minimumSeparationMeters=Math.min(minimumSeparationMeters,gap);
    if(gap<scene.minimumGapMeters-1e-6)throw new Error(`Collision warning: ${controllers[a]!.id}/${controllers[b]!.id} at frame ${f+1}, conservative gap ${gap.toFixed(3)} m`);
   }
  }
  return {schemaVersion:'1.0',scene,controllers,events,cameraAnchor,frameCount:scene.durationSeconds*scene.fps,footprints:this.footprints,minimumSeparationMeters,targetSampling:'event start; camera targets are explicit world positions',reviewOnly:true,productionPublishingAllowed:false};
 }
}
export function greetingDemo(radius:number):SceneInstructions{
 const stop=2*radius+.7,bx=stop/2,ax=-stop/2-3;
 return SceneInstructionSchema.parse({schemaVersion:'1.0',sceneId:'wolf-greeting',fps:24,durationSeconds:20,resolution:{width:1280,height:720},minimumGapMeters:.5,
 characters:[{id:'wolf-a',assetId:'wolf-warrior-native',initialPosition:[ax,0,0],initialHeadingDegrees:90,timeline:[]},{id:'wolf-b',assetId:'wolf-warrior-native',initialPosition:[bx,0,0],initialHeadingDegrees:-60,timeline:[]}],
 interactions:[{id:'approach',type:'approach',actor:'wolf-a',target:'wolf-b',start:3,end:9,stoppingDistanceMeters:stop},{id:'greeting',type:'greeting',initiator:'wolf-a',receiver:'wolf-b',start:12,responseSeconds:15,waveDuration:3,faceDuration:3}],
 cameraShots:[{start:0,end:3,type:'establishing'},{start:3,end:9,type:'tracking'},{start:9,end:12,type:'two_character'},{start:12,end:15,type:'medium'},{start:15,end:18,type:'medium'},{start:18,end:20,type:'establishing'}].map(s=>({...s,subjects:['wolf-a','wolf-b'],transition:'cut'}))});
}
