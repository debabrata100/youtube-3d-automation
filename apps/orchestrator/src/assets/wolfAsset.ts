import {readFile,realpath} from 'node:fs/promises';
import path from 'node:path';
import {z} from 'zod';
import {ROOT} from '../utils/paths.js';
export const WolfAssetSchema=z.object({id:z.literal('wolf-warrior-native'),name:z.string(),version:z.string(),path:z.literal('characters/wolf-warrior/character.blend'),armature:z.literal('Armature'),meshes:z.array(z.string()),bones:z.array(z.string()),actions:z.object({idle:z.literal('01-Idle(60)'),walk:z.literal('02-Walk (42)')}).strict(),adapter:z.literal('wolf-native'),reviewOnly:z.literal(true),license:z.object({name:z.string(),source:z.string(),commercialUse:z.literal(false)}).strict()}).strict();
export type WolfAsset=z.infer<typeof WolfAssetSchema>&{absolutePath:string};
export async function resolveWolfAsset():Promise<WolfAsset>{
  const root=await realpath(path.join(ROOT,'assets'));
  const asset=WolfAssetSchema.parse(JSON.parse(await readFile(path.join(root,'characters/wolf-warrior/asset.json'),'utf8')));
  const absolutePath=await realpath(path.join(root,asset.path));
  if(!absolutePath.startsWith(root+path.sep))throw new Error('Wolf source escapes approved assets directory');
  return {...asset,absolutePath};
}
