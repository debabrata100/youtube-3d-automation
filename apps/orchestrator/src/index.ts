import "dotenv/config";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { ROOT } from "./utils/paths.js";
import { workflow } from "./graph/workflow.js";

async function main() {
  const prompt = process.argv.slice(2).join(" ").trim();

  if (!prompt) {
    throw new Error('Usage: npm run dev -- "Animate a blue ball"');
  }

  if (!process.env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is missing");
  }

  const jobId = randomUUID();

  const jobDir = path.join(ROOT, "jobs", jobId);

  console.log("Job ID:", jobId);
  console.log("Prompt:", prompt);

  const result = await workflow.invoke({
    prompt,
    jobId,
    jobDir,
    asset: null,
    plan: null,
    videoPath: null,
  });

  console.log("\nAnimation completed!");
  console.log("Video:", result.videoPath);
}

main().catch((error) => {
  console.error("Pipeline failed:", error);
  process.exitCode = 1;
});
