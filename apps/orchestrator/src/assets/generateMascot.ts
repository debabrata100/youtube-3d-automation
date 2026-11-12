import path from 'node:path';
import { ROOT, BLENDER } from '../utils/paths.js';
import { runCommand } from '../utils/runCommand.js';
await runCommand(BLENDER,['--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',path.join(ROOT,'workers/blender/mascot.py'),'--',path.join(ROOT,'assets/characters/mascot-v2.blend')],ROOT);
