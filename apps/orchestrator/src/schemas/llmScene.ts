import { z } from 'zod';
import { BallSchema, CharacterSchema, MascotSchema, MascotAction, SceneSchema, type ScenePlan } from './scene.js';

// OpenAI's strict subset excludes tuple prefixItems and requires every property.
// Nullable objects represent optional movement; application tuples stay unchanged.
const position = z.object({ x: z.number(), y: z.number(), z: z.number() }).strict();
const applicationAction = CharacterSchema.shape.character.shape.actions.element;
const character = CharacterSchema.extend({
  character: z.object({
    assetId: CharacterSchema.shape.character.shape.assetId,
    actions: z.array(z.object({
      name: applicationAction.shape.name,
      startFrame: applicationAction.shape.startFrame,
      endFrame: applicationAction.shape.endFrame,
      startPosition: position.nullable(),
      endPosition: position.nullable(),
    }).strict()).min(1),
  }).strict(),
}).strict();

const mascot = MascotSchema.extend({
  character: MascotSchema.shape.character.extend({
    actions:z.array(MascotAction.extend({startPosition:position.nullable(),endPosition:position.nullable()}).strict()).min(1),
  }).strict(),
}).strict();

// Nested anyOf is supported; the response root itself must be an object.
export const LLMSceneSchema = z.object({ scene: z.union([BallSchema, character, mascot, z.object({unsupported:z.string()}).strict()]) }).strict();

export function normalizeScenePlan(output: unknown): ScenePlan {
  const { scene } = LLMSceneSchema.parse(output);
  if ('unsupported' in scene) throw new Error('Unsupported request: '+scene.unsupported);
  if (!('character' in scene)) return SceneSchema.parse(scene);
  const tuple = (p: z.infer<typeof position>): [number, number, number] => [p.x, p.y, p.z];
  return SceneSchema.parse({
    ...scene,
    character: {
      ...scene.character,
      actions: scene.character.actions.map(({ startPosition, endPosition, ...action }) => ({
        ...action,
        ...(startPosition === null ? {} : { startPosition: tuple(startPosition) }),
        ...(endPosition === null ? {} : { endPosition: tuple(endPosition) }),
      })),
    },
  });
}
