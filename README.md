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

## Strict OpenAI planning schema

The API uses `src/schemas/llmScene.ts`, separate from application validation in
`src/schemas/scene.ts`. The response is a strict object containing `scene` with a
nested ball/character union. Every property is required. Character actions use
required nullable `startPosition` and `endPosition`: both are either `{x,y,z}`
objects or `null`. Normalization converts objects to application `[x,y,z]` tuples
and removes null positions, then runs the unchanged `SceneSchema` checks.
Blender and saved plan formats are unchanged.

The previous wire schema contained unsupported tuple `prefixItems` with
`items: false`, and its action `required` list omitted the optional positions.
The root wrapper and `additionalProperties: false` were already present; defaults
and application refinements were not being sent. The planner explicitly uses
`method: "jsonSchema"` and `strict: true`; strict mode remains enabled.
See the [official supported schema rules](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas).

With Node 22+ selected and `OPENAI_API_KEY` configured in the orchestrator `.env`,
run live planning alone (no Blender invocation or job creation):

```sh
cd /Users/deb/Documents/learn/ai-foundation/youtube-3d-automation/apps/orchestrator
npm run plan -- "Create a 5-second animation of a cartoon character walking from left to right, stopping and waving at the camera"
npm run plan -- "Create a 5-second animation of a blue ball moving left to right"
```

Then run the complete character pipeline:

```sh
npm run assets:demo
npm run dev -- "Create a 5-second animation of a cartoon character walking from left to right, stopping and waving at the camera"
```

`npm test` includes ball and character normalization, retained application validation,
a conservative supported-keyword/schema-shape guard, and mocked OpenAI transport
tests that inspect the actual SDK-generated `response_format` and normalized output.
These offline checks do not establish live API acceptance; use `npm run plan` to
verify credentials, model access and schema acceptance against OpenAI.

## Milestone 4: Pebble mascot

Milestone 4 adds an original reusable `mascot-v2` asset without replacing
`demo-character-v1`. Its weighted rounded parts overlap at shoulders, hips, neck,
and wrists. Hands, feet, eyes, pupils, eyebrows, nose, crest and a curved mouth
make the character recognizable. Every part uses armature deformation; this is
an intentionally rigid-part rig, not seamless organic skin. Automatic geometry
and acting remain prototypes requiring artistic review.

The existing LangGraph nodes are retained. New plans add explicit render settings,
transition lengths and independent expressions. Strict OpenAI responses still
use required nullable movement objects; application validation restores tuples
and validates frame ranges, channel overlaps, positions and transition lengths.
Old plans, CLI prompts, and the original final video specification remain valid.

### Generate and use the mascot

Use Node 22+ in `apps/orchestrator`:

```sh
npm run assets:mascot
npm run assets:validate -- mascot-v2
npm run plan -- "Create a 10-second animation of Pebble the mascot walking, stopping, smiling, blinking and waving at the camera"
npm run dev -- "Create a 10-second animation of Pebble the mascot walking, stopping, smiling, blinking and waving at the camera"
```

Assets are generated once and reused. No paid service, third-party download or
asset-generation API is used. Model planning can choose a registered character;
manual supplied/licensed assets enter through the local registry workflow.

### Saved-plan rendering without an API key

```sh
npm run render:plan -- ../../assets/plans/mascot-v2.json --preview
npm run render:plan -- ../../assets/plans/mascot-v2.json
```

Preview is explicitly 640×360 with 8 EEVEE samples. Final is 1280×720 at 24 FPS
with 32 samples. Both use H.264 and FFprobe verification. New plans select
`soft_studio`, `sunny_outdoor`, or `neutral_preview` lighting. Legacy scenes retain
their previous settings. Every run creates a new isolated job; previous outputs
are not overwritten. Frame paths are configured before saving the scene.

### Import, normalize and validate licensed assets

Extend an existing registry entry or register a `.blend`, `.glb`, or `.fbx` under
`assets/`. Metadata includes source/provenance, license name/source/commercial-use
permission, optional attribution and URL, mesh names, armature name, required bones,
action mappings, optional facial-control mappings, rig definition (`demo-v1`,
`mascot-v2`, `custom`) and normalization (`scale`, `rotationDegrees`). Scale must
be finite and positive. Commercial-use permission must explicitly be true for
this commercial-video pipeline; retain the original license evidence yourself.

`npm run assets:validate -- your-asset-id` imports with auto-execution disabled,
checks registered meshes, rig, required bones, positive object scales, nonempty
local bone Action channels and OBJECT slots, then writes `normalized.blend` and
`validation.json` in a new `jobs/import-…` directory. Failures produce a report
and nonzero exit status. Bone paths are resolved against the actual imported rig;
matching an asset's name alone is not sufficient. Existing source files are not
modified. Copy a validated normalized asset into the approved asset directory
and register its new path to use it; when registering the normalized result,
set normalization to identity to avoid applying it twice. Apply/bake unsupported
constraints, retarget motion, pack textures, and verify axis conventions in Blender
before registration. This tool does not automatically retarget arbitrary rigs.

Custom rigs may use the new body sequencing format and their own registered
Actions. Facial sequencing currently requires the exact `mascot-v2` facial bone
convention: `face.mouth`, `face.brow.L/R`, `face.eye.L/R`, `face.pupil.L/R`.
Unsupported facial rigs fail explicitly; arbitrary shape-key assets require a
future adapter. Registry metadata never supplies executable scripts. Only trust
assets you have inspected; automatic Python execution remains disabled.

### Body transitions and facial channels

New action entries require `blendInFrames` and `blendOutFrames` (0–24). Their sum
must fit the action duration. Logical body ranges stay ordered and nonoverlapping;
NLA creates controlled internal overlaps, using the larger of the outgoing and
incoming blend lengths, bounded by available frames. Prior poses hold through
gaps, and higher tracks blend in rather than fading the whole rig to rest.
The final outgoing pose holds at the end of the video. Walk/run/idle cycle at their
native 24-frame rate; root position is animated separately and must be continuous.
Turn and look_at are reusable authored gestures toward the fixed camera, not
arbitrary target tracking. No foot IK or ground-contact solver is claimed.

Expressions have `name`, `startFrame`, `endFrame`, and `intensity` (0–1).
`neutral`, `smile`, `sad`, and `surprised` share the emotion channel; `blink`
uses eyelid/pupil scale, and `look_left`/`look_right` use pupil location. Conflicting
ranges on one channel are rejected. Separate channels can overlap, e.g. a smile
and blink while waving. Facial Actions only key facial bones, so they do not reset
body poses. Expressions ease in/out, and a blink closes at the range midpoint.
The mouth is a stylized curve of weighted rounded segments; it is not a deformable
lip or speech system. Surprise and sadness are basic stylized mouth changes.

### Tests and visual approval

```sh
npm run typecheck
npm test
npm run test:integration  # original character + ball renders
npm run test:mascot       # saved 10-second final mascot plan, no API key
```

Unit tests do not render. `test:mascot` requires the generated mascot asset and
checks the 240-frame final MP4, scene bounds across all frames, root movement,
body poses, facial changes and body/face independence. It also tests failed
imports (missing rig, bone, mesh, action or facial control). A new review job
contains front, three-quarter, neutral, smile, blink, walking and waving images,
plus beginning/middle/end frames and the complete MP4. These are technical and
visual review artifacts, not automatic proof of artistic quality. Human approval
of proportions, expressions, motion and final appearance remains necessary.

Known limitations: rigid body parts can reveal joint seams at extreme poses;
there is no mesh retopology, automatic rig retargeting, facial shape-key adapter,
foot locking, lip sync or production animation polish. Artists must normalize
licensed rigs, author compatible clips, inspect textures and approve appearance.
On sandboxed macOS, allow Metal GPU access for EEVEE rendering. An API key is
required only for live planning; saved-plan rendering remains entirely local.

If the planner cannot represent a requested feature, its strict response schema
also permits `scene: {"unsupported": "reason"}`. Normalization raises that reason
as an error before any job is built instead of substituting an unrelated motion.
A successful import report verifies supported technical conventions; it is not
proof of license ownership or human approval of the character's visual quality.

## Milestone 4.5 — Phase 1: external character inspection

Inspect a user-supplied local file without rendering, generating a video, changing
the source model, or registering it for production. No external assets or services
are downloaded. The existing `assets:validate` command remains the stricter
registered-asset normalization workflow; `assets:inspect` inventories unregistered
models and reports all discovered compatibility problems instead of stopping at
the first one.

With Node 22+ selected:

```sh
cd /Users/deb/Documents/learn/ai-foundation/youtube-3d-automation/apps/orchestrator
# Inventory first; the file can be outside assets/ because this is explicit read-only inspection.
npm run assets:inspect -- /absolute/path/to/character.blend
npm run assets:inspect -- /absolute/path/to/character.fbx
npm run assets:inspect -- /absolute/path/to/character.glb
# Then inspect with your explicit mapping configuration.
npm run assets:inspect -- /absolute/path/to/character.glb --config /absolute/path/to/rig.json
# Original procedural fixtures (generate once if missing).
npm run assets:demo
npm run assets:inspect -- ../../assets/characters/demo-character-v1.blend --config ../../assets/rigs/demo-v1.json
npm run assets:inspect -- ../../assets/characters/mascot-v2.blend --config ../../assets/rigs/mascot-v2.json
```

Each call prints a new `jobs/inspect-<uuid>/compatibility.json` path and retains
`inspection-request.json`. Source paths are resolved and checked for file type;
arguments use no shell. Blender auto-execution is disabled. No scripts can be
specified in config. Only inspect trusted local assets: Blender importers are not
a security isolation boundary. Source models are never saved over or copied into
the approved registry automatically, and existing job videos are never opened.

### Mapping configuration

Copy `assets/rigs/demo-v1.json` or `mascot-v2.json` and edit it for the source rig.
`boneMap` maps **pipeline semantic bone → source bone name**, not the reverse.
For example, `"root": "Hips"`, `"torso": "Spine"`, `"head": "Head"`.
The required semantic bones are root, torso, head, arm.L/R, leg.L/R; the mascot
profile additionally requires face.mouth, face.brow.L/R, face.eye.L/R and
face.pupil.L/R. These intentionally describe the current project rigs rather than
a universal humanoid standard. Missing mappings, duplicate targets, unknown
semantic keys, absent bones and hierarchy mismatches are reported. Intermediate
bones are allowed in descendant relationships.

Optional `armature` selects one exact imported object when there are several.
`actionMap` maps supported semantic Actions to *embedded source Action names*.
`orientation` declares source-local up/forward axes; the inspector compares them
through the imported rig transform with Z up/-Y forward. It also checks the mapped
root-to-head direction. Geometric facing cannot be inferred reliably; omitted
orientation remains explicitly unverified. `heightMeters` defaults to 0.5–4 and
checks imported mesh bounding boxes using the inspection scene's unit scale.
`.blend` library loading does not import the source scene's unit settings, so
confirm units/scale with the asset supplier. This phase reports normalization
needs; it does not rotate, scale, rename bones or transfer animation.

Optional `character` records id, name, version, source and license metadata
(`name`, `commercialUse`: true/false/null, `attribution`). Unknown licensing is
reported for review; source-file metadata does not establish commercial rights.
Unknown config fields and invalid types/axes/height ranges fail before Blender.

### Compatibility report and status

The JSON includes source hash/provenance; mesh counts, vertex groups, bindings and
materials/textures; every armature's bone hierarchy, rest matrices, lengths and
transforms; embedded Actions with slots/channel paths and compatibility findings;
NLA tracks; shape keys, candidate facial bones and custom properties; explicit
required mappings; issues with severity and recommended fixes; and scale/orientation
findings. Facial names are candidates, not proof of expression semantics.

Statuses:

- `import_failed`: Blender could not read the file; a failure report is retained and the CLI exits nonzero.
- `incompatible`: technical errors such as missing mapped bones, wrong hierarchy, unbound meshes or invalid scale.
- `needs_mapping`: inspection succeeded but explicit bone mappings are incomplete.
- `needs_review`: mapped structural checks pass but orientation, license, selected Actions or other findings remain unresolved.
- `structural_checks_passed`: the requested structural checks pass; this does **not** mean transferred animation or artistic quality was verified.

An inspection with incompatibilities still exits successfully because a usable
report was produced. Consumers must read `status` and `issues`; successful CLI
execution does not approve an asset. All Phase 1 reports set `animationReady` to
false and explicitly state that retargeting is not implemented or tested.

`pipelineLocalBoneChannelsCompatible` checks an embedded Action against the
selected rig's actual RNA paths and array indices, a single OBJECT slot/layer/strip,
keyframes, and nonzero duration. It does not prove skin quality or the motion's
visual result. Multiple-layer/multi-slot and object-root animation need a future
adapter or source normalization. Rest-pose rotations, bone axes, proportions,
skinning and source/target bind matrices have not been retargeted. A complete
bone map is only configuration for future work, never proof that the existing
project animation library can be applied safely.

### Tests and scope

```sh
npm run typecheck
npm test
npm run test:inspection
```

The Blender test generates original fixtures in a new job directory, exports
actual `.blend`, `.glb` and `.fbx` files, reimports all three and checks meshes,
materials, renamed skeletons, animations and shape keys. Negative fixtures cover
missing rig/mappings/bones/actions, duplicate mappings, hierarchy, orientation,
scale and corrupt files. No video rendering or API key is required. These are
controlled round-trip fixtures; vendor-specific purchased rigs remain untested.
The existing animation workers, graph and OpenAI response schemas are unchanged.

Before using a purchased character: obtain the file yourself with documented
commercial permission; run inventory; identify the actual rig and Action names;
provide mappings and confirm units/axes; resolve report errors; validate texture
paths and deformation; author compatible source-specific Actions or implement and
test retargeting in a later phase; add a facial adapter if necessary; and only
then register the approved local asset and run visual animation tests. Phase 1
makes no purchases, implements no retargeting and does not implement later 4.5 phases.

Blender adapter reference: [import operators](https://docs.blender.org/api/main/bpy.ops.import_scene.html).

Example excerpt from the procedural mascot's actual report (full report also
contains the mesh, material, skeleton and Action-channel inventories):

```json
{
  "status": "structural_checks_passed",
  "targetRig": "mascot-v2",
  "animationReady": false,
  "animationCompatibility": {
    "existingLocalActionChannelChecksPassed": true,
    "projectLibraryTransferVerified": false,
    "restPoseAndBoneAxesTransferVerified": false
  },
  "retargeting": {
    "implemented": false,
    "tested": false,
    "mappingApplied": false
  }
}
```

## Milestone 4.5 Phase 2 — Wolf Warrior native Action review

This is an asset-specific native playback adapter, **not retargeting**. Supply the
licensed source yourself at `assets/characters/wolf-warrior/character.blend`.
The source binary and companion textures are ignored by Git. Only the review
manifest (`asset.json`) is included. The manifest deliberately records commercial
permission as **unverified/false**; a successful technical test grants no publishing
rights. Verify the actual commercial license and attribution terms separately
before production publishing. There is no publishing command in this phase.

Run with Node 22+ and Blender 5.3 available:

```sh
cd /Users/deb/Documents/learn/ai-foundation/youtube-3d-automation/apps/orchestrator
npm run wolf:review
```

No API key is required. The command uses the existing LangGraph build/render/
FFmpeg/FFprobe infrastructure with a fixed saved plan. Wolf resolution is enabled
only through this explicit review command; it is not offered to the normal LLM
planner. Existing ball, demo and mascot plans keep their original worker. Only
idle → walk → idle at frames 1–72, 73–168, 169–240 is authorized by this adapter;
movement positions, expressions and other body sequences are rejected.

The native manifest maps `idle` to `01-Idle(60)` (0–216) and `walk` to
`02-Walk (42)` (0–31). `00-Key` is not a motion clip and is not used. The adapter
assigns each native OBJECT Action slot explicitly, checks actual RNA channels,
and sequences repeated clips with six-frame NLA overlaps. Original Action
keyframes, rig constraints, IK/FK properties, drivers, materials, and source file
remain intact. Rig-widget meshes and source lights/cameras are excluded from the
review render. No native rig animations are replaced with project-library clips.

Before saving, the worker checks native evaluated Body deformation, differences
between idle and walk, driver validity and auto-execution failures. It determines
forward from evaluated Head/nose control positions, measures bounds over all
240 frames, applies one common placement transform, and checks framing/floor
clearance on every frame. Floor placement uses the minimum evaluated Body height
across the sequence, with 1.5 cm clearance; this avoids penetration but can leave
small gaps and is not a foot-contact solver. The static camera shows the full body
with studio lighting. Source-specific textures must be packed or present locally;
missing textures block rendering rather than silently replacing them.

Automatic scripts stay disabled during build, render and preview. Blender's safe
native/driver evaluation is retained; invalid drivers, non-simple scripted drivers
or blocked execution halt with `animation-report.json` diagnostics. Do not enable
untrusted scripts to bypass a failure. Ask the author for baked native Actions
and a script-free rig when necessary.

Output is a fresh `jobs/wolf-review-<uuid>/` containing:

- `plan.json`, `asset.json`, `scene.blend`
- `frames/` and `output/animation.mp4` (H.264, 1280×720, 24 FPS, 240 frames, 10 seconds)
- `animation-report.json`: source hash, native channel/slot information, mesh-motion
  deltas, drivers, textures, facing, placement, frame/floor checks and FFprobe data
- `previews/`: start/middle/end images for each of the three segments (nine images)

The report remains `verified_pending_human_visual_review` after technical success.
Inspect preview images and the MP4 for facing, motion, deformation, transitions
and foot contact. Native digitigrade posture and the source's materials are
preserved. Root travel, wave, facial animation, generic retargeting and additional
characters are deliberately out of scope.

Tests:

```sh
npm run typecheck
npm test
npm run test:integration
# Validate an already-completed wolf job without rerendering it:
WOLF_REVIEW_JOB="/absolute/path/to/jobs/wolf-review-UUID" npm run test:wolf
```

Unit tests do not need the proprietary binary. The wolf artifact test checks the
original source hash, 552-bone native rig, idle/walk evaluated motion evidence,
saved-scene deformation, framing/floor checks, nine previews and MP4 metadata.
The source file is never saved over. Existing generated jobs are not modified.

## Milestone 4.5 Phase 3 — character animation controller

```sh
cd /Users/deb/Documents/learn/ai-foundation/youtube-3d-automation/apps/orchestrator
npm run wolf:motion-review
```

This deterministic, API-free command produces a fresh review-only job with a
15-second H.264 MP4, 1280×720, 24 FPS, 360 PNG frames, `scene.blend`,
`animation-report.json`, action-boundary preview images, and isolated facial
experiment files. The original `wolf:review` command and the ball/demo/mascot
interfaces remain available. The wolf source and licensing restrictions from
Phase 2 still apply: no commercial publishing is authorized by a successful test.

### Validated instructions and architecture

`assets/plans/wolf-motion.json` is the source instruction document. It specifies
initial world position/heading, camera preset and a contiguous timeline:

| Seconds | State |
| --- | --- |
| 0–2 | Native idle |
| 2–3 | Relative turn +90 degrees |
| 3–8 | Native walk, from [-1.5,0,0] to [1.5,0,0], average speed 0.6 m/s |
| 8–10 | Face the camera |
| 10–13 | Layered right-arm wave (three wrist oscillations) |
| 13–15 | Native idle |

`animation/animationSchema.ts` validates instructions, frame-aligned timestamps,
contiguous/nonoverlapping states, positions, duration, minimum stable segment
lengths, known actions and speed/distance consistency. `motionPlanner.ts` compiles
inclusive frame ranges and provides heading/position interpolation utilities.
`characterController.ts` creates the application scene envelope used by the
existing LangGraph graph. Derived body scheduling is checked against the
instructions to prevent contradictory plans. Controller scenes have their own
explicit duration schema; legacy ball/character duration limits and the strict
OpenAI transport schema are unchanged. The normal LLM planner does not yet emit
controller scenes; a future LLM transport adapter must normalize output into the
same validated `ControllerSchema` rather than bypassing these checks.

The Python `character_controller.py` adapter reuses safe native loading, Action
slots, driver checks, studio setup and source preservation from Phase 2. It adds
a separate `CharacterMotion` parent above the normalization hierarchy, preserving
rig scale, local skinning, constraints and IK/FK state. `motion_utils.py` provides
smooth/shortest-path heading operations and camera helpers. Native idle remains
a continuous base NLA track; walking replaces it during locomotion, and a new
right-arm-only ADD track supplies the gesture. Original native clips are not edited.
This is a controller/adapter boundary, not a universal rig or retargeting system.
The current wolf verification adapter requires a walk and wave segment and is
fully exercised only on the shipped demonstration; other rigs require adapters.

### Coordinates, travel and cadence

One world unit represents one metre. Z is up. Heading 0 faces world -Y; positive
heading turns toward +X. Turns support relative/absolute degrees, `faceTarget`
with a position, and `turnToCamera`. Heading interpolation takes the shortest
angular path. The walker must already face its destination; sideways movement
is rejected instead of silently rotating mid-walk. Walking uses a near-linear
path with short acceleration/deceleration ramps and exact endpoint placement.
Provided speed is the segment's average speed; plateau speed is slightly higher
to compensate for those ramps. Scene frames are numbered from 1; conceptual
half-open time intervals compile to inclusive sampled frame ranges.

The adapter inspects native walk channel paths before adding world motion and
refuses unexpected object/Root channels. Tests also check the evaluated rig-local
Root for drift. Native foot motion and the 31-frame cycle are measured in the
scaled character space. Median backward low-foot velocity determines clip cadence;
world movement then counteracts that stance motion. The report compares
horizontal Foot-control speed with and without translation at the same cadence.
The contact proxy is a control origin within 4.5 cm of its own sequence minimum,
not a sole sensor. Measurements are not a claim of foot locking. The demonstrated
cadence correction reduces this proxy but leaves noticeable residual sliding.
There is no new IK/contact solver, and turn-in-place foot pivoting is not locked.

Floor placement samples the full evaluated sequence and adds 1.5 cm minimum
clearance. The entire character, including gesture bounds, is checked against the
full-body camera throughout all 360 frames. Source digitigrade posture is retained.

### Wave and facial experiments

`assets/characters/wolf-warrior/animation-config.json` contains the tested native
cycle, axes, foot names and source-specific FK gesture controls/offsets. The wave
uses only `FK_UpperArm.R`, `FK_Forearm.R`, and `FK_Hand.R`, with smooth raise/lower
envelopes, elbow bend and three wrist oscillations. The original FK/IK properties
and constraints are retained. Tests verify evaluated hand lift, mesh changes,
opposite-arm independence and return to the underlying idle after the gesture.
The pose is asset-specific and needs artistic review at other clip phases.

`facial_experiments.py` runs separately on a newly loaded copy of the original
rig, without changing the demo. `experiments/head_nod.blend` and
`experiments/jaw_open_close.blend` contain isolated test Actions.
`experiments/facial-report.json` records evaluated mesh response and driver checks.
Head control and `ORG_Jaw` produce experimental responses; author confirmation of
the intended jaw mapping is still required. Blink and eyebrow mappings are not
verified and are reported as unsupported/unmapped, rather than inferred from
unrelated deformation bones. These experiments are not production facial acting.

### Cameras and verification

Camera presets are `full_body`, `medium`, and `close_up`, fitted using evaluated
bounds. The full-body preset includes the full motion path. Medium/close-up are
static end-position shots and intentionally crop the lower body; they do not
promise full-path visibility. A deterministic position/orientation/orthographic
scale transition helper is tested, but camera transitions are not yet scheduled
through the scene instructions. The first demonstration uses the stable fixed
full-body camera and records its actual position for final heading verification.

```sh
npm run typecheck
npm test
# Verify a completed controller render, including Blender save/reload checks:
WOLF_MOTION_JOB="/absolute/path/to/jobs/wolf-motion-UUID" npm run test:controller
# Existing regressions:
npm run test:integration
WOLF_REVIEW_JOB="/absolute/path/to/jobs/wolf-review-UUID" npm run test:wolf
```

Controller tests check schema/timing errors, overlaps, unsupported motions,
heading/position interpolation, world displacement, native deformation, heading,
layered waving and idle restoration, floor clearance, framing, root continuity,
camera presets/transition helper, source hash and FFprobe metadata. Automatic
scripts remain disabled in every worker invocation. Reports separate numerical
checks from required human visual review. New outputs never replace old videos.

Known limits: only the wolf adapter is tested; sequential state scheduling does
not yet expose simultaneous walk-and-wave instructions; no generic retargeting,
full IK foot locking, blink/brow adapter, camera timeline, dialogue, lip-sync or
multi-character behavior is implemented. Next steps should be visual approval,
source-specific contact refinement and verified facial mappings, not expansion
into unrelated scene features.

## Milestone 4.5 Phase 3.1 — animation polish and cinematic shots

```sh
cd /Users/deb/Documents/learn/ai-foundation/youtube-3d-automation/apps/orchestrator
npm run wolf:polish-review
```

The new command is opt-in. `wolf:motion-review`, `wolf:review`, existing scene
plans and OpenAI transport schemas remain unchanged. `assets/plans/wolf-polish.json`
keeps the original 15-second character timeline but adds `polish: true` and
explicit `cameraShots`. Output is a new `jobs/wolf-polish-UUID/` containing the
360-frame H.264 MP4, saved scene, report, individual previews and `contact-sheet.png`.
No facial work, retargeting, additional characters or Milestone 5 features are added.

### Baseline and honest contact measurements

By default, comparison uses the Phase 3 job
`wolf-motion-a81b0258-42d3-4856-9b7d-03af047ac992`. To use another equivalent
unpolished baseline:

```sh
WOLF_BASELINE_JOB="/absolute/path/to/jobs/wolf-motion-UUID" npm run wolf:polish-review
```

The baseline must be inside this project's jobs directory and use the identical
source hash, 360 frames and 3 m displacement. Its scene is opened read-only with
auto-execution disabled; evaluated Foot-control samples from frames 78–186 are
written only into the new job. This permits a paired comparison without changing
old reports, scenes or videos. The command requires a completed Phase 3 baseline.

Contact detection combines low relative foot-control height (4.5 cm band) **and**
low vertical velocity (0.16 m/s), not height alone. Short detection gaps of up to
three frames are bridged for correction activation, but the original measurement
masks are retained. Statistics use identical baseline masks for before/after
comparisons. A separate legacy height-only comparison reproduces Phase 3's
approximately 0.324 m/s value. Neither method proves physical sole contact.

Native IK leg mode and unconstrained `Foot.L/R` controls are checked before a
new ADD track applies bounded local location offsets. World-space stance anchors
are converted into native control space. Corrections blend in at touchdown and
release over 12 frames after stance. Native constraints, pole targets and IK/FK
properties are not disabled or replaced. The native walk cycle and speed-based
cadence adjustment remain in use.

The initial stronger correction was rejected because it stretched evaluated leg
segments excessively. The accepted implementation calibrates a per-frame gain by
bisection, limits leg-segment length changes to 5% relative to the uncorrected
pose, and conservatively anticipates those limits. A 35 cm world-offset cap also
applies. This is **partial native-IK stance stabilization**, not an unlimited foot
lock or a new general-purpose IK solver. Toe-off drift and turn-in-place sliding
remain; the correction does not promise zero sliding.

`animationQuality.footContact` records mean **and maximum** stance speeds,
baseline mask definitions, correction bounds/gains, measured leg-length ratios,
foot-step sizes and comparison frames. Lower mean sliding must not be interpreted
as elimination of the remaining maximum-speed outliers. Acceptance of skinning,
contact timing and visual quality still requires human review.

### Wave v2 and transitions

`Wolf.Controller.Wave.v2` is a new Action; v1 is retained. It uses the same three
verified right-arm FK controls with isolated rotation channels. A small shoulder
preparation precedes raising; elbow motion lags the shoulder; two smaller wrist
waves run during the hold; wrist and elbow settle with overlapping follow-through
as the arm lowers. Underlying native idle remains active. No deformation bones
or opposite-arm channels are directly keyed.

Walk NLA transitions use 8-frame entry and 12-frame exit blends. Root timing and
3 m displacement are unchanged. Reports retain adjacent-frame root/heading/mesh
metrics and add boundary-specific deltas with warnings for unusually large pose
changes. Legitimate fast movement is recorded separately from numerical failures;
passing thresholds is not proof that the acting is natural. Gesture diagnostics
include hand lift, elbow-angle range, wrist/head control distance, opposite-arm
independence and return-to-idle comparison. Control distances are not a mesh
self-collision test.

### Instruction-level cinematic camera scheduling

Each camera shot requires `start`, `end`, `preset` (`wide` or `medium`),
`target: "wolf-warrior-native"`, `transition` (`cut` or `smooth`) and
`transitionFrames`. Shots must cover the timeline contiguously, align with frames,
and use zero transition frames for cuts or at least two for smooth interpolation.
The initial shot starts with a cut. Close-up scheduling is deliberately not exposed
in this milestone; Phase 3's static close-up helper remains available.

The demonstration uses tracking-wide framing for 0–8 seconds, an explicit cut to
medium for 8–10 seconds, and a continuous medium shot for 10–15 seconds. Bounds
are evaluated for the relevant poses, including the raised hand. Wide shots show
the whole body and partially track its translation so movement remains visible.
Medium shots intentionally crop below the waist while retaining the gesture region.
Shot-union extents keep the lens stable instead of breathing on every arm movement.

Camera transforms and orthographic scale are keyed deterministically. Smooth
transitions interpolate position, orientation and scale; an integration fixture
exercises an actual wide-to-medium interpolation. Deliberate cuts are excluded
from continuity-failure metrics. `animationQuality.camera` records shot boundaries,
cut frames, framing checks and continuous movement metrics. Full-body clipping
rules apply to wide shots; medium checks apply to the declared upper-body region.

### Review artifacts and tests

The contact sheet preserves 16:9 aspect ratios and labels initial idle, turn,
mid-stride, near-destination walk, stop, camera-facing turn, wave preparation,
peak, follow-through, lowering, completion and final idle. The job also retains
individual action-boundary images. The verification report preserves previous
fields and adds `animationQuality` sections for contact, wave, transitions and
camera, along with explicit visual limitations and human-review requirements.

```sh
npm run typecheck
npm test
WOLF_POLISH_JOB="/absolute/path/to/jobs/wolf-polish-UUID" npm run test:polish
```

Tests cover contact height/velocity detection, paired measurement masks, correction
release, camera validation, cuts and interpolation, shot framing, Wave v1/v2
separation, channel isolation, idle restoration, native Action curve integrity,
source hash, leg-stretch safety, saved-scene reload and MP4 metadata. Existing
rendering and inspection tests are retained.

Modified/added implementation files: `animationSchema.ts`, `wolfPolishReview.ts`,
`character_controller.py`, `animation_polish.py`, `foot_contact.py`,
`cinematic_camera.py`, `contact_baseline.py`, `polish_previews.py`,
`wolf-polish.json`, polish unit/integration tests, `test_polish.py`,
`test_foot_contact_unit.py`, package scripts and this README.

All outputs remain `reviewOnly: true` and `productionPublishingAllowed: false`.
Review the video and contact sheet before authorizing further animation work.
Commercial licensing is still unverified. Recommended follow-up is human-directed
sole/contact calibration and gesture timing refinement; Milestone 5 is not started.

Accepted review measurements (paired baseline frames 78–186):

| Metric | Phase 3 | Safe polish candidate |
| --- | ---: | ---: |
| Mean stance proxy, height + vertical velocity | 0.336 m/s | 0.156 m/s |
| Mean original height-only proxy | 0.324 m/s | 0.151 m/s |
| Maximum paired stance proxy | 1.222 m/s | 1.216 m/s |

Mean reduction is about 54%; maximum residual sliding is nearly unchanged.
The evaluated leg-length ratio stays below 1.05. The largest all-motion Foot-control
step increases from about 9.0 to 12.5 cm/frame during a swing/release interval
(frame 125→126), rather than a detected planted-foot interval. It is recorded for
visual review, not dismissed as proof of perfect contact. Extra full-body foot
motion/stop diagnostic images are provided so medium-shot cropping does not hide
those poses. The original source and native Action curve data pass integrity checks.

## Milestone 4.5 Phase 3.2 — performance refinement (review only)

Run from `apps/orchestrator` with Node 22+, Blender 5.3 and FFmpeg installed:

```sh
npm run wolf:performance-review
```

This uses the existing LangGraph render/encode workflow with the deterministic
`assets/plans/wolf-performance.json` plan; it does not call OpenAI. Existing
`wolf:review`, `wolf:motion-review` and `wolf:polish-review` behavior is retained.
The sequence remains idle → turn → 3-meter walk → turn to camera → wave → idle,
15 seconds, 360 frames, 24 FPS, 1280×720 H.264. The existing camera scheduler
recomputes composition from the refined, evaluated geometry: full-body tracking
wide through frame 192, intentional medium cut at 193, smooth continuation at 241.
All evaluated Body vertices in each shot's required region are checked with 1.5%
frame margins; medium shots deliberately crop the lower body.

The opt-in controller `performance` block requires `polish: true`. It adds:

- Four-frame quintic contact onset, a default 24-frame quintic release, and a
  deterministic safety-gain envelope limited to 0.045 change per frame. The
  existing bounded native Foot-control correction and evaluated 1.05 leg-length
  ratio limit remain in force. No rig constraints or IK/FK settings are disabled.
- `Wolf.Controller.Wave.v3`, alongside the preserved v1/v2 Actions, layered over
  native idle with Blender Action slots. It uses the original right FK arm and
  `FK_Spine_02` controls, delayed elbow/wrist movement, two small wrist cycles,
  a lower greeting pose, subtle torso motion and smooth recovery.

Wave parameters (edit the plan before running):

| Parameter | Default | Meaning / supported range |
| --- | ---: | --- |
| `intensity` | 0.85 | Anticipation, torso and small arm accents; 0.4–1 |
| `handHeight` | 0.8 | Shoulder rotation multiplier, **not a height in meters**; 0.75–1 |
| `waveCount` | 2 | Exactly two verified cycles; other counts rejected |
| `wristAmplitude` | 0.17 | Wrist oscillation amplitude in radians; 0.08–0.28 |
| `anticipation` | 0.12 | Fraction of normalized gesture duration; 0.06–0.18 |
| `recovery` | 0.28 | Fraction reserved for lowering; 0.2–0.35 |

`releaseFrames` accepts 16–32 (default 24). Only the default parameter combination
has been rendered and visually inspected. All variants must pass the existing
safety/framing checks and require human review. Slight opposite-hand movement
from the torso is intentional; no opposite-arm channels are authored.
The application controller schema is separate from the unchanged OpenAI-facing
strict response schema.

A unique `jobs/wolf-performance-UUID/` contains:

```text
scene.blend                        # existing repository convention
output/animation.mp4
animation-report.json
comparison-report.json
performance-baseline.json          # read-only capture of Phase 3.1
performance-foot-samples.json
contact-sheet.png
visual-review-checklist.md
previews/foot-contact/             # includes full-body stop diagnostics
previews/wave/                     # includes Phase 3.1 frame 276 when present
previews/camera/                   # walking, stopping, cut boundaries
```

The Phase 3.1 default baseline is
`jobs/wolf-polish-14813eea-226b-4cdf-8e76-ed2bad140de4`.
Override it with a matching Phase 3.1 job inside `jobs/`:

```sh
WOLF_PERFORMANCE_BASELINE="/absolute/path/to/jobs/wolf-polish-UUID" npm run wolf:performance-review
```

Missing baseline files produce `available: false` with a reason; no before values
are fabricated. Current, unpaired metrics remain available, explicitly separate
from the paired comparison. Invalid baselines (different asset, v3 Action, or
wrong duration) fail. Previous jobs and the source character are not overwritten.

### Measured Phase 3.1 → Phase 3.2 comparison

Verified review job: `jobs/wolf-performance-4af821b9-1d31-4803-a981-bfdf351e7c2c`.

| Metric | Phase 3.1 | Phase 3.2 | Result |
| --- | ---: | ---: | --- |
| Mean stance sliding | 0.155787 m/s | 0.136156 m/s | 12.6% lower; **0.12 target missed** |
| 95th percentile stance sliding | 0.967426 m/s | 0.667692 m/s | 31.0% lower; target met |
| Maximum stance sliding | 1.215726 m/s | 1.150004 m/s | 5.4% lower; **15% reduction target missed** |
| Maximum swing/release step | 12.484 cm | 10.915 cm | 12.6% lower; target met |
| Maximum vertical foot step | 1.4166117 cm | 1.4166132 cm | +0.0000015 cm, numerical-only increase |
| Minimum evaluated Body/floor clearance | 1.500003 cm | 1.500005 cm | No measured penetration |
| Maximum evaluated leg-length ratio | 1.049773 | 1.049880 | Slight increase; within the existing 5% limit |
| Travel | 3 m | 3 m | Preserved |

Stance measurements use the **same 120 baseline-defined foot pairs**, frames
78–186, a 4.5 cm height band, vertical speed ≤0.16 m/s. Correction intervals separately bridge gaps of
up to three frames; the measurement masks themselves are not bridged. Speeds are horizontal Foot-control origins, not calibrated
sole-pressure contacts. The p95 uses linear interpolation of sorted paired speeds.
Swing and vertical steps use frames 73–216 for both runs, covering the longer
release. Raw deltas, meaningful regressions and positive numerical-only deltas
(≤1e-6 meters or m/s) are all recorded.

The actual cause of the residual spikes is bounded contact correction competing
with translated native gait and the leg-extension limit, especially near contact
boundaries; the old shorter release and rapidly varying safety gains also
contributed to swing steps. A longer C2 release and rate-limited safety envelope
reduce those effects without increasing stretch. They do not correct the native
cycle's entire root/sole mismatch or create true toe contacts. More aggressive
locking was not used to meet a metric at the expense of leg safety.

Wave v2's large shoulder rotation produced the high-arm appearance. V3 lowers
that rotation, adds a small native torso accent and gives the two wrist cycles
slightly varying timing/amplitude. Its peak wrist is about 0.303 m above the
Head **control origin** (not above the ears). Conservative evaluated weighted
hand/head and hand/chest AABBs show no overlap in this candidate. These checks
exclude weakly weighted vertices/fur and do not replace triangle collision or
human inspection of shoulder clearance. The saved scene returns exactly to
native idle after the wave layer ends.

### Verification and limits

```sh
npm run typecheck
npm test
WOLF_PERFORMANCE_JOB="/absolute/path/to/jobs/wolf-performance-UUID" npm run test:performance
WOLF_POLISH_JOB="/absolute/path/to/jobs/wolf-polish-UUID" npm run test:polish
WOLF_MOTION_JOB="/absolute/path/to/jobs/wolf-motion-UUID" npm run test:controller
WOLF_REVIEW_JOB="/absolute/path/to/jobs/wolf-review-UUID" npm run test:wolf
npm run test:inspection
npm run test:integration
npm run test:mascot
```

New tests cover deterministic bounded gain envelopes, release endpoints, fixed
measurement masks, parameter validation, Action slots, two wrist cycles,
anticipation/recovery, idle restoration, native Action curve integrity, source
hash, saved-scene reload, leg safety, camera boundaries/hand and head region
visibility, missing-baseline reporting and FFprobe metadata. Existing strict
OpenAI schema, procedural character, ball, mascot and importer tests are retained.

Technical checks are distinct from artistic approval. The contact sheet shows a
lower hand position and complete walking framing; stills cannot establish natural
wrist timing, convincing toe-off, absence of visible snapping or knee distortion.
Review both videos and the full-body foot diagnostics using the checklist.
Residual sliding remains substantial, and mean/worst-case targets remain unmet.
All outputs stay `reviewOnly: true`, `productionPublishingAllowed: false` and
`verified_pending_human_visual_review`. Script auto-execution remains disabled;
the external character's commercial license remains unverified. Milestone 5 and
other later phases have not been started.

Implementation files: controller schema and package scripts; `wolfPerformanceReview.ts`;
`wolf-performance.json`; `animation_polish.py`; `character_controller.py`;
`performance_math.py`, `performance_refinement.py`, `performance_baseline.py`,
`performance_previews.py`; TypeScript performance unit/integration tests;
`test_performance.py`, `test_performance_math_unit.py`; this README.

Executed Phase 3.2 verification: TypeScript check passed; 21 unit tests passed;
7 integration tests passed across performance, polish, controller, native wolf,
character inspection, procedural character/ball rendering and the 10-second mascot.
The integration tests include saved-scene Blender checks and FFprobe verification.
Detailed logs and the file manifest are in the new job’s `implementation-report.md`
and `test-logs/`. Artistic approval remains pending.
