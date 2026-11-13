import {Annotation,StateGraph,START,END} from '@langchain/langgraph';
import {mkdir,readFile,writeFile,copyFile} from 'node:fs/promises';
import path from 'node:path';
import {ROOT,BLENDER} from '../utils/paths.js';
import {runCommand} from '../utils/runCommand.js';
import {resolveWolfAsset,type WolfAsset} from '../assets/wolfAsset.js';
import {controllerScene} from '../animation/characterController.js';
import {renderFrames,encodeVideo} from '../graph/mediaNodes.js';
import {verifyVideo} from '../utils/verifyVideo.js';
import {SceneDirector,greetingDemo,type Footprints} from './sceneDirector.js';
import {SceneInstructionSchema,type SceneInstructions} from './schema.js';
const State=Annotation.Root({jobDir:Annotation<string>,input:Annotation<unknown>,plan:Annotation<SceneInstructions>,asset:Annotation<WolfAsset>,footprints:Annotation<Footprints>,execution:Annotation<ReturnType<SceneDirector['plan']>>,videoPath:Annotation<string>});
async function blender(script:string,args:string[],blend?:string){await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec',...(blend?[blend]:[]),'--python-exit-code','1','--python',path.join(ROOT,'workers/blender',script),'--',...args],ROOT);}
export function createSceneWorkflow(){return new StateGraph(State)
 .addNode('validateScene',async s=>{await mkdir(s.jobDir,{recursive:true});return s.input?{plan:SceneInstructionSchema.parse(s.input)}:{};})
 .addNode('resolveInstances',async s=>{
  const asset=await resolveWolfAsset();if(s.plan?.characters.some(c=>c.assetId!==asset.id))throw new Error('Missing asset reference: only the registered wolf adapter is supported');
  const probe=path.join(s.jobDir,'footprint');await mkdir(probe);await writeFile(path.join(probe,'asset.json'),JSON.stringify(asset));await blender('scene_instance.py',['probe',probe]);
  const footprint=JSON.parse(await readFile(path.join(probe,'footprint.json'),'utf8'));return {asset,footprints:{[asset.id]:footprint},plan:s.plan??greetingDemo(footprint.radiusMeters)};
 })
 .addNode('planInteractions',async s=>{const execution=new SceneDirector(s.footprints).plan(s.plan);await writeFile(path.join(s.jobDir,'scene-plan.json'),JSON.stringify(execution,null,2));return {execution};})
 .addNode('buildScene',async s=>{
  for(const c of s.execution.controllers){const dir=path.join(s.jobDir,'characters',c.id);await mkdir(dir,{recursive:true});await writeFile(path.join(dir,'asset.json'),JSON.stringify(s.asset));await writeFile(path.join(dir,'plan.json'),JSON.stringify(controllerScene(c.controller)));await blender('scene_instance.py',['build',dir]);}
  await blender('scene_composition.py',['build',s.jobDir]);
  await blender('wave_review.py',['diagnose',s.jobDir],path.join(s.jobDir,'scene.blend'));return {};
 })
 .addNode('renderFrames',renderFrames).addNode('encodeVideo',encodeVideo)
 .addNode('verify',async s=>{await blender('scene_composition.py',['verify',s.jobDir],path.join(s.jobDir,'scene.blend'));const video=await verifyVideo(s.videoPath,s.plan);const f=path.join(s.jobDir,'animation-report.json'),report=JSON.parse(await readFile(f,'utf8'));await writeFile(f,JSON.stringify({...report,video,status:'verified_pending_human_visual_review'},null,2));return {};})
 .addNode('reviewArtifacts',async s=>{
  await blender('wave_review.py',['previews',s.jobDir],path.join(s.jobDir,'scene.blend'));
  await runCommand('ffmpeg',['-y','-v','error','-i',path.join(s.jobDir,'previews/wave/sheet-%02d.png'),'-vf','scale=384:216,tile=4x6','-frames:v','1',path.join(s.jobDir,'wave-contact-sheet.png')],ROOT);
  const dir=path.join(s.jobDir,'previews');await mkdir(dir,{recursive:true});const frames=[1,72,144,216,252,288,312,336,360,396,432,480].map(f=>Math.max(1,Math.round(f*s.execution.frameCount/480)));
  for(const [i,f] of frames.entries())await copyFile(path.join(s.jobDir,'frames',`frame_${String(f).padStart(4,'0')}.png`),path.join(dir,`sheet-${String(i+1).padStart(2,'0')}.png`));
  await runCommand('ffmpeg',['-y','-v','error','-i',path.join(dir,'sheet-%02d.png'),'-vf','scale=384:216,tile=4x3','-frames:v','1',path.join(s.jobDir,'contact-sheet.png')],ROOT);
  await writeFile(path.join(s.jobDir,'implementation-report.md'),`# Milestone 5 review\n\nSceneDirector compiles events to independent existing controllers. Characters are built in separate Blender processes and appended as local collections. All native Actions retain their source curves.\n\n${s.execution.frameCount} frames; 1280×720, 24 FPS H.264. See animation-report.json for measured checks. Footprints are conservative proxies, not triangle collision proof. Target positions are sampled at event start. Camera cuts are intentional.\n\nHuman review pending: inspect walking/contact, profile silhouettes, turn timing, both waves, idle recovery, spacing, camera cuts and interaction readability. Commercial licensing remains unverified; reviewOnly=true and productionPublishingAllowed=false. No publishing.\n`);return {};
 })
 .addEdge(START,'validateScene').addEdge('validateScene','resolveInstances').addEdge('resolveInstances','planInteractions').addEdge('planInteractions','buildScene').addEdge('buildScene','renderFrames').addEdge('renderFrames','encodeVideo').addEdge('encodeVideo','verify').addEdge('verify','reviewArtifacts').addEdge('reviewArtifacts',END).compile();}
