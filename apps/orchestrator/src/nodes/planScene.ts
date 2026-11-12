import { listAssets } from "../assets/registry.js";
import { ChatOpenAI } from "@langchain/openai";
import type { ScenePlan } from "../schemas/scene.js";
import { LLMSceneSchema, normalizeScenePlan } from "../schemas/llmScene.js";

export const SCENE_OUTPUT_OPTIONS = { name: "scene_plan", method: "jsonSchema", strict: true } as const;

export async function generateScenePlan(prompt: string, modelOverride?: ChatOpenAI): Promise<ScenePlan> {
  const available = (await listAssets()).map(asset => ({id:asset.id,name:asset.name,actions:Object.keys(asset.actions),expressions:Object.keys(asset.facialControls ?? {})}));
  const model = modelOverride ?? new ChatOpenAI({
    model: process.env.OPENAI_MODEL ?? "gpt-4.1-mini",
    temperature: 0,
  });

  const planner = model.withStructuredOutput(LLMSceneSchema, SCENE_OUTPUT_OPTIONS);

  const plan = await planner.invoke([
    {
      role: "system",
      content: `
You are a 3D animation scene planner.

Convert user requests into structured Blender
scene configurations.

Supported capabilities:
- One animated sphere OR one registered cartoon character from this registry: ${JSON.stringify(available)}
- Legacy character actions: idle, walk, run, jump, wave
- For cute mascot requests choose mascot-v2 (Pebble). It also supports turn and look_at
- Mascot plans require renderMode final (1280x720) unless preview is requested (640x360), lighting soft_studio, and expressions array
- Mascot body actions require blendInFrames and blendOutFrames (use 6); logical action ranges must not overlap
- Facial names: neutral, smile, sad, surprised, blink, look_left, look_right; each expression requires startFrame, endFrame, intensity 0..1
- Use short blink ranges of 6 frames, independently overlapping body actions and smiles. Emotion ranges cannot overlap each other; gaze ranges cannot overlap each other
- For 10 seconds: walk 1-96 from [-3,0,0] to [0,0,0], look_at 97-120, wave 121-240; smile 100-240, blinks 140-146 and 200-206
- Ordered nonoverlapping inclusive body frame ranges
- Use character + environment for characters, ball + floor for spheres, never both
- For walking then waving over 5 seconds use walk frames 1-72 with startPosition {x:-3,y:0,z:0} and endPosition {x:0,y:0,z:0}, wave frames 73-120
- Every action must include startPosition and endPosition: use {x,y,z} objects for movement, or null for BOTH to preserve position
- Return the scene inside the required scene wrapper
- Frame 1 is the first frame; final frame is durationSeconds * 24
- Use environment type simple-ground and color green
- A flat floor
- Linear movement along the X axis
- Fixed camera and lighting
- Maximum duration: 10 seconds

Use 24 FPS and 1280x720 resolution.
Choose sensible defaults for unspecified values.
Do not invent unsupported objects or features. If a requested feature cannot be represented, return scene as {"unsupported":"A clear explanation of the unsupported feature"}; do not silently substitute a supported action.
      `.trim(),
    },
    {
      role: "user",
      content: prompt,
    },
  ]);

  return normalizeScenePlan(plan);
}
