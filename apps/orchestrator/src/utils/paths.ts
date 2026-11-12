import { fileURLToPath } from 'node:url';
export const ROOT = fileURLToPath(new URL('../../../../', import.meta.url));
export const BLENDER = process.env.BLENDER_PATH ?? '/Applications/Blender.app/Contents/MacOS/Blender';
