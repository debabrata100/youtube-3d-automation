import { z } from 'zod';
export const ActionName = z.enum(['idle', 'walk', 'run', 'jump', 'wave']);
const position = z.tuple([z.number().min(-3).max(3), z.number().min(-2).max(2), z.literal(0)]);
const common = {
  durationSeconds: z.number().int().min(1).max(10), fps: z.literal(24),
  resolution: z.object({width: z.literal(1280), height: z.literal(720)}).strict(),
};
export const BallSchema = z.object({...common,
  ball: z.object({color: z.enum(['red','blue','green','yellow','purple']), startX: z.number().min(-3).max(3), endX: z.number().min(-3).max(3), radius: z.number().min(.3).max(1.5)}).strict(),
  floor: z.object({color: z.enum(['green','blue','gray','yellow'])}).strict(),
}).strict();
export const CharacterSchema = z.object({...common,
  character: z.object({assetId: z.string().regex(/^[a-z0-9][a-z0-9-]*$/), actions: z.array(z.object({
    name: ActionName, startFrame: z.number().int().min(1), endFrame: z.number().int().min(2),
    startPosition: position.optional(), endPosition: position.optional(),
  }).strict()).min(1)}).strict(),
  environment: z.object({type: z.literal('simple-ground'), color: z.enum(['green','blue','gray','yellow'])}).strict(),
}).strict();
// Structural union preserves existing untagged Milestone 2 plans.
export const PlanningSchema = z.union([BallSchema, CharacterSchema]);
export const SceneSchema = PlanningSchema.superRefine((plan, ctx) => {
  if (!('character' in plan)) return;
  let previous = 0;
  for (const [i, action] of plan.character.actions.entries()) {
    if (action.endFrame <= action.startFrame || action.endFrame > plan.durationSeconds * plan.fps || action.startFrame <= previous)
      ctx.addIssue({code: 'custom', path: ['character','actions',i], message: 'Actions must be ordered, nonoverlapping, and fit the video; endFrame must exceed startFrame'});
    if (!!action.startPosition !== !!action.endPosition)
      ctx.addIssue({code:'custom', path:['character','actions',i], message:'Provide both movement positions or neither'});
    previous = action.endFrame;
  }
});
export type ScenePlan = z.infer<typeof SceneSchema>;
