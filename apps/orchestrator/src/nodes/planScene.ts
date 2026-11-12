import { listAssets } from "../assets/registry.js";
import { ChatOpenAI } from "@langchain/openai";
import type { ScenePlan } from "../schemas/scene.js";
import { LLMSceneSchema, normalizeScenePlan } from "../schemas/llmScene.js";

export const SCENE_OUTPUT_OPTIONS = { name: "scene_plan", method: "jsonSchema", strict: true } as const;

export async function generateScenePlan(prompt: string, modelOverride?: ChatOpenAI): Promise<ScenePlan> {
  const available = (await listAssets()).map(asset => ({id:asset.id,name:asset.name,actions:Object.keys(asset.actions)}));
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
- Character actions: idle, walk, run, jump, wave; ordered nonoverlapping inclusive frame ranges
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
Do not invent unsupported objects or features.
      `.trim(),
    },
    {
      role: "user",
      content: prompt,
    },
  ]);

  return normalizeScenePlan(plan);
}
