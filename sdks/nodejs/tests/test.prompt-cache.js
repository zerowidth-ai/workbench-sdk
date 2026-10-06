// Prompt caching: cache marks go where a model that needs them can reuse
// the prompt, and nowhere else; and what the provider read from and wrote
// to its prompt cache is kept on a model call's usage and cost breakdown.
//
// The upstream call is faked by patching the integration's OpenAI
// client (same approach as test.custom-inference.js).

import assert from "assert";
import OpenRouterIntegration, { readCacheUsage } from "../src/integrations/openrouter.js";
import { applyPromptCache } from "../src/utilities/promptCache.js";

const MARK = { type: "ephemeral" };
const marked = (b) => Boolean(b && b.cache_control);
const conversation = () => [
  {
    role: "system",
    content: [
      { type: "text", text: "You help the team.\n\n", cache_control: MARK },
      { type: "text", text: "Now: 2026-10-05 12:00" },
    ],
  },
  { role: "user", content: "First question" },
  { role: "assistant", content: "First answer" },
  { role: "user", content: [{ type: "text", text: "Second question" }] },
];

let failures = 0;
function check(name, fn) {
  return fn().then(
    () => console.log(`  ✓ ${name}`),
    (err) => {
      failures++;
      console.error(`  ✗ ${name}\n    ${err.message}`);
    },
  );
}

function fakeStream(chunks) {
  return (async function* () {
    for (const c of chunks) yield c;
  })();
}

const pricing = {
  items: [
    { key: "input_cost_per_million", cost: 3 },
    { key: "output_cost_per_million", cost: 15 },
  ],
};

console.log("prompt-cache:");

await check("a Claude call keeps the system prompt's mark and marks the last user message", async () => {
  const input = conversation();
  const out = applyPromptCache(input, { model: "anthropic/claude-sonnet-4.6" });
  assert.ok(marked(out[0].content[0]), "fixed part of the system prompt stays marked");
  assert.ok(!marked(out[0].content[1]), "the changing part is never marked");
  assert.ok(!Array.isArray(out[1].content), "earlier user turns are left alone");
  assert.ok(marked(out[3].content[0]), "the last user message is marked");
  assert.ok(!marked(input[3].content[0]), "the input isn't changed");
});

await check("other models get no marks at all", async () => {
  const out = applyPromptCache(conversation(), { model: "openai/gpt-5" });
  for (const m of out) {
    if (Array.isArray(m.content)) assert.ok(!m.content.some(marked), `${m.role} still carries a mark`);
  }
});

await check("caching off removes every mark, even for Claude", async () => {
  const out = applyPromptCache(conversation(), { model: "anthropic/claude-sonnet-4.6", enabled: false });
  assert.ok(!out[0].content.some(marked));
  assert.ok(!Array.isArray(out[3].content) || !out[3].content.some(marked));
});

await check("never more than four marks, keeping the earliest", async () => {
  const many = [
    { role: "system", content: [1, 2, 3, 4, 5].map((n) => ({ type: "text", text: `part ${n}`, cache_control: MARK })) },
    { role: "user", content: "hi" },
  ];
  const out = applyPromptCache(many, { model: "anthropic/claude-sonnet-4.6" });
  assert.deepEqual(out[0].content.map(marked), [true, true, true, true, false]);
  assert.equal(out[1].content, "hi", "no room left for the user mark");
});

await check("a mark on an empty block is dropped", async () => {
  const out = applyPromptCache(
    [{ role: "system", content: [{ type: "text", text: "", cache_control: MARK }] }, { role: "user", content: "hi" }],
    { model: "anthropic/claude-sonnet-4.6" },
  );
  assert.ok(!marked(out[0].content[0]));
});

await check("the request a Claude node sends carries the marks; the engine option turns them off", async () => {
  for (const [promptCache, expectMarks] of [[undefined, true], [false, false]]) {
    const i = new OpenRouterIntegration("k");
    i._engineConfig = promptCache === undefined ? {} : { promptCache };
    let sent = null;
    i.client.chat.completions.create = async (payload) => {
      sent = payload;
      return fakeStream([{ object: "chat.completion.chunk", choices: [{ delta: { role: "assistant", content: "ok" }, finish_reason: "stop" }] }]);
    };
    await i.chatCompletion({ model: "anthropic/claude-sonnet-4.6", messages: conversation() }, { type: "x", id: "llm" });
    assert.equal(marked(sent.messages[0].content[0]), expectMarks, `promptCache=${promptCache}`);
  }
});

await check("reads cached and written tokens from a usage block", async () => {
  assert.deepEqual(readCacheUsage({ prompt_tokens_details: { cached_tokens: 900, cache_write_tokens: 100 } }), {
    cached_tokens: 900,
    cache_write_tokens: 100,
  });
  assert.deepEqual(readCacheUsage({ prompt_tokens: 5 }), { cached_tokens: 0, cache_write_tokens: 0 });
  assert.deepEqual(readCacheUsage(undefined), { cached_tokens: 0, cache_write_tokens: 0 });
});

await check("a streamed call keeps the cache counts on usage and on the input cost line", async () => {
  const i = new OpenRouterIntegration("k");
  i.client.chat.completions.create = async () =>
    fakeStream([
      { object: "chat.completion.chunk", choices: [{ delta: { role: "assistant", content: "Hi" }, finish_reason: null }] },
      {
        object: "chat.completion.chunk",
        choices: [{ delta: {}, finish_reason: "stop" }],
        usage: {
          prompt_tokens: 1000,
          completion_tokens: 10,
          total_tokens: 1010,
          cost: 0.0012,
          prompt_tokens_details: { cached_tokens: 800, cache_write_tokens: 150 },
        },
      },
    ]);
  const res = await i.chatCompletion(
    { model: "anthropic/claude-sonnet-4.6", messages: [{ role: "user", content: "hi" }] },
    { type: "anthropic-claude-sonnet-4-6", id: "llm", pricing },
    {},
  );
  assert.equal(res.usage.cached_tokens, 800);
  assert.equal(res.usage.cache_write_tokens, 150);
  assert.equal(res.cost_total, 0.0012, "the provider's total (already reflecting the cache) stays the total");
  const input = res.cost_itemized.find((c) => c.label === "Input Tokens");
  assert.equal(input.tokens, 1000);
  assert.equal(input.cached_tokens, 800);
  assert.equal(input.cache_write_tokens, 150);
});

await check("a call with no cache reports zeros and leaves the cost lines as they were", async () => {
  const i = new OpenRouterIntegration("k");
  i.client.chat.completions.create = async () =>
    fakeStream([
      { object: "chat.completion.chunk", choices: [{ delta: { role: "assistant", content: "Hi" }, finish_reason: "stop" }], usage: { prompt_tokens: 5, completion_tokens: 2, total_tokens: 7 } },
    ]);
  const res = await i.chatCompletion(
    { model: "x", messages: [{ role: "user", content: "hi" }] },
    { type: "x", id: "llm", pricing },
    {},
  );
  assert.equal(res.usage.cached_tokens, 0);
  assert.equal(res.usage.cache_write_tokens, 0);
  const input = res.cost_itemized.find((c) => c.label === "Input Tokens");
  assert.ok(!("cached_tokens" in input), "no cache keys when nothing was cached");
});

if (failures > 0) {
  console.error(`\n${failures} prompt-cache test(s) failed`);
  process.exit(1);
}
console.log("prompt-cache: all passed");
