import { readFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';
import { ROOT } from '../utils/paths.js';
import type { ScenePlan } from '../schemas/scene.js';
const AssetSchema = z.object({
  id:z.string(), name:z.string().min(1), version:z.string().min(1), path:z.string(), procedural:z.boolean().default(false),
  armature:z.string().min(1), bones:z.array(z.string()).min(1), actions:z.record(z.string(),z.string().min(1)),
  license:z.object({name:z.string().min(1), source:z.string().min(1), commercialUse:z.literal(true)}),
}).strict();
export type Asset = z.infer<typeof AssetSchema> & {absolutePath:string};
export async function listAssets(assetsRoot = path.join(ROOT,'assets')) {
  const entries = z.array(AssetSchema).parse(JSON.parse(await readFile(path.join(assetsRoot,'characters/registry.json'),'utf8')));
  if (new Set(entries.map(a=>a.id)).size !== entries.length) throw new Error('Duplicate asset ID');
  return entries;
}
export async function resolveAsset(id:string, assetsRoot = path.join(ROOT,'assets')):Promise<Asset> {
  const entries = await listAssets(assetsRoot);
  const asset = entries.find(a=>a.id===id);
  if (!asset) throw new Error(`Unknown character ID: ${id}`);
  if (path.isAbsolute(asset.path) || !['.blend','.glb','.fbx'].includes(path.extname(asset.path).toLowerCase())) throw new Error('Unsupported asset path');
  const root = await realpath(assetsRoot);
  const candidate = path.resolve(root,asset.path);
  if (!candidate.startsWith(root+path.sep)) throw new Error('Asset path escapes assets directory');
  let absolutePath:string;
  try { absolutePath = await realpath(candidate); }
  catch { throw new Error(`Missing character asset: ${asset.path}. Run npm run assets:demo`); }
  if (!absolutePath.startsWith(root+path.sep) || !(await stat(absolutePath)).isFile()) throw new Error('Invalid asset file');
  return {...asset,absolutePath};
}
export function validateAnimations(plan:ScenePlan, asset:Asset|null) {
  if (!('character' in plan)) return;
  if (!asset || asset.id !== plan.character.assetId) throw new Error('Character asset not resolved');
  let position = [0,0,0];
  for (const action of plan.character.actions) {
    if (!asset.actions[action.name]) throw new Error(`Unsupported animation: ${action.name}`);
    if (action.startPosition && action.startFrame !== 1 && action.startPosition.some((v,i)=>v !== position[i])) throw new Error('Root movement must be continuous between actions');
    position = action.endPosition ?? position;
  }
}
