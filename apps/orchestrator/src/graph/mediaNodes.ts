import {mkdir,readdir} from 'node:fs/promises';
import path from 'node:path';
import {ROOT,BLENDER} from '../utils/paths.js';
import {runCommand} from '../utils/runCommand.js';
export type VideoSpec={durationSeconds:number,fps:number,resolution:{width:number,height:number}};
type MediaState={jobDir:string,plan:VideoSpec|null};
export async function renderFrames(state: MediaState) {
    console.log("4. Rendering animation...");

    await runCommand(
      BLENDER,
      ["--background", "--disable-autoexec", "--factory-startup", path.join(state.jobDir, "scene.blend"), "--render-anim"],
      ROOT,
    );

    return {};
}
export async function encodeVideo(state: MediaState) {
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
}
