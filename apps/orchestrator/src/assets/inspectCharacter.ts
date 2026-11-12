import {readFile} from 'node:fs/promises';
import {inspectCharacter,InspectionConfig} from './inspection.js';
async function main() {
  const args=process.argv.slice(2);
  if (!args[0] || args.length!==1 && !(args.length===3 && args[1]==='--config')) throw new Error('Usage: npm run assets:inspect -- character.blend [--config rig.json]');
  const config=args[2] ? InspectionConfig.parse(JSON.parse(await readFile(args[2],'utf8'))) : {};
  const directory=await inspectCharacter(args[0],config);
  const report=JSON.parse(await readFile(directory+'/compatibility.json','utf8'));
  console.log('Inspection completed:',report.status,'— this is not retargeting or automatic registration.');
}
main().catch(error=>{console.error('Inspection failed:',error);process.exitCode=1;});
