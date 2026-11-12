import { Annotation } from "@langchain/langgraph";
import type { ScenePlan } from "../schemas/scene.js";

import type { Asset } from "../assets/registry.js";

export const AnimationState = Annotation.Root({
  asset: Annotation<Asset | null>,
  prompt: Annotation<string>,
  jobId: Annotation<string>,
  jobDir: Annotation<string>,
  plan: Annotation<ScenePlan | null>,
  videoPath: Annotation<string | null>,
});
