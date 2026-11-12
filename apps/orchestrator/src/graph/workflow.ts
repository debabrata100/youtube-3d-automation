import { StateGraph, START, END } from "@langchain/langgraph";
import { writeFile, mkdir, readdir, stat } from "node:fs/promises";
import path from "node:path";

import { AnimationState } from "./state.js";
import { generateScenePlan } from "../nodes/planScene.js";
import { runCommand } from "../utils/runCommand.js";

import { ROOT, BLENDER } from '../utils/paths.js';
import { resolveAsset, validateAnimations } from '../assets/registry.js';
import { SceneSchema } from '../schemas/scene.js';
import { verifyVideo } from '../utils/verifyVideo.js';

const workerScript = path.join(ROOT, "workers/blender/build_from_plan.py");

export function createWorkflow(planner = generateScenePlan) {
return new StateGraph(AnimationState)
  .addNode("planScene", async (state) => {
    console.log("1. Planning scene...");

    const plan = await planner(state.prompt);
    console.log(JSON.stringify(plan, null, 2));

    return { plan };
  })

  .addNode('resolveAssets', async state => {
    const plan = SceneSchema.parse(state.plan);
    return {plan, asset: 'character' in plan ? await resolveAsset(plan.character.assetId) : null};
  })
  .addNode('validateAnimations', async state => {
    if (!state.plan) throw new Error('Missing scene plan');
    validateAnimations(state.plan,state.asset);
    return {};
  })
  .addNode("savePlan", async (state) => {
    console.log("2. Saving plan...");

    if (!state.plan) {
      throw new Error("Scene plan is missing");
    }

    await mkdir(state.jobDir, { recursive: true });

    await writeFile(
      path.join(state.jobDir, "plan.json"),
      JSON.stringify(state.plan, null, 2),
    );

    if (state.asset) await writeFile(path.join(state.jobDir,"asset.json"), JSON.stringify(state.asset,null,2));
    return {};
  })

  .addNode("buildScene", async (state) => {
    console.log("3. Building Blender scene...");

    await runCommand(
      BLENDER,
      [
        "--background",
        "--disable-autoexec",
        "--factory-startup",
        "--python-exit-code", "1",
        "--python",
        workerScript,
        "--",
        path.join(state.jobDir, "plan.json"),
        state.jobDir,
      ],
      ROOT,
    );

    return {};
  })

  .addNode("renderFrames", async (state) => {
    console.log("4. Rendering animation...");

    await runCommand(
      BLENDER,
      ["--background", "--disable-autoexec", path.join(state.jobDir, "scene.blend"), "--render-anim"],
      ROOT,
    );

    return {};
  })

  .addNode("encodeVideo", async (state) => {
    console.log("5. Encoding MP4...");

    if (!state.plan) {
      throw new Error("Scene plan is missing");
    }

    const framesDir = path.join(state.jobDir, "frames");
    const outputDir = path.join(state.jobDir, "output");
    const videoPath = path.join(outputDir, "animation.mp4");

    const expectedFrames = state.plan.durationSeconds * state.plan.fps;

    const frames = (await readdir(framesDir)).filter((name) =>
      /^frame_\d{4}\.png$/.test(name),
    );

    if (frames.length !== expectedFrames) {
      throw new Error(
        `Expected ${expectedFrames} frames, found ${frames.length}`,
      );
    }

    await mkdir(outputDir, { recursive: true });

    await runCommand(
      "ffmpeg",
      [
        "-y",
        "-framerate",
        String(state.plan.fps),
        "-start_number",
        "1",
        "-i",
        path.join(framesDir, "frame_%04d.png"),
        "-frames:v",
        String(expectedFrames),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        videoPath,
      ],
      ROOT,
    );

    return { videoPath };
  })

  .addNode("verifyVideo", async (state) => {
    console.log("6. Verifying output...");

    if (!state.videoPath || !state.plan) {
      throw new Error("Missing video or scene plan");
    }

    const file = await stat(state.videoPath);

    if (file.size === 0) {
      throw new Error("Generated video is empty");
    }

    await verifyVideo(state.videoPath, state.plan);
    console.log("Video exists:", state.videoPath);
    console.log("File size:", file.size, "bytes");

    return {};
  })

  .addEdge(START, "planScene")
  .addEdge("planScene", "resolveAssets")
  .addEdge("resolveAssets", "validateAnimations")
  .addEdge("validateAnimations", "savePlan")
  .addEdge("savePlan", "buildScene")
  .addEdge("buildScene", "renderFrames")
  .addEdge("renderFrames", "encodeVideo")
  .addEdge("encodeVideo", "verifyVideo")
  .addEdge("verifyVideo", END)
  .compile();

}
export const workflow = createWorkflow();
