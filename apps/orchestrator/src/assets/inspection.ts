import {z} from 'zod';
import {realpath,stat,mkdir,writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import path from 'node:path';
import {ROOT,BLENDER} from '../utils/paths.js';
import {runCommand} from '../utils/runCommand.js';

export const InspectionConfig = z.object({
  character:z.object({id:z.string().min(1),name:z.string().min(1),version:z.string().min(1),source:z.string(),license:z.object({name:z.string(),commercialUse:z.boolean().nullable(),attribution:z.string()}).strict()}).strict().optional(),
  targetRig:z.enum(['demo-v1','mascot-v2']).default('demo-v1'),
  armature:z.string().min(1).optional(),
  boneMap:z.record(z.string(),z.string().min(1)).default({}),
  actionMap:z.partialRecord(z.enum(['idle','walk','run','jump','wave','turn','look_at']),z.string().min(1)).default({}),
  orientation:z.object({up:z.enum(['X','Y','Z','-X','-Y','-Z']),forward:z.enum(['X','Y','Z','-X','-Y','-Z'])}).strict().refine(v=>v.up.replace('-','')!==v.forward.replace('-',''),'Up and forward axes must differ').optional(),
  heightMeters:z.object({min:z.number().positive(),max:z.number().positive()}).strict().refine(v=>v.min<v.max,'Height minimum must be less than maximum').default({min:.5,max:4}),
}).strict();
export type InspectionOptions=z.input<typeof InspectionConfig>;
export async function inspectCharacter(filename:string, options:InspectionOptions={}) {
  const config=InspectionConfig.parse(options);
  const source=await realpath(filename);
  if (!['.blend','.glb','.fbx'].includes(path.extname(source).toLowerCase())) throw new Error('Expected a .blend, .glb or .fbx character file');
  if (!(await stat(source)).isFile()) throw new Error('Character source is not a file');
  const jobDir=path.join(ROOT,'jobs','inspect-'+randomUUID());
  await mkdir(jobDir,{recursive:true});
  const request=path.join(jobDir,'inspection-request.json');
  await writeFile(request,JSON.stringify({source,config},null,2));
  console.log('Compatibility report:',path.join(jobDir,'compatibility.json'));
  await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',path.join(ROOT,'workers/blender/inspect_character.py'),'--',request,jobDir],ROOT);
  return jobDir;
}
