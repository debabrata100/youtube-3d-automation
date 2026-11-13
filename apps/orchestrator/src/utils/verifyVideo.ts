import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import type { VideoSpec } from '../graph/mediaNodes.js';
export async function verifyVideo(filename:string, plan:VideoSpec) {
  const {stdout} = await promisify(execFile)('ffprobe',['-v','error','-count_frames','-select_streams','v:0','-show_streams','-show_format','-of','json',filename]);
  const result = JSON.parse(stdout);
  const s = result.streams[0];
  const [n,d] = String(s?.avg_frame_rate).split('/').map(Number);
  if (!s || s.codec_name !== 'h264' || s.width !== plan.resolution.width || s.height !== plan.resolution.height || Number(n)/Number(d) !== plan.fps || Number(s.nb_read_frames) !== plan.fps*plan.durationSeconds || Math.abs(Number(result.format.duration)-plan.durationSeconds) > 1/plan.fps)
    throw new Error('FFprobe video validation failed: '+stdout);
  return result;
}
