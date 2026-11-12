import { test } from 'node:test';
import assert from 'node:assert/strict';
import { z } from 'zod';
import { toJsonSchema } from '@langchain/core/utils/json_schema';
import { ChatOpenAI } from '@langchain/openai';
import { LLMSceneSchema, normalizeScenePlan } from '../src/schemas/llmScene.js';
import { PlanningSchema } from '../src/schemas/scene.js';
import { generateScenePlan } from '../src/nodes/planScene.js';
import { ball, character } from './fixtures.js';

const llmBall = { scene: ball };
const llmCharacter = {
  scene: {
    ...character,
    character: {
      ...character.character,
      actions: character.character.actions.map(action => ({
        ...action,
        startPosition: action.startPosition ? { x: -3, y: 0, z: 0 } : null,
        endPosition: action.endPosition ? { x: 0, y: 0, z: 0 } : null,
      })),
    },
  },
};

// Conservative guard for the documented strict subset used by this schema.
// It rejects unknown keywords rather than pretending to validate arbitrary schemas.
function assertStrictSubset(schema: unknown, root = true, document = schema as Record<string, any>): void {
  assert.ok(schema && typeof schema === 'object' && !Array.isArray(schema));
  const s = schema as Record<string, any>;
  const allowed = new Set(['$schema', 'title', 'description', 'type', 'properties', 'required', 'additionalProperties',
    '$defs', '$ref', 'items', 'anyOf', 'enum', 'const', 'minimum', 'maximum', 'minItems', 'maxItems', 'pattern']);
  for (const key of Object.keys(s)) assert.ok(allowed.has(key), `Unsupported keyword: ${key}`);
  if (root) { assert.equal(s.type, 'object'); assert.equal(s.anyOf, undefined); }
  if (s.$defs) for (const definition of Object.values(s.$defs)) assertStrictSubset(definition, false, document);
  if (s.$ref) {
    assert.match(s.$ref, /^#\/\$defs\//);
    assert.ok(Object.hasOwn(document.$defs ?? {}, s.$ref.slice('#/$defs/'.length)), 'Unresolved schema reference');
    return;
  }
  if (s.anyOf) {
    assert.ok(Array.isArray(s.anyOf) && s.anyOf.length > 0);
    for (const branch of s.anyOf) assertStrictSubset(branch, false, document);
  } else {
    const types = Array.isArray(s.type) ? s.type : [s.type];
    for (const type of types) assert.ok(['object','array','string','number','integer','boolean','null'].includes(type));
  }
  if (s.type === 'object') {
    assert.equal(s.additionalProperties, false);
    assert.ok(s.properties && typeof s.properties === 'object');
    assert.deepEqual([...s.required].sort(), Object.keys(s.properties).sort());
    for (const value of Object.values(s.properties)) assertStrictSubset(value, false, document);
  }
  if (s.type === 'array') {
    assert.ok(s.items && typeof s.items === 'object' && !Array.isArray(s.items));
    assertStrictSubset(s.items, false, document);
  }
}
test('LLM ball and character responses normalize to unchanged application plans', () => {
  assert.deepEqual(normalizeScenePlan(llmBall), ball);
  assert.deepEqual(normalizeScenePlan(llmCharacter), character);
});

test('normalization preserves application validation and strict LLM fields', () => {
  const invalids = [
    { scene: { ...ball, durationSeconds: 11 } },
    { scene: { ...ball, ball: { ...ball.ball, radius: 5 } } },
    { ...llmBall, extra: true },
  ];
  for (const invalid of invalids) assert.throws(() => normalizeScenePlan(invalid));
  for (const patch of [
    { startPosition: undefined },
    { startPosition: null }, // one null, one movement position
    { startPosition: [-3,0,0] },
    { startPosition: { x: -4, y: 0, z: 0 } },
    { startPosition: { x: -3, y: 0, z: 1 } },
    { name: 'dance' },
    { endFrame: 121 },
    { endFrame: 73 }, // overlaps the wave
    { path: '/tmp/evil.blend' },
  ]) {
    const invalid = structuredClone(llmCharacter);
    Object.assign(invalid.scene.character.actions[0]!, patch);
    assert.throws(() => normalizeScenePlan(invalid));
  }
});

test('actual LangChain-generated JSON Schema conforms to supported strict subset', () => {
  assertStrictSubset(toJsonSchema(LLMSceneSchema));
  // Reproduce the old schema failure rather than assuming the root union caused it.
  const old = toJsonSchema(z.object({ scene: PlanningSchema }));
  assert.throws(() => assertStrictSubset(old));
  const encoded = JSON.stringify(old);
  assert.ok(encoded.includes('"prefixItems"'));
  for (const invalid of [
    { type: 'object', properties: {}, required: [], additionalProperties: true },
    { type: 'object', properties: { x: { type: 'number' } }, required: [], additionalProperties: false },
    { anyOf: [{ type: 'null' }] },
    { type: 'object', properties: {}, required: [], additionalProperties: false, default: {} },
  ]) assert.throws(() => assertStrictSubset(invalid));
});

for (const [name, output, expected] of [
  ['ball', llmBall, ball], ['character', llmCharacter, character],
] as const) {
  test(`planner sends strict response_format and normalizes ${name} via mocked API transport`, async () => {
    let requests = 0;
    const model = new ChatOpenAI({
      model: 'gpt-4.1-mini', apiKey: 'test-only', temperature: 0, maxRetries: 0,
      configuration: {
        fetch: async (_input, init) => {
          requests++;
          const body = JSON.parse(init?.body ? String(init.body) : await new Request(_input).text());
          assert.equal(body.response_format.type, 'json_schema');
          assert.equal(body.response_format.json_schema.strict, true);
          assert.equal(body.response_format.json_schema.name, 'scene_plan');
          assertStrictSubset(body.response_format.json_schema.schema);
          return new Response(JSON.stringify({
            id: 'test', object: 'chat.completion', created: 0, model: 'gpt-4.1-mini',
            choices: [{ index: 0, finish_reason: 'stop', message: { role: 'assistant', content: JSON.stringify(output) } }],
            usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
          }), { headers: { 'Content-Type': 'application/json' } });
        },
      },
    });
    let result;
    try { result = await generateScenePlan(`Create a ${name} animation`, model); }
    catch (error) { throw (error as Error).cause ?? error; }
    assert.deepEqual(result, expected);
    assert.equal(requests, 1);
  });
}
