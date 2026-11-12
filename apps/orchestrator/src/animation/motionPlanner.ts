import {ControllerSchema,type ControllerPlan} from './animationSchema.js';
export const smoothstep=(t:number)=>{const x=Math.max(0,Math.min(1,t));return x*x*(3-2*x)};
// Heading zero faces world -Y; positive yaw turns toward +X.
export const shortestHeading=(a:number,b:number)=>a+((b-a+180)%360+360)%360-180;
export const interpolateHeading=(a:number,b:number,t:number)=>a+(shortestHeading(a,b)-a)*smoothstep(t);
export const interpolatePosition=(a:number[],b:number[],t:number)=>a.map((v,i)=>v+(b[i]!-v)*smoothstep(t));
export function planMotion(input:ControllerPlan){
 const plan=ControllerSchema.parse(input);let position=[...plan.startPosition];
 const timeline=plan.actions.map(action=>{
   const frames={startFrame:Math.round(action.start*plan.fps)+1,endFrame:Math.round(action.end*plan.fps)};
   if(action.type==='walk'){
     const distance=Math.hypot(...action.destination.map((v,i)=>v-position[i]!));
     if(distance<.01||Math.abs(distance/(action.end-action.start)-action.speedMetersPerSecond)>.02)throw new Error('Walking speed must equal destination distance / duration (within 0.02 m/s)');
     position=[...action.destination];
   }
   return {...action,...frames};
 });
 return {...plan,timeline};
}
