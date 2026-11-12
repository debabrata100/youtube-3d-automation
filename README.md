# Reusable 3D animation pipeline

TypeScript orchestrates a LangGraph workflow:

`planScene → resolveAssets → validateAnimations → savePlan → buildScene → renderFrames → encodeVideo → verifyVideo`

OpenAI produces a structured plan. Zod validates it before registered local assets are resolved; Blender builds a deterministic scene, renders PNGs, and FFmpeg encodes H.264. FFprobe checks resolution, frame rate, decoded frame count and duration. Existing untagged `ball` + `floor` plans remain supported alongside `character` + `environment` plans through a strict structural union. Plans cannot supply paths or executable code.

## Setup and execution

Requires Node.js 22+, Blender 5.3, FFmpeg and FFprobe on PATH. On macOS install Blender in Applications, or set `BLENDER_PATH` to its executable.

```sh
cd apps/orchestrator
node --version # must be 22 or newer; select your Node 22 installation first
npm ci
cp .env.example .env
# Set OPENAI_API_KEY in .env (never commit it).
npm run assets:demo
npm run dev -- "Create a 5-second animation of a cartoon character walking from left to right, stopping and waving at the camera"
```

Generate the demo asset once before character jobs. It is original procedural geometry with rigid armature weights, seven bones, basic materials, and five Actions with stable IDs `demo.idle.v1`, `demo.walk.v1`, `demo.run.v1`, `demo.jump.v1`, and `demo.wave.v1`. Generated binary assets and jobs are ignored by Git. No third-party assets are downloaded.

Jobs use UUID directories under `jobs/` and contain `plan.json`, `asset.json` (characters only), `scene.blend`, `frames/frame_0001.png` through the final frame, and `output/animation.mp4`. Existing generated jobs are never edited by tests. Paths derive from source locations rather than the caller's working directory.

## Character plans

```json
{
  "durationSeconds": 5,
  "fps": 24,
  "resolution": {"width": 1280, "height": 720},
  "character": {
    "assetId": "demo-character-v1",
    "actions": [
      {"name": "walk", "startFrame": 1, "endFrame": 72, "startPosition": [-3,0,0], "endPosition": [0,0,0]},
      {"name": "wave", "startFrame": 73, "endFrame": 120}
    ]
  },
  "environment": {"type": "simple-ground", "color": "green"}
}
```

Frame ranges are inclusive, ordered and nonoverlapping, with end greater than start. They must fit the duration (1–10 seconds at 24 FPS). Both movement positions must be supplied together. Positions omitted on later actions retain the last position; explicit later movement must start there. Movement is linear on a separate `CharacterRoot` object; local Actions may only target pose bones. NLA strips use REPLACE, no extrapolation, and short fades to the rest pose inside each range. Gaps return to the rest pose. Action duration is scaled to each requested segment; the demo walk/run each perform one cycle per segment.

## Register a commercially licensed character

1. Obtain a character yourself with a license explicitly permitting your intended commercial videos and local processing. Keep proof of purchase and check attribution requirements and redistribution restrictions.
2. Import its `.blend`, `.glb`, or `.fbx` in Blender 5.3. Normalize scale and orientation: Z up, facing camera toward negative Y, feet on Z=0, origin centered. Keep its armature, meshes, weights and parent relationships. Remove unrelated cameras, lights, constraints, scripts and external dependencies; pack textures in Blender for portability.
3. Prepare local, in-place bone Actions for the supported motions. Bake constraints to pose channels if needed. Remove object/root scene translation from Actions; keep scene travel separate. Save one OBJECT slot per Action, all bound to the registered rig, with pose bone channels only and a nonzero frame range. For GLB/FBX, confirm imported Action names in Blender; exporters can rename them. Converting the normalized result to `.blend` is recommended.
4. Place the file under `assets/characters/`. Add an entry to `assets/characters/registry.json`: unique `id`, `name`, `version`, relative `path`, exact `armature` object name, required `bones`, supported `actions` mapping (semantic name to Blender Action name), and `license` (`name`, `source`, `commercialUse: true`). Only `.blend`, `.glb`, and `.fbx` paths contained within `assets/`, including after symlink resolution, are accepted. Do not put licensed binaries in version control unless redistribution is allowed.
5. The planner reads available IDs and supported motions from the registry. Request the registered character by name or ID. Unsupported motions are rejected. Test a deterministic plan before using the asset in production.

## Add animations

Author an in-place bone Action on the target rig and register its exact stable name in the asset's `actions` map. The supported semantic vocabulary is `idle`, `walk`, `run`, `jump`, `wave`. To extend it, update `ActionName` in `src/schemas/scene.ts`, the planner instructions, registry mapping and tests. The procedural source in `workers/blender/character.py` shows keyframe creation using the modern slot/channelbag API; it never reads legacy `action.fcurves`.

## Tests

```sh
cd apps/orchestrator
npm run typecheck
npm test
npm run test:integration
```

Integration generates the demo asset and runs the real LangGraph pipeline with an injected deterministic planner, requiring no API call. It renders separate five-second character and legacy ball jobs and verifies H.264, 1280×720, 24 FPS, 120 decoded frames and approximately five seconds. It reopens each `.blend` to inspect frame output paths and ball movement; character checks include bones, NLA strips, action slots and channels, evaluated walk/wave poses, actual mesh deformation, root translation and stopping. Unit tests cover schema failures, invalid ranges/overlaps, unsupported actions, missing/unknown assets, path escape and symlinks. Natural-language planning requires an API key and is separate from offline integration tests.

## Limitations and troubleshooting

The demo is a rigid-segment humanoid, not a production character. There is no automatic retargeting, IK, foot locking, lip sync, asset download or arbitrary model generation. Normalize real rigs and supply their own Actions. Walk and run speed depend on segment length; transitions fade through rest instead of overlapping clips. The fixed camera supports bounded movement (X ±3, Y ±2, ground Z=0). Review real characters for framing and deformation.

Blender 5.3 uses slotted Actions: use `bpy_extras.anim_utils.action_get_channelbag_for_slot` and `NlaStrip.action_slot`, not legacy `action.fcurves`. Python exceptions exit Blender with a nonzero status. Background asset loading and rendering disable automatic script execution; register only trusted assets.

On macOS EEVEE needs access to a Metal device. A restricted sandbox or headless session can fail with “no default Metal device available”; run integration in a local session permitted to use the GPU. The USD `ARCH_CACHE_LINE_SIZE` startup warning is harmless when Blender continues successfully. Check `BLENDER_PATH` if spawn fails. Missing asset errors mean `npm run assets:demo` has not run or the registry path is wrong. Missing bones/actions or multiple Action slots require normalizing the source asset. If TypeScript fails with `ERR_UNKNOWN_FILE_EXTENSION`, check `node --version` in the orchestrator directory; some shell setups select an older Node there. Use Node 22 or newer. FFmpeg/FFprobe must both be on PATH. A failed job remains available for inspection; retry with a fresh job directory.

Blender API references: [slotted Actions migration](https://developer.blender.org/docs/release_notes/5.0/python_api/) and [Blender 5.3 NLA strips](https://docs.blender.org/api/5.3/bpy.types.NlaStrip.html).
