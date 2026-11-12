import 'dotenv/config';
import { generateScenePlan } from './nodes/planScene.js';

async function main() {
  const prompt = process.argv.slice(2).join(' ').trim();
  if (!prompt) throw new Error('Usage: npm run plan -- "Animate a blue ball"');
  if (!process.env.OPENAI_API_KEY) throw new Error('OPENAI_API_KEY is missing; live planning requires an API key');
  console.log(JSON.stringify(await generateScenePlan(prompt), null, 2));
}
main().catch(error => {
  console.error('Planning failed:', error);
  process.exitCode = 1;
});
