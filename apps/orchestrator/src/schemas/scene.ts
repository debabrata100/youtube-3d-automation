import { z } from 'zod';
import {ControllerSceneSchema} from '../animation/animationSchema.js';
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
export const ExpressionName = z.enum(['neutral','smile','sad','surprised','blink','look_left','look_right']);
export const MascotAction = CharacterSchema.shape.character.shape.actions.element.extend({
  name: z.enum(['idle','walk','run','jump','wave','turn','look_at']),
  blendInFrames: z.number().int().min(0).max(24),
  blendOutFrames: z.number().int().min(0).max(24),
}).strict();
export const MascotSchema = CharacterSchema.extend({
  renderMode: z.enum(['preview','final']),
  resolution: z.union([common.resolution,z.object({width:z.literal(640),height:z.literal(360)}).strict()]),
  lighting: z.enum(['soft_studio','sunny_outdoor','neutral_preview']),
  character: z.object({
    assetId:CharacterSchema.shape.character.shape.assetId,
    actions:z.array(MascotAction).min(1),
    expressions:z.array(z.object({name:ExpressionName,startFrame:z.number().int().min(1),endFrame:z.number().int().min(2),intensity:z.number().min(0).max(1)}).strict()),
  }).strict(),
}).strict();
// Legacy shapes remain unchanged. Mascot plans explicitly configure rendering.
export const PlanningSchema = z.union([BallSchema, CharacterSchema, MascotSchema]);
const LegacySceneSchema = PlanningSchema.superRefine((plan, ctx) => {
  if (!('character' in plan)) return;
  if ('renderMode' in plan && plan.resolution.width !== (plan.renderMode === 'preview' ? 640 : 1280))
    ctx.addIssue({code:'custom',message:'Resolution must match renderMode'});
  let previous = 0;
  for (const [i, action] of plan.character.actions.entries()) {
    if (action.endFrame <= action.startFrame || action.endFrame > plan.durationSeconds * plan.fps || action.startFrame <= previous)
      ctx.addIssue({code: 'custom', path: ['character','actions',i], message: 'Actions must be ordered, nonoverlapping, and fit the video; endFrame must exceed startFrame'});
    if (!!action.startPosition !== !!action.endPosition)
      ctx.addIssue({code:'custom', path:['character','actions',i], message:'Provide both movement positions or neither'});
    if ('blendInFrames' in action && action.blendInFrames + action.blendOutFrames > action.endFrame-action.startFrame)
      ctx.addIssue({code:'custom',message:'Transition lengths exceed action duration'});
    previous = action.endFrame;
  }
  if ('expressions' in plan.character) {
    const channels = new Map<string,number>();
    for (const expression of [...plan.character.expressions].sort((a,b)=>a.startFrame-b.startFrame)) {
      const channel = expression.name === 'blink' ? 'eyelids' : expression.name.startsWith('look_') ? 'gaze' : 'emotion';
      if (expression.endFrame <= expression.startFrame || expression.endFrame > plan.durationSeconds*plan.fps || expression.startFrame <= (channels.get(channel) ?? 0))
        ctx.addIssue({code:'custom',message:'Expression ranges must fit duration and cannot overlap on the same facial channel'});
      channels.set(channel,expression.endFrame);
    }
  }
});
export const SceneSchema = z.union([LegacySceneSchema,ControllerSceneSchema]);
export type ScenePlan = z.infer<typeof SceneSchema>;
